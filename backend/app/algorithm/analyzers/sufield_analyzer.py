"""
物-场分析器 — 从 RootSeek 迁移
"""
import logging
from typing import Any

from app.algorithm.base import AIAnalyzer, AIBase

logger = logging.getLogger(__name__)

SUFIELD_SYSTEM_PROMPT = """你是一个TRIZ物质-场分析专家。从问题中识别物质-场模型。

【物质-场模型基础】
- S1（工具）：主动发出作用的物体
- S2（对象）：被动承受作用的物体
- F（场）：能量传递媒介（机械场/热场/电场/磁场/化学场等）

【问题类型】
- measurement：测量/检测类问题
- non_measurement：改进性能类问题

【效应类型】
- harmful：存在有害效应
- insufficient：效应不足
- normal：效应正常但需要改进

只输出JSON：
{{"s1": "工具", "s2": "对象", "f": "场类型", "problem_type": "类型", "effect_type": "类型"}}"""


class SuFieldAnalyzer(AIAnalyzer):
    """物-场分析器"""

    def __init__(self, ai: AIBase):
        super().__init__(ai)

    async def analyze(self, problem: str, s1: str = "", s2: str = "", **kwargs) -> dict[str, Any] | None:
        user_input = problem
        if s1 or s2:
            parts = []
            if s1:
                parts.append(f"S1（工具）: {s1}")
            if s2:
                parts.append(f"S2（对象）: {s2}")
            user_input += "\n【已知物质-场参数】\n" + "\n".join(parts)
        user_input += "\n\n请分析这个问题，提取物质-场模型。"

        result = await self.call_ai_async(
            SUFIELD_SYSTEM_PROMPT,
            user_input,
            temperature=0.2,
            logger_prefix="物-场分析",
            json_mode=True,
        )
        if not result or not isinstance(result, dict):
            return None

        return {
            "s1": result.get("s1", ""),
            "s2": result.get("s2", ""),
            "f": result.get("f", ""),
            "problem_type": result.get("problem_type", "non_measurement"),
            "effect_type": result.get("effect_type", "normal"),
        }
