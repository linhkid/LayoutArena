from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from typing import Any, Callable, Literal, Optional

import litellm
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_litellm import ChatLiteLLM

from layoutarena.llm.multimodal import (
    get_gemini_sanitize_mode,
    is_gemini_model,
    looks_like_gemini_image_error,
    sanitize_langchain_messages_for_gemini,
    sanitize_openai_messages_for_gemini,
)
from layoutarena.llm.schema import MessageContent
from layoutarena.llm.tracker import ResourceTracker
from layoutarena.llm.utils import (
    _build_langchain_messages,
    _build_openai_messages,
    _call_custom_endpoint_direct,
    _call_custom_endpoint_direct_async,
    _call_sagemaker_direct,
    _handle_non_streaming,
    _handle_streaming,
    _postprocess_response,
    _resolve_custom_endpoint,
    _supports_native_n,
    extract_code_block,
)

logger = logging.getLogger(__name__)

_ASYNC_LLM_SEMAPHORES_BY_LOOP_ID: dict[int, tuple[int, asyncio.Semaphore]] = {}

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Google AI Studio API keys often show up as ?key=... in exception URLs.
    (re.compile(r"([?&]key=)[^&\s'\"]+"), r"\1REDACTED"),
    (re.compile(r"([?&]api_key=)[^&\s'\"]+"), r"\1REDACTED"),
    # Common key formats (best-effort redaction; avoid leaking tokens into logs).
    (re.compile(r"AIza[0-9A-Za-z\-_]{20,}"), "REDACTED"),
    (re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}"), "REDACTED"),
    (
        re.compile(r"(Authorization:\s*Bearer)\s+[A-Za-z0-9\-_\.]+", re.IGNORECASE),
        r"\1 REDACTED",
    ),
)


def _redact_secrets(text: str) -> str:
    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _log_exception_redacted(prefix: str, exc: BaseException) -> None:
    """Log a traceback while redacting common secret patterns (API keys, bearer tokens)."""
    try:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        logger.error(_redact_secrets(f"{prefix}: {tb}"))
    except Exception:
        # Fall back to default logging if formatting/redaction fails.
        logger.exception(f"{prefix}: {exc}")


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_async_llm_semaphore() -> Optional[asyncio.Semaphore]:
    """
    Global (per-event-loop) concurrency limit for outbound LLM calls.

    Why: when many LangGraph runs hit the same node at the same time, they can
    burst a large number of LLM requests concurrently (especially with
    `asyncio.gather(...)`). This semaphore turns that burst into a queue.

    Configure via env var:
      - MPS_LLM_MAX_CONCURRENCY=0 (default, disabled)
      - MPS_LLM_MAX_CONCURRENCY=8 (cap concurrent async requests to 8)
    """
    limit = _get_int_env("MPS_LLM_MAX_CONCURRENCY", 0)
    if limit <= 0:
        return None

    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    entry = _ASYNC_LLM_SEMAPHORES_BY_LOOP_ID.get(loop_id)
    if entry is not None:
        stored_limit, sem = entry
        if stored_limit == limit:
            return sem

    sem = asyncio.Semaphore(limit)
    _ASYNC_LLM_SEMAPHORES_BY_LOOP_ID[loop_id] = (limit, sem)
    return sem


@asynccontextmanager
async def _llm_concurrency_guard():
    """
    Optional concurrency guard + jitter to de-batch LLM calls.

    Configure via env vars:
      - MPS_LLM_MAX_CONCURRENCY (int, 0=disabled)
      - MPS_LLM_JITTER_S (float seconds, default 0)
    """
    jitter_s = _get_float_env("MPS_LLM_JITTER_S", 0.0)
    if jitter_s > 0:
        await asyncio.sleep(random.random() * jitter_s)

    sem = _get_async_llm_semaphore()
    if sem is None:
        yield
        return

    async with sem:
        yield


def _call_litellm_native_n(
    model: str,
    messages: list[dict],
    temperature: float,
    num_samples: int,
    max_retries: int,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    resource_tracker: Optional[ResourceTracker] = None,
    **kwargs: Any,
) -> list[Optional[str | dict | list]]:
    """Call LiteLLM with native n parameter for multiple completions.

    Args:
        model: The resolved model name
        messages: OpenAI-format messages
        temperature: Sampling temperature
        num_samples: Number of completions to generate
        max_retries: Maximum retry attempts
        extract_code_flag: Whether to extract code blocks
        return_type: Return type for post-processing
        return_exception: Whether to return exceptions as strings
        resource_tracker: Resource tracker to update usage
        **kwargs: Additional arguments for litellm

    Returns:
        List of response contents
    """
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=temperature,
                n=num_samples,
                **kwargs,
            )
            if resource_tracker:
                resource_tracker.update_usage(response, model)  # type: ignore[arg-type]
            # Extract content from all choices
            results: list[Optional[str | dict | list]] = []
            for choice in response.choices:  # type: ignore
                content = choice.message.content or ""  # type: ignore
                processed = _postprocess_response(
                    content,
                    extract_code_flag,
                    return_type,
                )
                results.append(processed)

            return results

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                f"Native n sampling failed on attempt {attempt + 1}: {exc}",
            )
            last_error = exc

    # All retries exhausted
    if return_exception:
        error_str = str(last_error) if last_error else "Unknown error occurred"
        return [error_str] * num_samples

    raise RuntimeError(
        f"Native n sampling failed after {max_retries + 1} attempts: {last_error}",
    )


