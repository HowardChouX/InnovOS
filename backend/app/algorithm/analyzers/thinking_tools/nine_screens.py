"""
九屏幕法分析器 — 从 RootSeek 迁移
"""
from typing import Any

from app.algorithm.base import AIAnalyzer, AIBase

NINE_SCREENS_SYSTEM_PROMPT = """你是一个TRIZ九屏幕法分析专家。

【九屏幕法】
从时间和系统两个维度，对问题进行9个视角的分析：
- 时间维度：过去(past)、现在(present)、未来(future)
- 系统维度：子系统(subsystem)、系统(system)、超系统(supersystem)

对每个屏幕，分析该视角下的系统状态和特征。

只输出JSON：
{{"screens": {{"supersystem": {{"past": "", "present": "", "future": ""}}, "system": {{"past": "", "present": "", "future": ""}}, "subsystem": {{"past": "", "present": "", "future": ""}}}}, "insights": ["洞察1"], "contradictions": ["矛盾1"]}}"""


class NineScreensAnalyzer(AIAnalyzer):
    """九屏幕法分析器"""

    def __init__(self, ai: AIBase):
        super().__init__(ai)

    async def analyze(self, problem: str, **kwargs) -> dict[str, Any] | None:
        user_prompt = f"系统描述：{problem}\n\n请进行九屏幕法分析。"

        result = await self.call_ai_async(
            NINE_SCREENS_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.3,
            logger_prefix="九屏幕分析",
            json_mode=True,
        )
        if not result or not isinstance(result, dict):
            return None

        result["screens"] = result.get("screens") or {}
        result["insights"] = result.get("insights") or []
        result["contradictions"] = result.get("contradictions") or []

        screens = result.get("screens", {})
        for level in ["supersystem", "system", "subsystem"]:
            if level not in screens:
                screens[level] = {}
            for period in ["past", "present", "future"]:
                screens[level].setdefault(period, "")

        return result
