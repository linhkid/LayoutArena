"""Minimal LLM wrapper using litellm directly."""

import re

import litellm


def call_llm(*, model: str, system_prompt: str, user_prompt: str | list, temperature: float = 0.7, extract_code: bool = False) -> str:
    """Call LLM. user_prompt can be a string or a list of content parts (text/image_url dicts) for multimodal."""
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    text = response.choices[0].message.content or ""
    if extract_code:
        match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        return match.group(1).strip() if match else text.strip()
    return text