def _call_custom_endpoint(
    model: str,
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
    temperature: float,
    max_retries: int,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    **kwargs: Any,
) -> Optional[str | dict | list]:
    """Handle custom API Gateway calls using direct HTTP (no OpenAI SDK).

    This bypasses the OpenAI SDK which adds an Authorization header that
    AWS API Gateway rejects. Instead, we use httpx with only x-api-key header.
    """
    messages = _build_openai_messages(
        system_prompt,
        user_prompt,
        assistant_prompt,
        previous_messages,
    )
    max_tokens = kwargs.pop("max_tokens", None)

    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            result = _call_custom_endpoint_direct(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return _postprocess_response(result, extract_code_flag, return_type)

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                f"Custom endpoint call failed on attempt {attempt + 1}: {exc}",
            )
            last_error = exc

            # Add exponential backoff before retry (especially for 429 rate limit errors)
            if attempt < max_retries:
                # Check if it's a rate limit error (429)
                is_rate_limit = "429" in str(exc)
                # Base delay: 1s for rate limits, 0.5s for other errors
                base_delay = 2.0 if is_rate_limit else 0.5
                # Exponential backoff: 2s, 4s, 8s... for rate limits
                delay = base_delay * (2**attempt)
                logger.info(
                    f"Retrying in {delay:.1f}s (attempt {attempt + 2}/{max_retries + 1})",
                )
                time.sleep(delay)

    # All retries exhausted
    if return_exception:
        return str(last_error) if last_error else "Unknown error occurred"

    raise RuntimeError(
        f"Custom endpoint call failed after {max_retries + 1} attempts: {last_error}",
    )


