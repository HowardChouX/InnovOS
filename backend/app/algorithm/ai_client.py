import os
import json
from typing import Any

CLIENT: Any = None


def get_ai_client():
    global CLIENT
    if CLIENT is not None:
        return CLIENT

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        CLIENT = None
        return None

    try:
        from openai import OpenAI

        base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        CLIENT = OpenAI(api_key=api_key, base_url=base_url)
        return CLIENT
    except ImportError:
        CLIENT = None
        return None


def ai_available() -> bool:
    return get_ai_client() is not None


async def chat_completion(
    model: str = "deepseek-chat",
    system_prompt: str = "",
    user_prompt: str = "",
    temperature: float = 0.3,
    response_format: type = str,
) -> Any:
    client = get_ai_client()
    if not client:
        raise RuntimeError("AI client not configured. Set DEEPSEEK_API_KEY or OPENAI_API_KEY")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format == dict:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content

    if response_format == dict:
        return json.loads(content)
    return content
