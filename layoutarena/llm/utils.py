from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Union

import httpx
import yaml
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_litellm import ChatLiteLLM

from layoutarena.llm.schema import MessageContent, OpenAIMessage
from layoutarena.llm.tracker import ResourceTracker

# Default timeout for SageMaker async polling (seconds)
DEFAULT_SAGEMAKER_TIMEOUT = 300
DEFAULT_POLL_INTERVAL = 5

# Cache for custom endpoint configs
_custom_endpoints_cache: Optional[dict] = None

# Providers that support native n parameter for multiple completions
_NATIVE_N_PROVIDERS = frozenset(
    {
        "openai",
        "azure",
        "azure_ai",
        "openai_compatible",
        "custom_openai",
        "text-completion-openai",
        "gpt-3.5-turbo",
        "gpt-4",
        "gpt-4o",
        "o1",
        "o3",
    },
)

logger = logging.getLogger(__name__)


def _supports_native_n(model: str) -> bool:
    """Check if a model supports native n parameter for multiple completions.

    Args:
        model: The model name (e.g., "gpt-4", "openai/gpt-4", "anthropic/claude-3")

    Returns:
        True if the model supports native n parameter, False otherwise.
    """
    model_lower = model.lower()

    # Check direct model name matches
    for provider in _NATIVE_N_PROVIDERS:
        if model_lower.startswith(provider):
            return True

    # Check if model name contains openai-related patterns
    if any(p in model_lower for p in ["gpt-", "o1-", "o3-", "chatgpt"]):
        return True

    # Custom endpoints might be OpenAI-compatible
    if model.startswith("custom/"):
        # Could be OpenAI-compatible, but we can't be sure
        # Default to parallel calls for safety
        return False

    return False


def _load_custom_endpoints() -> dict:
    """Load custom endpoint configurations from YAML file.

    Returns:
        Dictionary of endpoint configurations, or empty dict if file not found.
    """
    global _custom_endpoints_cache

    if _custom_endpoints_cache is not None:
        return _custom_endpoints_cache

    # Look for config file relative to this module
    config_path = Path(__file__).parent / "custom_endpoints.yaml"

    if not config_path.exists():
        logger.debug(f"Custom endpoints config not found at {config_path}")
        _custom_endpoints_cache = {}
        return _custom_endpoints_cache

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            _custom_endpoints_cache = config.get("endpoints", {})
            logger.debug(
                f"Loaded {len(_custom_endpoints_cache or {})} custom endpoints",
            )
            return _custom_endpoints_cache or {}
    except Exception as e:
        logger.warning(f"Failed to load custom endpoints config: {e}")
        _custom_endpoints_cache = {}
        return _custom_endpoints_cache


def _resolve_custom_endpoint(model: str) -> tuple[str, dict[str, Any]]:
    """Resolve custom endpoint model name to LiteLLM model and kwargs.

    Custom endpoints use the format "custom/<endpoint-name>".
    Example: "custom/qwen3-vl-8b" -> resolves to Qwen3-VL config

    Args:
        model: The model name, possibly with "custom/" prefix

    Returns:
        Tuple of (resolved_model_name, additional_kwargs)
    """
    if not model.startswith("custom/"):
        return model, {}

    endpoint_name = model[7:]  # Remove "custom/" prefix
    endpoints = _load_custom_endpoints()

    if endpoint_name not in endpoints:
        available = ", ".join(endpoints.keys()) if endpoints else "none"
        raise ValueError(
            f"Unknown custom endpoint: '{endpoint_name}'. "
            f"Available endpoints: {available}",
        )

    config = endpoints[endpoint_name]
    resolved_model = config.get("litellm_model", f"openai/{endpoint_name}")

    # Build kwargs for ChatLiteLLM
    extra_kwargs: dict[str, Any] = {}

    if "api_base" in config:
        extra_kwargs["api_base"] = config["api_base"]

    if "api_key" in config:
        # API Gateway uses x-api-key header for authentication, not Bearer token.
        # We must NOT pass the real api_key here because:
        # 1. LiteLLM/OpenAI SDK adds an "Authorization: Bearer <api_key>" header
        # 2. AWS API Gateway rejects this unexpected Authorization header format
        # Instead, we only pass the x-api-key via extra_headers for API Gateway auth.
        # We set api_key to "NA" (minimal dummy) to satisfy the SDK requirement
        # while avoiding issues with empty strings or env var fallbacks.
        extra_kwargs["api_key"] = "NA"
        extra_kwargs["model_kwargs"] = {
            "extra_headers": {"x-api-key": config["api_key"]},
        }

    if "max_tokens_default" in config:
        extra_kwargs["max_tokens"] = config["max_tokens_default"]

    logger.debug(
        f"Resolved custom endpoint '{endpoint_name}' -> {resolved_model} "
        f"with api_base={config.get('api_base', 'default')}",
    )

    return resolved_model, extra_kwargs