def _call_sagemaker(
    model: str,
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
    temperature: float,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    **kwargs: Any,
) -> Optional[str | dict | list]:
    """Handle direct SageMaker calls (bypasses API Gateway for longer timeouts)."""
    messages = _build_openai_messages(
        system_prompt,
        user_prompt,
        assistant_prompt,
        previous_messages,
    )
    max_tokens = kwargs.pop("max_tokens", None)

    try:
        result = _call_sagemaker_direct(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        if not isinstance(result, str):
            return result
        return _postprocess_response(result, extract_code_flag, return_type)

    except Exception as exc:
        logger.exception(f"SageMaker direct call failed: {exc}")
        if return_exception:
            return str(exc)
        raise RuntimeError(f"SageMaker direct call failed: {exc}") from exc


def _call_litellm_single(
    model: str,
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
    temperature: float,
    max_retries: int,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    stream: bool,
    stream_handler: Optional[Callable[[str], None]],
    resource_tracker: Optional[ResourceTracker] = None,
    **kwargs: Any,
) -> Optional[str | dict | BaseMessage | list]:
    """Handle a single LiteLLM call with retry logic."""
    # Resolve custom endpoints
    resolved_model, endpoint_kwargs = _resolve_custom_endpoint(model)

    # Merge kwargs (passed kwargs take precedence, with special handling for model_kwargs)
    if "model_kwargs" in endpoint_kwargs and "model_kwargs" in kwargs:
        endpoint_kwargs["model_kwargs"] = {
            **endpoint_kwargs["model_kwargs"],
            **kwargs.pop("model_kwargs"),
        }
    merged_kwargs = {**endpoint_kwargs, **kwargs}

    chat = ChatLiteLLM(model=resolved_model, temperature=temperature, **merged_kwargs)
    messages = _build_langchain_messages(
        system_prompt,
        user_prompt,
        assistant_prompt,
        previous_messages,
    )
    gemini_sanitize_mode = (
        get_gemini_sanitize_mode() if is_gemini_model(resolved_model) else "off"
    )
    gemini_max_edge_px = _get_int_env("MPS_GEMINI_IMAGE_MAX_EDGE_PX", 2048)
    gemini_max_bytes = _get_int_env("MPS_GEMINI_IMAGE_MAX_BYTES", 4_000_000)
    gemini_max_images = _get_int_env("MPS_GEMINI_MAX_IMAGES", 0)
    gemini_drop_on_error = _get_int_env("MPS_GEMINI_DROP_IMAGES_ON_ERROR", 0) > 0
    gemini_sanitized_once = False
    gemini_dropped_once = False

    if gemini_sanitize_mode == "always":
        stats = sanitize_langchain_messages_for_gemini(
            messages,
            max_edge_px=gemini_max_edge_px,
            max_bytes=gemini_max_bytes,
            max_images=gemini_max_images,
            prefer_lossless=True,
            drop_images=False,
        )
        gemini_sanitized_once = True
        if stats.changed_images or stats.dropped_images or stats.resized_images:
            logger.info(
                "Gemini prompt image sanitation applied (changed=%s, dropped=%s, resized=%s).",
                stats.changed_images,
                stats.dropped_images,
                stats.resized_images,
            )

    # Validate streaming constraints
    if stream and return_type != "text":
        raise ValueError("Streaming is only supported for return_type='text'")

    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            if stream:
                content = _handle_streaming(chat, messages, stream_handler)
            else:
                result = _handle_non_streaming(
                    chat,
                    messages,
                    return_type,
                    resource_tracker,
                )
                # For image or full return type, return immediately
                if return_type == "image" or return_type == "full":
                    return result
                content = result if isinstance(result, str) else str(result)

            return _postprocess_response(content, extract_code_flag, return_type)

        except Exception as exc:  # noqa: BLE001
            if (
                gemini_sanitize_mode != "off"
                and looks_like_gemini_image_error(exc)
                and attempt < max_retries
            ):
                if not gemini_sanitized_once:
                    stats = sanitize_langchain_messages_for_gemini(
                        messages,
                        max_edge_px=gemini_max_edge_px,
                        max_bytes=gemini_max_bytes,
                        max_images=gemini_max_images,
                        prefer_lossless=True,
                        drop_images=False,
                    )
                    gemini_sanitized_once = True
                    logger.warning(
                        "Gemini image error; sanitized prompt images and retrying (changed=%s, dropped=%s, resized=%s).",
                        stats.changed_images,
                        stats.dropped_images,
                        stats.resized_images,
                    )
                    continue
                if gemini_drop_on_error and not gemini_dropped_once:
                    stats = sanitize_langchain_messages_for_gemini(
                        messages,
                        max_edge_px=gemini_max_edge_px,
                        max_bytes=gemini_max_bytes,
                        max_images=gemini_max_images,
                        prefer_lossless=True,
                        drop_images=True,
                    )
                    gemini_dropped_once = True
                    logger.warning(
                        "Gemini image error persists; dropped prompt images and retrying (dropped=%s).",
                        stats.dropped_images,
                    )
                    continue

            _log_exception_redacted(f"LLM call failed on attempt {attempt + 1}", exc)
            last_error = exc

    # All retries exhausted
    if return_exception:
        return str(last_error) if last_error else "Unknown error occurred"

    raise RuntimeError(
        f"LLM call failed after {max_retries + 1} attempts: {last_error}",
    )


def _call_litellm(
    model: str,
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
    temperature: float,
    max_retries: int,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    stream: bool,
    stream_handler: Optional[Callable[[str], None]],
    num_samples: int = 1,
    resource_tracker: Optional[ResourceTracker] = None,
    **kwargs: Any,
) -> Optional[str | dict | BaseMessage | list]:
    """Handle LiteLLM calls with retry logic and optional multiple sampling.

    Args:
        num_samples: Number of independent responses to generate (default: 1).
            When > 1, uses native n parameter for OpenAI models, or makes
            parallel calls for other providers.
    """
    # Validate constraints for multiple samples
    if num_samples > 1:
        if stream:
            raise ValueError("Streaming is not supported with num_samples > 1")
        if return_type == "full":
            raise ValueError("return_type='full' is not supported with num_samples > 1")

    # Single sample - use existing logic
    if num_samples == 1:
        return _call_litellm_single(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_prompt=assistant_prompt,
            previous_messages=previous_messages,
            temperature=temperature,
            max_retries=max_retries,
            extract_code_flag=extract_code_flag,
            return_type=return_type,
            return_exception=return_exception,
            stream=stream,
            stream_handler=stream_handler,
            resource_tracker=resource_tracker,
            **kwargs,
        )

    # Multiple samples - check if native n is supported
    resolved_model, endpoint_kwargs = _resolve_custom_endpoint(model)

    # Merge kwargs for native n call
    if "model_kwargs" in endpoint_kwargs and "model_kwargs" in kwargs:
        endpoint_kwargs["model_kwargs"] = {
            **endpoint_kwargs["model_kwargs"],
            **kwargs.pop("model_kwargs"),
        }
    merged_kwargs = {**endpoint_kwargs, **kwargs}

    if _supports_native_n(resolved_model):
        # Use native n parameter (single API call, more efficient)
        logger.debug(
            f"Using native n={num_samples} sampling for model {resolved_model}",
        )
        messages = _build_openai_messages(
            system_prompt,
            user_prompt,
            assistant_prompt,
            previous_messages,
        )
        return _call_litellm_native_n(  # type: ignore
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            num_samples=num_samples,
            max_retries=max_retries,
            extract_code_flag=extract_code_flag,
            return_type=return_type,
            return_exception=return_exception,
            resource_tracker=resource_tracker,
            **merged_kwargs,
        )

    # Fall back to parallel calls for providers that don't support n
    logger.debug(
        f"Using parallel calls for n={num_samples} sampling (model {resolved_model} doesn't support native n)",
    )
    results: list[Optional[str | dict | BaseMessage | list]] = [None] * num_samples

    def make_single_call(
        idx: int,
    ) -> tuple[int, Optional[str | dict | BaseMessage | list]]:
        result = _call_litellm_single(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_prompt=assistant_prompt,
            previous_messages=previous_messages,
            temperature=temperature,
            max_retries=max_retries,
            extract_code_flag=extract_code_flag,
            return_type=return_type,
            return_exception=return_exception,
            stream=False,
            stream_handler=None,
            resource_tracker=resource_tracker,
            **kwargs,
        )
        return idx, result

    with ThreadPoolExecutor(max_workers=min(num_samples, 10)) as executor:
        futures = [executor.submit(make_single_call, i) for i in range(num_samples)]

        for future in as_completed(futures):
            try:
                idx, result = future.result()
                results[idx] = result
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"Sample call failed: {exc}")
                if not return_exception:
                    raise

    return results


