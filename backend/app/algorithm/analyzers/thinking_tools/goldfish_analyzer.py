"""
金鱼法分析器 — 幻想方案分解（从 RootSeek 迁移）
"""
import logging
from typing import Any

from app.algorithm.base import AIAnalyzer, AIBase

logger = logging.getLogger(__name__)

GOLDFISH_SYSTEM_PROMPT = """你是一个TRIZ金鱼法分析专家。

【金鱼法原理】
像许愿一样，先让用户描述一个"幻想方案"（不受任何约束的理想解决方案），
然后逐步分解：哪些部分已经可以实现？哪些需要技术突破？哪些是约束条件？

【分析步骤】
1. 提取幻想方案的核心需求
2. 分解为可实现部分和需突破部分
3. 识别约束条件
4. 从幻想方案中提炼实际可行的创新方向

只输出JSON：
{{"fantasy_solution": "幻想方案描述", "achievable_parts": ["可实现部分1"], "breakthrough_parts": ["需突破部分1"], "constraints": ["约束1"], "iterations": [{{"step": 1, "description": "分解步骤"}}], "final_solution": "最终可行方案", "insights": ["洞察1"]}}"""


class GoldfishAnalyzer(AIAnalyzer):
    """金鱼法分析器"""

    def __init__(self, ai: AIBase):
        super().__init__(ai)

    async def analyze(self, problem: str, **kwargs) -> dict[str, Any] | None:
        user_prompt = f"系统描述：{problem}"
        for ctx_key, ctx_label in [
            ("root_cause_context", "根因分析"),
            ("function_model_context", "功能模型"),
            ("resource_context", "资源分析"),
        ]:
            ctx = kwargs.get(ctx_key, "")
            if ctx:
                user_prompt += f"\n\n【{ctx_label}】\n{ctx}"
        user_prompt += "\n\n请使用金鱼法进行分析。"

        result = await self.call_ai_async(
            GOLDFISH_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.5,
            logger_prefix="金鱼法分析",
            json_mode=True,
        )
        if not result or not isinstance(result, dict):
            return None

        for key in ("fantasy_solution", "final_solution"):
            result[key] = result.get(key) or ""
        for key in ("iterations", "insights", "achievable_parts", "breakthrough_parts", "constraints"):
            result[key] = result.get(key) or []

        return result