def _call_api_gateway_direct(
    api_base: str,
    api_key: str,
    model_id: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.2,
    timeout: float = 180.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call API Gateway endpoint directly using httpx (no OpenAI SDK).

    This bypasses the OpenAI SDK which automatically adds an Authorization
    header that AWS API Gateway rejects. Instead, we only send x-api-key.

    Args:
        api_base: The API Gateway base URL
        api_key: The x-api-key for authentication
        model_id: The model identifier (e.g., "Qwen/Qwen3-VL-4B-Instruct")
        messages: OpenAI-format messages list
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        timeout: Request timeout in seconds (default 180s to match API Gateway limit)
        **kwargs: Additional parameters for the request body

    Returns:
        OpenAI-compatible chat completion response dict
    """
    # Ensure api_base ends with /chat/completions
    url = api_base.rstrip("/")
    if not url.endswith("/chat/completions"):
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        url = f"{url}/chat/completions"

    # Build request payload
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **kwargs,
    }

    # Headers - only x-api-key, NO Authorization header
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }

    logger.debug(f"Calling API Gateway directly: POST {url}")

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def _call_api_gateway_direct_async(
    api_base: str,
    api_key: str,
    model_id: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.2,
    timeout: float = 180.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call API Gateway endpoint directly using httpx async (no OpenAI SDK).

    This is the async version of _call_api_gateway_direct. It bypasses the
    OpenAI SDK which automatically adds an Authorization header that AWS
    API Gateway rejects. Instead, we only send x-api-key.

    Args:
        api_base: The API Gateway base URL
        api_key: The x-api-key for authentication
        model_id: The model identifier (e.g., "Qwen/Qwen3-VL-4B-Instruct")
        messages: OpenAI-format messages list
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        timeout: Request timeout in seconds (default 180s to match API Gateway limit)
        **kwargs: Additional parameters for the request body

    Returns:
        OpenAI-compatible chat completion response dict
    """
    # Ensure api_base ends with /chat/completions
    url = api_base.rstrip("/")
    if not url.endswith("/chat/completions"):
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        url = f"{url}/chat/completions"

    # Build request payload
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **kwargs,
    }

    # Headers - only x-api-key, NO Authorization header
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }

    logger.debug(f"Calling API Gateway directly (async): POST {url}")

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def _call_custom_endpoint_direct(
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    **kwargs: Any,
) -> str | list:
    """Call custom API Gateway endpoint directly and return text response.

    This uses direct HTTP calls to avoid OpenAI SDK's Authorization header
    which AWS API Gateway rejects.

    Args:
        model: Model name with "custom/" prefix (e.g., "custom/qwen3-vl-4b")
        messages: OpenAI-format messages list
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        **kwargs: Additional parameters

    Returns:
        Text content from the response
    """
    endpoint_name = model[7:]  # Remove "custom/" prefix
    endpoints = _load_custom_endpoints()

    if endpoint_name not in endpoints:
        available = ", ".join(endpoints.keys()) if endpoints else "none"
        raise ValueError(
            f"Unknown custom endpoint: '{endpoint_name}'. "
            f"Available endpoints: {available}",
        )

    config = endpoints[endpoint_name]

    if "api_base" not in config or "api_key" not in config:
        raise ValueError(
            f"Endpoint '{endpoint_name}' missing api_base or api_key config.",
        )

    # Get config values
    api_base = config["api_base"]
    api_key = config["api_key"]
    model_id = config.get("litellm_model", "").replace("openai/", "")
    default_max_tokens = config.get("max_tokens_default", 4096)

    logger.info(f"Calling API Gateway directly: {endpoint_name} at {api_base}")

    response = _call_api_gateway_direct(
        api_base=api_base,
        api_key=api_key,
        model_id=model_id,
        messages=messages,
        max_tokens=max_tokens or default_max_tokens,
        temperature=temperature,
        **kwargs,
    )

    # Extract text from OpenAI-format response
    if "choices" in response and len(response["choices"]) > 0:
        # If multiple choices, return list of all contents
        if len(response["choices"]) > 1:
            return [
                choice.get("message", {}).get("content", "")
                for choice in response["choices"]
            ]
        # Single choice, return just the content string
        return response["choices"][0].get("message", {}).get("content", "")

    raise RuntimeError(f"Unexpected response format: {response}")