def call_llm(
    *,
    model: str,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str | list[dict]] = None,
    assistant_prompt: Optional[str | list[dict]] = None,
    previous_messages: Optional[list[Any]] = None,
    temperature: float = 0.2,
    max_retries: int = 2,
    extract_code: bool = False,
    return_type: Literal["text", "json", "image", "full"] = "text",
    return_exception: bool = False,
    stream: bool = False,
    stream_handler: Optional[Callable[[str], None]] = None,
    num_samples: int = 1,
    resource_tracker: Optional[ResourceTracker] = None,
    **kwargs: Any,
) -> Optional[str | dict | BaseMessage | list[str | dict | BaseMessage | None]]:
    """Invoke ChatLiteLLM synchronously.

    Args:
        model: The model name. Supports:
            - Standard LiteLLM models: "gemini/gemini-2.5-pro", "gpt-5", "anthropic/claude-sonnet-4-5-20250929"
            - Custom endpoints via API Gateway: "custom/<endpoint-name>" (e.g., "custom/qwen3-vl-8b")
              Uses API Gateway (29s timeout limit). Good for quick requests.
            - Direct SageMaker endpoints: "sagemaker/<endpoint-name>" (e.g., "sagemaker/qwen3-vl-8b")
              Bypasses API Gateway for longer timeouts (5min+). Use for large/complex requests.
              Custom endpoints are configured in custom_endpoints.yaml.
        system_prompt: Optional system prompt
        user_prompt: Optional user prompt (string or list of dicts for multimodal)
        assistant_prompt: Optional assistant prompt
        previous_messages: Optional list of previous messages
        temperature: Sampling temperature (default: 0.2)
        max_retries: Maximum number of retry attempts (default: 2)
        extract_code: Whether to extract code blocks from response (default: False)
        return_type: Return type - "text", "json", "image", or "full" (default: "text"). Full for returning the full response object.
        return_exception: If True, return exception string instead of raising (default: False)
        stream: Whether to stream the response (default: False)
        stream_handler: Optional callback function for streaming chunks
        num_samples: Number of independent responses to generate (default: 1).
            When > 1, makes parallel API calls and returns a list of responses.
            Not supported with streaming or return_type='full'.
        **kwargs: Additional arguments to pass to ChatLiteLLM

    Returns:
        - When num_samples=1: Response content as string, dict (for JSON), BaseMessage (for full), or None
        - When num_samples>1: List of response contents

    Example:
        # Using a custom endpoint (configs auto-injected from custom_endpoints.yaml)
        response = call_llm(
            model="custom/qwen3-vl-8b",
            user_prompt=[
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            ],
        )

        # For longer requests, use direct SageMaker (bypasses API Gateway 29s limit):
        response = call_llm(
            model="sagemaker/qwen3-vl-8b",  # Note: "sagemaker/" prefix
            user_prompt="Analyze this complex image in detail...",
        )

        # Sample multiple responses (for best-of-n or diversity):
        responses = call_llm(
            model="gemini/gemini-2.5-pro",
            user_prompt="Write a creative story about a robot.",
            temperature=0.8,
            num_samples=5,
        )
        # responses is a list of 5 different completions
    """
    if model.startswith("sagemaker/"):
        if num_samples > 1:
            raise ValueError("num_samples > 1 is not supported for SageMaker endpoints")
        return _call_sagemaker(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_prompt=assistant_prompt,
            previous_messages=previous_messages,
            temperature=temperature,
            extract_code_flag=extract_code,
            return_type=return_type,
            return_exception=return_exception,
            **kwargs,
        )

    # Custom API Gateway endpoints use direct HTTP calls to avoid OpenAI SDK's
    # Authorization header which AWS API Gateway rejects.
    if model.startswith("custom/"):
        # if num_samples > 1:
        #     raise ValueError("num_samples > 1 is not supported for custom endpoints")
        if stream:
            raise ValueError("Streaming is not supported for custom endpoints")
        return _call_custom_endpoint(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_prompt=assistant_prompt,
            previous_messages=previous_messages,
            temperature=temperature,
            max_retries=max_retries,
            extract_code_flag=extract_code,
            return_type=return_type,
            return_exception=return_exception,
            n=num_samples,
            **kwargs,
        )

    return _call_litellm(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        assistant_prompt=assistant_prompt,
        previous_messages=previous_messages,
        temperature=temperature,
        max_retries=max_retries,
        extract_code_flag=extract_code,
        return_type=return_type,
        return_exception=return_exception,
        stream=stream,
        stream_handler=stream_handler,
        num_samples=num_samples,
        resource_tracker=resource_tracker,
        **kwargs,
    )


# ============================================================================
# ASYNC VERSIONS
# ============================================================================


