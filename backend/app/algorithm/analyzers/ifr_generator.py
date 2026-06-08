"""
IFR（理想最终解）生成器 — 从 RootSeek 迁移
两步管线：主生成 + 一致性验证
"""
import json
import logging
from typing import Any

from app.algorithm.base import AIAnalyzer, AIBase

logger = logging.getLogger(__name__)

IFR_SYSTEM_PROMPT = """你是一个TRIZ理想最终解（IFR）专家。IFR描述系统在理想状态下的行为。

【IFR定义】
- IFR-1：系统自身实现功能，不需要额外的资源和代价
- IFR-2：系统通过X元素实现功能，X元素由现有资源产生

【输出要求】
1. 明确系统应该做什么（what_to_achieve）
2. 明确要消除什么（what_to_eliminate）
3. 物理矛盾描述
4. X元素描述（理想化的解决方案核心）

只输出JSON：
{{"ifr_1_statement": "系统自身实现...", "ifr_2_statement": "通过X元素...", "x_element": "X元素描述", "physical_contradiction": {{"parameter": "参数", "requirement_a": "需求A", "requirement_b": "需求B"}}, "operating_time": "作用时间", "operating_zone": "作用区域", "what_to_eliminate": "要消除的", "what_to_achieve": "要实现的", "constraints": ["约束1"], "key_parameters": ["参数1"], "measurement_criteria": ["标准1"], "ifr_1_to_2_reasoning": "推理过程", "contradiction_derivation": "矛盾推导"}}"""


class IFRGenerator(AIAnalyzer):
    """最终理想解生成器"""

    def __init__(self, ai: AIBase):
        super().__init__(ai)

    async def analyze(self, problem: str, **kwargs) -> dict[str, Any] | None:
        user_prompt = f"系统描述：{problem}"
        for ctx_key, ctx_label in [
            ("root_cause_context", "根因分析"),
            ("function_model_context", "功能模型"),
            ("problem_pool_context", "问题池"),
        ]:
            ctx = kwargs.get(ctx_key, "")
            if ctx:
                user_prompt += f"\n\n【{ctx_label}】\n{ctx}"
        user_prompt += "\n\n请生成理想最终解。"

        result = await self.call_ai_async(
            IFR_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.3,
            logger_prefix="IFR生成",
            json_mode=True,
        )
        if not result or not isinstance(result, dict):
            return None

        def _s(v):
            return v if isinstance(v, str) else ""
        def _d(v):
            return v if isinstance(v, dict) else {}
        def _l(v):
            return v if isinstance(v, list) else []

        return {
            "ifr_1_statement": _s(result.get("ifr_1_statement")),
            "ifr_2_statement": _s(result.get("ifr_2_statement")),
            "x_element": _s(result.get("x_element")),
            "physical_contradiction": _d(result.get("physical_contradiction")),
            "operating_time": _s(result.get("operating_time")),
            "operating_zone": _s(result.get("operating_zone")),
            "what_to_eliminate": _s(result.get("what_to_eliminate")),
            "what_to_achieve": _s(result.get("what_to_achieve")),
            "constraints": _l(result.get("constraints")),
            "key_parameters": _l(result.get("key_parameters")),
            "measurement_criteria": _l(result.get("measurement_criteria")),
            "ifr_1_to_2_reasoning": _s(result.get("ifr_1_to_2_reasoning")),
            "contradiction_derivation": _s(result.get("contradiction_derivation")),
        }