async def _call_custom_endpoint_direct_async(
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    **kwargs: Any,
) -> str | list:
    """Call custom API Gateway endpoint directly and return text response (async).

    This is the async version of _call_custom_endpoint_direct. It uses
    async HTTP calls to avoid blocking and allows for concurrent requests.

    Args:
        model: Model name with "custom/" prefix (e.g., "custom/qwen3-vl-4b")
        messages: OpenAI-format messages list
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        **kwargs: Additional parameters

    Returns:
        Text content from the response
    """
    endpoint_name = model[7:]  # Remove "custom/" prefix
    endpoints = _load_custom_endpoints()

    if endpoint_name not in endpoints:
        available = ", ".join(endpoints.keys()) if endpoints else "none"
        raise ValueError(
            f"Unknown custom endpoint: '{endpoint_name}'. "
            f"Available endpoints: {available}",
        )

    config = endpoints[endpoint_name]

    if "api_base" not in config or "api_key" not in config:
        raise ValueError(
            f"Endpoint '{endpoint_name}' missing api_base or api_key config.",
        )

    # Get config values
    api_base = config["api_base"]
    api_key = config["api_key"]
    model_id = config.get("litellm_model", "").replace("openai/", "")
    default_max_tokens = config.get("max_tokens_default", 4096)

    logger.info(f"Calling API Gateway directly (async): {endpoint_name} at {api_base}")

    response = await _call_api_gateway_direct_async(
        api_base=api_base,
        api_key=api_key,
        model_id=model_id,
        messages=messages,
        max_tokens=max_tokens or default_max_tokens,
        temperature=temperature,
        **kwargs,
    )

    # Extract text from OpenAI-format response
    if "choices" in response and len(response["choices"]) > 0:
        # If multiple choices, return list of all contents
        if len(response["choices"]) > 1:
            return [
                choice.get("message", {}).get("content", "")
                for choice in response["choices"]
            ]
        # Single choice, return just the content string
        return response["choices"][0].get("message", {}).get("content", "")

    raise RuntimeError(f"Unexpected response format: {response}")


def _invoke_sagemaker_direct(
    endpoint_name: str,
    model_id: str,
    messages: list[dict],
    region: str,
    timeout: int = DEFAULT_SAGEMAKER_TIMEOUT,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    **kwargs: Any,
) -> dict[str, Any]:
    """Invoke SageMaker async endpoint directly (bypassing API Gateway).

    This allows for longer timeouts than API Gateway's 29 second limit.

    Args:
        endpoint_name: SageMaker endpoint name
        model_id: Model ID to pass in the request
        messages: OpenAI-format messages list
        region: AWS region
        timeout: Maximum time to wait for results (seconds)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        **kwargs: Additional parameters for the request

    Returns:
        OpenAI-compatible chat completion response
    """
    import boto3

    sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=region)
    sagemaker_client = boto3.client("sagemaker", region_name=region)
    s3_client = boto3.client("s3", region_name=region)

    # Get async config from endpoint
    endpoint_desc = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
    config_name = endpoint_desc["EndpointConfigName"]
    config_desc = sagemaker_client.describe_endpoint_config(
        EndpointConfigName=config_name,
    )

    if "AsyncInferenceConfig" not in config_desc:
        raise ValueError(
            f"Endpoint {endpoint_name} is not an async endpoint. "
            "Use 'custom/' prefix for real-time endpoints.",
        )

    s3_output = config_desc["AsyncInferenceConfig"]["OutputConfig"]["S3OutputPath"]
    bucket_name = s3_output.replace("s3://", "").split("/")[0]

    # Prepare OpenAI-format request
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **kwargs,
    }

    # Upload input to S3
    request_id = str(uuid.uuid4())
    input_key = f"async-inference-input/{request_id}.json"
    input_s3_uri = f"s3://{bucket_name}/{input_key}"

    logger.debug(f"Uploading request to S3: {input_s3_uri}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=input_key,
        Body=json.dumps(payload),
        ContentType="application/json",
    )

    # Invoke async endpoint
    logger.info(f"Invoking SageMaker async endpoint: {endpoint_name}")
    response = sagemaker_runtime.invoke_endpoint_async(
        EndpointName=endpoint_name,
        InputLocation=input_s3_uri,
        ContentType="application/json",
    )

    output_location = response["OutputLocation"]
    logger.debug(f"Output location: {output_location}")

    # Parse output location for polling
    output_bucket = output_location.split("/")[2]
    output_key = "/".join(output_location.split("/")[3:])

    # Poll for results
    waited = 0
    while waited < timeout:
        # Check for failure
        try:
            failure_obj = s3_client.get_object(
                Bucket=output_bucket,
                Key=output_key + ".failure",
            )
            failure_data = failure_obj["Body"].read().decode("utf-8")
            logger.error(f"SageMaker inference failed: {failure_data}")
            # Cleanup input
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=input_key)
            except Exception:
                pass
            raise RuntimeError(f"SageMaker inference failed: {failure_data}")
        except s3_client.exceptions.NoSuchKey:
            pass  # No failure, continue

        # Check for success
        try:
            result_obj = s3_client.get_object(Bucket=output_bucket, Key=output_key)
            result_data = result_obj["Body"].read().decode("utf-8")

            # Cleanup input
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=input_key)
            except Exception:
                pass

            if not result_data.strip():
                raise RuntimeError("Empty response from SageMaker endpoint")

            return json.loads(result_data)

        except s3_client.exceptions.NoSuchKey:
            # Result not ready yet
            time.sleep(DEFAULT_POLL_INTERVAL)
            waited += DEFAULT_POLL_INTERVAL
            logger.debug(f"Waiting for SageMaker result... ({waited}s/{timeout}s)")

    # Cleanup on timeout
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=input_key)
    except Exception:
        pass

    raise TimeoutError(f"SageMaker inference timed out after {timeout} seconds")