async def _call_custom_endpoint_async(
    model: str,
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
    temperature: float,
    max_retries: int,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    **kwargs: Any,
) -> Optional[str | dict | list]:
    """Handle custom API Gateway calls using async HTTP (no OpenAI SDK).

    This is the async version of _call_custom_endpoint. It bypasses the
    OpenAI SDK which adds an Authorization header that AWS API Gateway rejects.
    Instead, we use httpx AsyncClient with only x-api-key header.
    """
    messages = _build_openai_messages(
        system_prompt,
        user_prompt,
        assistant_prompt,
        previous_messages,
    )
    max_tokens = kwargs.pop("max_tokens", None)

    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            async with _llm_concurrency_guard():
                result = await _call_custom_endpoint_direct_async(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            return _postprocess_response(result, extract_code_flag, return_type)

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                f"Async custom endpoint call failed on attempt {attempt + 1}: {exc}",
            )
            last_error = exc

            # Add exponential backoff before retry (especially for 429 rate limit errors)
            if attempt < max_retries:
                # Check if it's a rate limit error (429)
                is_rate_limit = "429" in str(exc)
                # Base delay: 2s for rate limits, 0.5s for other errors
                base_delay = 2.0 if is_rate_limit else 0.5
                # Exponential backoff: 2s, 4s, 8s... for rate limits
                delay = base_delay * (2**attempt)
                logger.info(
                    f"Retrying in {delay:.1f}s (attempt {attempt + 2}/{max_retries + 1})",
                )
                await asyncio.sleep(delay)

    # All retries exhausted
    if return_exception:
        return str(last_error) if last_error else "Unknown error occurred"

    raise RuntimeError(
        f"Async custom endpoint call failed after {max_retries + 1} attempts: {last_error}",
    )


async def _call_litellm_single_async(
    model: str,
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
    temperature: float,
    max_retries: int,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    **kwargs: Any,
) -> Optional[str | dict | BaseMessage | list]:
    """Handle a single async LiteLLM call with retry logic."""
    # Resolve custom endpoints
    resolved_model, endpoint_kwargs = _resolve_custom_endpoint(model)

    # Merge kwargs (passed kwargs take precedence, with special handling for model_kwargs)
    if "model_kwargs" in endpoint_kwargs and "model_kwargs" in kwargs:
        endpoint_kwargs["model_kwargs"] = {
            **endpoint_kwargs["model_kwargs"],
            **kwargs.pop("model_kwargs"),
        }
    merged_kwargs = {**endpoint_kwargs, **kwargs}

    messages = _build_openai_messages(
        system_prompt,
        user_prompt,
        assistant_prompt,
        previous_messages,
    )
    gemini_sanitize_mode = (
        get_gemini_sanitize_mode() if is_gemini_model(resolved_model) else "off"
    )
    gemini_max_edge_px = _get_int_env("MPS_GEMINI_IMAGE_MAX_EDGE_PX", 2048)
    gemini_max_bytes = _get_int_env("MPS_GEMINI_IMAGE_MAX_BYTES", 4_000_000)
    gemini_max_images = _get_int_env("MPS_GEMINI_MAX_IMAGES", 0)
    gemini_drop_on_error = _get_int_env("MPS_GEMINI_DROP_IMAGES_ON_ERROR", 0) > 0
    gemini_sanitized_once = False
    gemini_dropped_once = False

    if gemini_sanitize_mode == "always":
        stats = sanitize_openai_messages_for_gemini(
            messages,
            max_edge_px=gemini_max_edge_px,
            max_bytes=gemini_max_bytes,
            max_images=gemini_max_images,
            prefer_lossless=True,
            drop_images=False,
        )
        gemini_sanitized_once = True
        if stats.changed_images or stats.dropped_images or stats.resized_images:
            logger.info(
                "Gemini prompt image sanitation applied (changed=%s, dropped=%s, resized=%s).",
                stats.changed_images,
                stats.dropped_images,
                stats.resized_images,
            )

    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            # Use litellm.acompletion for async calls
            async with _llm_concurrency_guard():
                response = await litellm.acompletion(
                    model=resolved_model,
                    messages=messages,
                    temperature=temperature,
                    **merged_kwargs,
                )

            content = response.choices[0].message.content or ""  # type: ignore

            # For image or full return type
            if return_type == "image":
                return content
            if return_type == "full":
                return response  # type: ignore

            return _postprocess_response(content, extract_code_flag, return_type)

        except Exception as exc:  # noqa: BLE001
            if (
                gemini_sanitize_mode != "off"
                and looks_like_gemini_image_error(exc)
                and attempt < max_retries
            ):
                if not gemini_sanitized_once:
                    stats = sanitize_openai_messages_for_gemini(
                        messages,
                        max_edge_px=gemini_max_edge_px,
                        max_bytes=gemini_max_bytes,
                        max_images=gemini_max_images,
                        prefer_lossless=True,
                        drop_images=False,
                    )
                    gemini_sanitized_once = True
                    logger.warning(
                        "Gemini image error; sanitized prompt images and retrying (changed=%s, dropped=%s, resized=%s).",
                        stats.changed_images,
                        stats.dropped_images,
                        stats.resized_images,
                    )
                    continue
                if gemini_drop_on_error and not gemini_dropped_once:
                    stats = sanitize_openai_messages_for_gemini(
                        messages,
                        max_edge_px=gemini_max_edge_px,
                        max_bytes=gemini_max_bytes,
                        max_images=gemini_max_images,
                        prefer_lossless=True,
                        drop_images=True,
                    )
                    gemini_dropped_once = True
                    logger.warning(
                        "Gemini image error persists; dropped prompt images and retrying (dropped=%s).",
                        stats.dropped_images,
                    )
                    continue

            _log_exception_redacted(
                f"Async LLM call failed on attempt {attempt + 1}",
                exc,
            )
            last_error = exc

    # All retries exhausted
    if return_exception:
        return str(last_error) if last_error else "Unknown error occurred"

    raise RuntimeError(
        f"Async LLM call failed after {max_retries + 1} attempts: {last_error}",
    )


