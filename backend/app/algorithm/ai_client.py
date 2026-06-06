"""
AI客户端

支持企业级Key池轮询、并发控制、自动切换和限流重试。
"""

import asyncio
import json
import random
from typing import Any
from openai import OpenAI
from app.algorithm.key_manager import key_manager


def pick_model(api_model: str) -> str:
    """从模型池中随机选择一个模型"""
    models = [m.strip() for m in api_model.split(",") if m.strip()]
    return random.choice(models) if models else "deepseek-chat"


async def chat_completion(
    system_prompt: str = "",
    user_prompt: str = "",
    temperature: float = 0.3,
    response_format: type = str,
    max_retries: int = 3,
) -> Any:
    """带自动Key切换的AI调用

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        temperature: 温度参数
        response_format: 返回格式（str 或 dict）
        max_retries: 最大重试次数

    Returns:
        AI返回的内容

    Raises:
        RuntimeError: 所有Key都不可用时抛出
    """
    last_error = None

    for attempt in range(max_retries):
        # 获取并发许可
        await key_manager.acquire()
        key_config = None
        try:
            # 获取可用Key
            key_config = await key_manager.get_key_for_request()

            client = OpenAI(
                api_key=key_config["api_key"],
                base_url=key_config["api_base_url"]
            )

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            kwargs = {
                "model": pick_model(key_config["api_model"]),
                "messages": messages,
                "temperature": temperature,
            }
            if response_format == dict:
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content

            # 记录使用次数
            if key_config["id"]:
                key_manager.record_usage(key_config["id"])

            if response_format == dict:
                return json.loads(content)
            return content

        except Exception as e:
            last_error = e
            error_msg = str(e).lower()

            if key_config and key_config.get("id"):
                if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg or "invalid" in error_msg:
                    # Key无效，禁用并重试
                    key_manager.mark_key_failed(key_config["id"], "401")
                    continue
                elif "429" in error_msg or "rate" in error_msg or "too many" in error_msg:
                    # 限流，标记并重试其他Key
                    key_manager.mark_key_failed(key_config["id"], "429")
                    await asyncio.sleep(1)
                    continue
                elif "insufficient_quota" in error_msg or "exceeded" in error_msg:
                    # 额度不足，禁用
                    key_manager.mark_key_failed(key_config["id"], "403")
                    continue

            # 其他错误，等待后重试
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            raise

        finally:
            key_manager.release()

    raise RuntimeError(f"AI调用失败: {last_error}")