def _call_sagemaker_direct(
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    **kwargs: Any,
) -> str:
    """Call SageMaker endpoint directly and return text response.

    Args:
        model: Model name with "sagemaker/" prefix (e.g., "sagemaker/qwen3-vl-8b")
        messages: OpenAI-format messages list
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        **kwargs: Additional parameters

    Returns:
        Text content from the response
    """
    endpoint_name = model[10:]  # Remove "sagemaker/" prefix
    endpoints = _load_custom_endpoints()

    if endpoint_name not in endpoints:
        available = ", ".join(endpoints.keys()) if endpoints else "none"
        raise ValueError(
            f"Unknown SageMaker endpoint: '{endpoint_name}'. "
            f"Available endpoints: {available}",
        )

    config = endpoints[endpoint_name]

    if "sagemaker_endpoint" not in config:
        raise ValueError(
            f"Endpoint '{endpoint_name}' does not have SageMaker direct config. "
            "Use 'custom/' prefix for API Gateway access.",
        )

    # Get config values
    sm_endpoint = config["sagemaker_endpoint"]
    sm_region = config.get("sagemaker_region", "us-west-2")
    model_id = config.get("litellm_model", "").replace("openai/", "")
    timeout = config.get("timeout", DEFAULT_SAGEMAKER_TIMEOUT)
    default_max_tokens = config.get("max_tokens_default", 4096)

    logger.info(
        f"Calling SageMaker directly: {sm_endpoint} in {sm_region} "
        f"(timeout: {timeout}s)",
    )

    response = _invoke_sagemaker_direct(
        endpoint_name=sm_endpoint,
        model_id=model_id,
        messages=messages,
        region=sm_region,
        timeout=timeout,
        max_tokens=max_tokens or default_max_tokens,
        temperature=temperature,
        **kwargs,
    )

    # Extract text from OpenAI-format response
    if "choices" in response and len(response["choices"]) > 0:
        return response["choices"][0].get("message", {}).get("content", "")

    raise RuntimeError(f"Unexpected response format: {response}")


def extract_code_block(text: str) -> str:
    """Extract code blocks from markdown-formatted text."""
    # Match ```language\ncode\n``` or ```\ncode\n```
    pattern = r"```(?:\w+)?\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return text


def list_custom_endpoints() -> dict[str, str]:
    """List all available custom endpoints.

    Returns:
        Dictionary mapping endpoint names to their descriptions.
    """
    endpoints = _load_custom_endpoints()
    return {
        name: config.get("description", "No description")
        for name, config in endpoints.items()
    }


def _extract_text_from_content(content: Any) -> str:
    """Extract text from multimodal content (list format) or return as string."""
    if isinstance(content, list):
        text_parts = [
            item if isinstance(item, str) else item.get("text", "")
            for item in content
            if isinstance(item, str) or (isinstance(item, dict) and "text" in item)
        ]
        return " ".join(text_parts) if text_parts else str(content)
    return str(content) if not isinstance(content, str) else content