async def _call_litellm_native_n_async(
    model: str,
    messages: list[dict],
    temperature: float,
    num_samples: int,
    max_retries: int,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    **kwargs: Any,
) -> list[Optional[str | dict | list]]:
    """Call LiteLLM asynchronously with native n parameter for multiple completions.

    This is the async version of _call_litellm_native_n. For models that support
    the native `n` parameter (like OpenAI), this makes a single API call that
    returns multiple completions, which is more efficient than making parallel calls.

    Args:
        model: The resolved model name
        messages: OpenAI-format messages
        temperature: Sampling temperature
        num_samples: Number of completions to generate
        max_retries: Maximum retry attempts
        extract_code_flag: Whether to extract code blocks
        return_type: Return type for post-processing
        return_exception: Whether to return exceptions as strings
        **kwargs: Additional arguments for litellm

    Returns:
        List of response contents
    """
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            async with _llm_concurrency_guard():
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    n=num_samples,
                    **kwargs,
                )

            # Extract content from all choices
            results: list[Optional[str | dict | list]] = []
            for choice in response.choices:  # type: ignore
                content = choice.message.content or ""  # type: ignore
                processed = _postprocess_response(
                    content,
                    extract_code_flag,
                    return_type,
                )
                results.append(processed)

            return results

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                f"Async native n sampling failed on attempt {attempt + 1}: {exc}",
            )
            last_error = exc

    # All retries exhausted
    if return_exception:
        error_str = str(last_error) if last_error else "Unknown error occurred"
        return [error_str] * num_samples

    raise RuntimeError(
        f"Async native n sampling failed after {max_retries + 1} attempts: {last_error}",
    )


async def _call_litellm_async(
    model: str,
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
    temperature: float,
    max_retries: int,
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
    return_exception: bool,
    num_samples: int = 1,
    **kwargs: Any,
) -> Optional[str | dict | BaseMessage | list]:
    """Handle async LiteLLM calls with optional multiple sampling.

    Args:
        num_samples: Number of independent responses to generate (default: 1).
            When > 1, uses native n parameter for OpenAI models, or falls back
            to asyncio.gather for parallel concurrent calls for other providers.
    """
    # Validate constraints for multiple samples
    if num_samples > 1:
        if return_type == "full":
            raise ValueError("return_type='full' is not supported with num_samples > 1")

    # Single sample - direct call
    if num_samples == 1:
        return await _call_litellm_single_async(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_prompt=assistant_prompt,
            previous_messages=previous_messages,
            temperature=temperature,
            max_retries=max_retries,
            extract_code_flag=extract_code_flag,
            return_type=return_type,
            return_exception=return_exception,
            **kwargs,
        )

    # Multiple samples - check if native n is supported
    resolved_model, endpoint_kwargs = _resolve_custom_endpoint(model)

    # Merge kwargs for native n call
    if "model_kwargs" in endpoint_kwargs and "model_kwargs" in kwargs:
        endpoint_kwargs["model_kwargs"] = {
            **endpoint_kwargs["model_kwargs"],
            **kwargs.pop("model_kwargs"),
        }
    merged_kwargs = {**endpoint_kwargs, **kwargs}

    if _supports_native_n(resolved_model):
        # Use native n parameter (single API call, more efficient)
        logger.debug(
            f"Using async native n={num_samples} sampling for model {resolved_model}",
        )
        messages = _build_openai_messages(
            system_prompt,
            user_prompt,
            assistant_prompt,
            previous_messages,
        )
        return await _call_litellm_native_n_async(  # type: ignore
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            num_samples=num_samples,
            max_retries=max_retries,
            extract_code_flag=extract_code_flag,
            return_type=return_type,
            return_exception=return_exception,
            **merged_kwargs,
        )

    # Fall back to parallel async calls for providers that don't support n
    logger.debug(
        f"Using asyncio.gather for n={num_samples} parallel async calls "
        f"(model {resolved_model} doesn't support native n)",
    )

    async def make_single_call(
        idx: int,
    ) -> tuple[int, Optional[str | dict | BaseMessage | list]]:
        result = await _call_litellm_single_async(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_prompt=assistant_prompt,
            previous_messages=previous_messages,
            temperature=temperature,
            max_retries=max_retries,
            extract_code_flag=extract_code_flag,
            return_type=return_type,
            return_exception=return_exception,
            **kwargs,
        )
        return idx, result

    # Create tasks for all samples
    tasks = [make_single_call(i) for i in range(num_samples)]

    # Execute all tasks concurrently
    results_with_idx = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results, maintaining order
    results: list[Optional[str | dict | BaseMessage | list]] = [None] * num_samples
    for item in results_with_idx:
        if isinstance(item, Exception):
            logger.exception(f"Async sample call failed: {item}")
            if not return_exception:
                raise item
            # If return_exception, we'll leave None in results
        else:
            idx, result = item  # type: ignore
            results[idx] = result

    return results


