"""
STC算子分析器 — 尺寸-时间-成本极限思维（从 RootSeek 迁移）
"""
import logging
from typing import Any

from app.algorithm.base import AIAnalyzer, AIBase

logger = logging.getLogger(__name__)

STC_SYSTEM_PROMPT = """你是一个TRIZ STC算子分析专家。通过尺寸(Size)、时间(Time)、成本(Cost)三个参数的极限思维来突破思维定式。

【分析方法】
1. Size Zero → Size Infinite：假设尺寸从零到无穷大，系统会怎样？
2. Time Zero → Time Infinite：假设时间从零到无穷大，系统会怎样？
3. Cost Zero → Cost Infinite：假设成本从零到无穷大，系统会怎样？

对每个极端情况，思考：
- 系统行为变化
- 暴露的隐含需求
- 可能的创新方向

只输出JSON：
{{"size_zero": "尺寸为零时...", "size_infinite": "尺寸无穷大时...", "time_zero": "时间为零时...", "time_infinite": "时间无穷大时...", "cost_zero": "成本为零时...", "cost_infinite": "成本无穷大时...", "insights": ["洞察1"], "contradictions": ["矛盾1"]}}"""


class STCAnalyzer(AIAnalyzer):
    """STC算子分析器"""

    def __init__(self, ai: AIBase):
        super().__init__(ai)

    async def analyze(self, problem: str, **kwargs) -> dict[str, Any] | None:
        user_prompt = f"系统描述：{problem}\n\n请进行STC算子分析。"

        result = await self.call_ai_async(
            STC_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.3,
            logger_prefix="STC算子分析",
            json_mode=True,
        )
        if not result or not isinstance(result, dict):
            return None

        for key in ("size_zero", "size_infinite", "time_zero", "time_infinite", "cost_zero", "cost_infinite"):
            result[key] = result.get(key) or ""
        for key in ("insights", "contradictions"):
            result[key] = result.get(key) or []

        return result