def _build_openai_messages(
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
) -> list[OpenAIMessage]:
    """Build messages in OpenAI format (for SageMaker)."""
    messages: list[OpenAIMessage] = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if previous_messages:
        for msg in previous_messages:
            if isinstance(msg, dict):
                messages.append(msg)
            elif isinstance(msg, SystemMessage):
                messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})

    if user_prompt:
        messages.append({"role": "user", "content": user_prompt})

    if assistant_prompt:
        messages.append({"role": "assistant", "content": assistant_prompt})

    return messages


def _build_langchain_messages(
    system_prompt: Optional[str],
    user_prompt: Optional[MessageContent],
    assistant_prompt: Optional[MessageContent],
    previous_messages: Optional[list[Any]],
) -> list[BaseMessage]:
    """Build messages in LangChain format."""
    messages: list[BaseMessage] = []

    # Handle previous messages first
    if previous_messages:
        for msg in previous_messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    messages.append(SystemMessage(content=content))
                elif role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
            elif isinstance(msg, (SystemMessage, HumanMessage, AIMessage)):
                messages.append(msg)

    # Add/update system prompt
    if system_prompt:
        if messages and isinstance(messages[0], SystemMessage):
            messages[0] = SystemMessage(content=system_prompt)
        else:
            messages.insert(0, SystemMessage(content=system_prompt))

    # Add user prompt
    if user_prompt:
        messages.append(HumanMessage(content=user_prompt))  # type: ignore[arg-type]

    # Add assistant prompt
    if assistant_prompt:
        messages.append(AIMessage(content=assistant_prompt))  # type: ignore[arg-type]

    return messages


def _postprocess_response(
    content: str | list[str],
    extract_code_flag: bool,
    return_type: Literal["text", "json", "image", "full"],
) -> Optional[Union[str, dict, list]]:
    """Post-process the response based on flags and return type."""
    if isinstance(content, list):
        return [
            _postprocess_response(item, extract_code_flag, return_type)
            for item in content
        ]  # type: ignore[return-value]

    if extract_code_flag:
        return extract_code_block(content)

    if return_type == "json":
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        # Strip markdown code blocks and retry
        stripped = re.sub(r"^```(?:json)?\s*\n?", "", content.strip())
        stripped = re.sub(r"\n?```\s*$", "", stripped)
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as e:
            logger.warning(f"Error parsing JSON: {e}")
            return content

    return content.strip()


def _handle_streaming(
    chat: ChatLiteLLM,
    messages: list[BaseMessage],
    stream_handler: Optional[Callable[[str], None]],
) -> str:
    """Handle streaming response from LLM."""
    output_chunks: list[str] = []

    try:
        for chunk in chat.stream(messages):
            chunk_text = _extract_chunk_text(chunk)
            if chunk_text:
                output_chunks.append(chunk_text)
                if stream_handler:
                    try:
                        stream_handler(chunk_text)
                    except Exception as handler_exc:  # noqa: BLE001
                        logger.warning(
                            f"Stream handler raised an exception: {handler_exc}",
                        )
    except Exception as stream_exc:
        logger.warning(
            f"Streaming interrupted after {len(output_chunks)} chunks: {stream_exc}. "
            "Returning partial results.",
        )
        if not output_chunks:
            raise

    return "".join(output_chunks)


def _extract_chunk_text(chunk: Any) -> str:
    """Extract text from a streaming chunk."""
    if hasattr(chunk, "content"):
        return _extract_text_from_content(chunk.content)
    if isinstance(chunk, str):
        return chunk
    return str(chunk)


def _handle_non_streaming(
    chat: ChatLiteLLM,
    messages: list[BaseMessage],
    return_type: Literal["text", "json", "image", "full"],
    resource_tracker: Optional[ResourceTracker] = None,
) -> Optional[Union[str, dict, BaseMessage]]:
    """Handle non-streaming response from LLM."""
    response = chat.invoke(messages)
    if resource_tracker:
        resource_tracker.update_usage(response, chat.model)
    if return_type == "full":
        return response
    content = response.content if hasattr(response, "content") else str(response)
    content = _extract_text_from_content(content)

    if return_type == "image":
        return _extract_image_from_response(response)

    return content


def _extract_image_from_response(response: Any) -> Optional[str]:
    """Extract image URL from response metadata."""
    if hasattr(response, "response_metadata"):
        images = getattr(response.response_metadata, "images", [])
        if images:
            return images[0].get("url") if isinstance(images[0], dict) else images[0]
    return None