async def call_llm_async(
    *,
    model: str,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str | list[dict]] = None,
    assistant_prompt: Optional[str | list[dict]] = None,
    previous_messages: Optional[list[Any]] = None,
    temperature: float = 0.2,
    max_retries: int = 2,
    extract_code: bool = False,
    return_type: Literal["text", "json", "image", "full"] = "text",
    return_exception: bool = False,
    num_samples: int = 1,
    **kwargs: Any,
) -> Optional[str | dict | BaseMessage | list[str | dict | BaseMessage | None]]:
    """Invoke ChatLiteLLM asynchronously.

    This is the async version of call_llm(). It uses litellm.acompletion() for
    non-blocking LLM calls and asyncio.gather() for parallel multi-sample requests.

    Args:
        model: The model name. Supports:
            - Standard LiteLLM models: "gemini/gemini-2.5-pro", "gpt-5", etc.
            - Custom endpoints via API Gateway: "custom/<endpoint-name>" (e.g., "custom/qwen3-vl-8b")
              Uses async HTTP calls to API Gateway. Custom endpoints are configured in custom_endpoints.yaml.
        system_prompt: Optional system prompt
        user_prompt: Optional user prompt (string or list of dicts for multimodal)
        assistant_prompt: Optional assistant prompt
        previous_messages: Optional list of previous messages
        temperature: Sampling temperature (default: 0.2)
        max_retries: Maximum number of retry attempts (default: 2)
        extract_code: Whether to extract code blocks from response (default: False)
        return_type: Return type - "text", "json", "image", or "full" (default: "text")
        return_exception: If True, return exception string instead of raising (default: False)
        num_samples: Number of independent responses to generate (default: 1).
            When > 1, uses asyncio.gather for parallel concurrent calls.
        **kwargs: Additional arguments to pass to litellm.acompletion

    Returns:
        - When num_samples=1: Response content as string, dict, BaseMessage, or None
        - When num_samples>1: List of response contents

    Example:
        # Single async call
        response = await call_llm_async(
            model="gemini/gemini-2.5-pro",
            user_prompt="What is 2+2?",
        )

        # Multiple parallel async calls
        responses = await call_llm_async(
            model="gemini/gemini-2.5-pro",
            user_prompt="Write a creative story.",
            temperature=0.8,
            num_samples=5,
        )
        # responses is a list of 5 different completions, all fetched concurrently
    """
    # Note: SageMaker direct calls don't have async support yet
    if model.startswith("sagemaker/"):
        raise ValueError(
            "Async calls are not supported for SageMaker endpoints. "
            "Use call_llm() instead or wrap with asyncio.to_thread().",
        )

    # Custom API Gateway endpoints use async HTTP calls to avoid OpenAI SDK's
    # Authorization header which AWS API Gateway rejects.
    if model.startswith("custom/"):
        # if num_samples > 1:
        #     raise ValueError("num_samples > 1 is not supported for custom endpoints")
        return await _call_custom_endpoint_async(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_prompt=assistant_prompt,
            previous_messages=previous_messages,
            temperature=temperature,
            max_retries=max_retries,
            extract_code_flag=extract_code,
            return_type=return_type,
            return_exception=return_exception,
            n=num_samples,
            **kwargs,
        )

    return await _call_litellm_async(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        assistant_prompt=assistant_prompt,
        previous_messages=previous_messages,
        temperature=temperature,
        max_retries=max_retries,
        extract_code_flag=extract_code,
        return_type=return_type,
        return_exception=return_exception,
        num_samples=num_samples,
        **kwargs,
    )


def main():
    """Test cases for ``call_llm`` function."""
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv("../../.env")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 80)
    print("Testing ``call_llm`` function")
    print("=" * 80)

    # Test 1: Basic text response
    print("-" * 80)
    print("Test 1: Basic text response")
    print("-" * 80)
    try:
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            user_prompt="What is 2+2? Respond with just the number.",
            temperature=0.1,
        )
        print(f"Response: {response}")
        assert response is not None, "Response should not be None"
        print("✓ Test 1 passed")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")

    # Test 2: System and user prompts
    print("-" * 80)
    print("Test 2: System and user prompts")
    print("-" * 80)
    try:
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            system_prompt="You are a helpful assistant that responds concisely.",
            user_prompt="What is Python?",
            temperature=0.1,
        )
        print(f"Response: {response}")
        assert response is not None, "Response should not be None"
        assert len(str(response)) > 0, "Response should not be empty"
        print("✓ Test 2 passed")
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")

    # Test 3: Previous messages (dict format)
    print("-" * 80)
    print("Test 3: Previous messages (dict format)")
    print("-" * 80)
    try:
        previous_messages = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Hello Alice! How can I help you?"},
        ]
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            user_prompt="What's my name?",
            previous_messages=previous_messages,
            temperature=0.1,
        )
        print(f"Response: {response}")
        assert response is not None, "Response should not be None"
        print("✓ Test 3 passed")
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")

    # Test 4: Previous messages (LangChain message objects)
    print("-" * 80)
    print("Test 4: Previous messages (LangChain message objects)")
    print("-" * 80)
    try:
        previous_messages = [
            HumanMessage(content="Count from 1 to 3."),
            AIMessage(content="1, 2, 3"),
        ]
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            user_prompt="Now count from 4 to 6.",
            previous_messages=previous_messages,
            temperature=0.1,
        )
        print(f"Response: {response}")
        assert response is not None, "Response should not be None"
        print("✓ Test 4 passed")
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")

    # Test 5: JSON return type
    print("-" * 80)
    print("Test 5: JSON return type")
    print("-" * 80)
    try:
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            system_prompt="You are a helpful assistant. Always respond with valid JSON.",
            user_prompt='Return a JSON object with keys "name" and "age" with example values.',
            return_type="json",
            temperature=0.1,
        )
        print(f"Response: {response}")
        assert isinstance(response, dict), "Response should be a dict"
        print("✓ Test 5 passed")
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")

    # Test 6: Code extraction
    print("-" * 80)
    print("Test 6: Code extraction")
    print("-" * 80)
    try:
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            user_prompt="Write a Python function that adds two numbers. Return it in a code block.",
            extract_code=True,
            temperature=0.1,
        )
        print(f"Extracted code: {response}")
        assert response is not None, "Response should not be None"
        assert (
            "def" in str(response) or "add" in str(response).lower()
        ), "Should contain code"
        print("✓ Test 6 passed")
    except Exception as e:
        print(f"✗ Test 6 failed: {e}")

    # Test 7: Streaming
    print("-" * 80)
    print("Test 7: Streaming")
    print("-" * 80)
    try:
        chunks_received = []

        def stream_handler(chunk: str):
            chunks_received.append(chunk)
            print(chunk, end="", flush=True)

        response = call_llm(
            model="gemini/gemini-2.5-pro",
            user_prompt="Count from 1 to 5, one number per line.",
            stream=True,
            stream_handler=stream_handler,
            temperature=0.1,
        )
        print(f"\nTotal chunks received: {len(chunks_received)}")
        print(f"Full response: {response}")
        assert response is not None, "Response should not be None"
        assert len(chunks_received) > 0, "Should have received chunks"
        print("\n✓ Test 7 passed")
    except Exception as e:
        print(f"✗ Test 7 failed: {e}")

    # Test 8: Temperature parameter
    print("-" * 80)
    print("Test 8: Temperature parameter")
    print("-" * 80)
    try:
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            user_prompt="Say 'test' in one word.",
            temperature=0.0,
        )
        print(f"Response: {response}")
        assert response is not None, "Response should not be None"
        print("✓ Test 8 passed")
    except Exception as e:
        print(f"✗ Test 8 failed: {e}")

    # Test 9: System prompt update (when previous messages exist)
    print("-" * 80)
    print("Test 9: System prompt update")
    print("-" * 80)
    try:
        previous_messages = [SystemMessage(content="Initial system message")]
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            system_prompt="You are a math tutor.",
            user_prompt="What is 5*5?",
            previous_messages=previous_messages,
            temperature=0.1,
        )
        print(f"Response: {response}")
        assert response is not None, "Response should not be None"
        print("✓ Test 9 passed")
    except Exception as e:
        print(f"✗ Test 9 failed: {e}")

    # Test 10: Assistant prompt (few-shot example)
    print("-" * 80)
    print("Test 10: Assistant prompt (few-shot example)")
    print("-" * 80)
    try:
        response = call_llm(
            model="gemini/gemini-2.5-pro",
            user_prompt="Translate 'hello' to Spanish",
            assistant_prompt="hola",
            temperature=0.1,
        )
        print(f"Response: {response}")
        assert response is not None, "Response should not be None"
        print("✓ Test 10 passed")
    except Exception as e:
        print(f"✗ Test 10 failed: {e}")

    # Test 11: Error handling with return_exception
    print("=" * 80)
    print("Test 11: Error handling with return_exception")
    print("=" * 80)
    try:
        # Use an invalid model to trigger an error
        response = call_llm(
            model="invalid-model-name-12345",
            user_prompt="Test",
            max_retries=1,
            return_exception=True,
        )
        print(f"Exception returned: {response}")
        assert response is not None, "Exception string should be returned"
        assert isinstance(response, str), "Exception should be a string"
        print("✓ Test 11 passed")
    except Exception as e:
        print(f"✗ Test 11 failed: {e}")

    # Test 12: extract_code_block function
    print("=" * 80)
    print("Test 12: extract_code_block function")
    print("=" * 80)
    try:
        test_text = """
Here is some code:
```python
def hello():
    print("Hello, World!")
```
That's the code.
"""
        extracted = extract_code_block(test_text)
        print(f"Extracted: {extracted}")
        assert "def hello" in extracted, "Should extract the function"
        assert "```" not in extracted, "Should not contain markdown markers"
        print("✓ Test 12 passed")
    except Exception as e:
        print(f"✗ Test 12 failed: {e}")

    print("=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
