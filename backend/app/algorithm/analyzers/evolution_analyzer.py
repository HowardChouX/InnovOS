"""
进化趋势分析器 — S曲线和八大进化法则（从 RootSeek 迁移）
"""
import logging
from typing import Any

from app.algorithm.base import AIAnalyzer, AIBase

logger = logging.getLogger(__name__)

DEFAULT_LAW_NAMES = [
    "完备性法则",
    "能量传导法则",
    "节奏协调法则",
    "向超系统进化",
    "向微观进化",
    "动态性进化",
    "理想化法则",
    "不均衡进化法则",
]

VALID_STAGES = ("infancy", "growth", "maturity", "decline")

STAGE_CN = {"infancy": "婴儿期", "growth": "成长期", "maturity": "成熟期", "decline": "衰退期"}

EVOLUTION_SYSTEM_PROMPT = """你是一个TRIZ技术进化趋势分析专家。分析技术系统的S曲线位置和八大进化法则。

【八大进化法则】
1. 完备性法则：技术系统趋向具备动力装置、传动装置、执行装置和控制装置
2. 能量传导法则：能量必须在系统内部顺畅传导
3. 节奏协调法则：系统各部分的节奏趋向协调一致
4. 向超系统进化：系统成为更大超系统的一部分
5. 向微观进化：系统趋向使用更微观的层面实现功能
6. 动态性进化：系统趋向动态化和可调节
7. 理想化法则：系统趋向理想化，功能实现但不产生代价
8. 不均衡进化法则：系统各部分进化速度不一致

【S曲线阶段】
- 婴儿期(infancy)：技术刚出现，效率低
- 成长期(growth)：快速改进，效率提升
- 成熟期(maturity)：改进放缓，接近极限
- 衰退期(decline)：被新技术取代

只输出JSON：
{{"s_curve": {{"current_stage": "阶段", "evidence": "证据", "stages": {{"infancy": "...", "growth": "...", "maturity": "...", "decline": "..."}}}}, "laws": [{{"name": "法则名", "score": 0.8, "description": "分析", "suggestion": "建议"}}], "suggestions": ["建议1"], "key_insights": ["洞察1"]}}"""


class EvolutionAnalyzer(AIAnalyzer):
    """进化趋势分析器"""

    def __init__(self, ai: AIBase):
        super().__init__(ai)

    async def analyze(self, problem: str, **kwargs) -> dict[str, Any] | None:
        components = kwargs.get("components", [])
        components_str = ", ".join(components) if components else "未知"

        user_prompt = f"系统描述：{problem}\n系统组件：{components_str}"
        for ctx_key, ctx_label in [
            ("root_cause_context", "根因分析"),
            ("function_model_context", "功能模型"),
            ("resource_context", "资源分析"),
        ]:
            ctx = kwargs.get(ctx_key, "")
            if ctx:
                user_prompt += f"\n\n【{ctx_label}】\n{ctx}"
        user_prompt += "\n\n请分析技术进化趋势。"

        result = await self.call_ai_async(
            EVOLUTION_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.3,
            logger_prefix="进化趋势分析",
            json_mode=True,
        )
        if not result or not isinstance(result, dict):
            return None

        return self._validate_result(result)

    @staticmethod
    def _validate_result(result: dict) -> dict:
        s_curve = result.get("s_curve", {})
        if not isinstance(s_curve, dict):
            s_curve = {}
        current_stage = s_curve.get("current_stage", "")
        if current_stage and current_stage not in VALID_STAGES:
            current_stage = ""
        if "stages" not in s_curve or not isinstance(s_curve.get("stages"), dict):
            s_curve["stages"] = {}
        s_curve["current_stage"] = current_stage

        laws = result.get("laws", [])
        if not isinstance(laws, list):
            laws = []
        if len(laws) > 8:
            laws = laws[:8]
        while len(laws) < 8:
            idx = len(laws)
            laws.append({
                "name": DEFAULT_LAW_NAMES[idx] if idx < len(DEFAULT_LAW_NAMES) else f"法则{idx + 1}",
                "score": 0.0, "description": "", "suggestion": "",
            })
        for i, law in enumerate(laws):
            if not law.get("name"):
                law["name"] = DEFAULT_LAW_NAMES[i] if i < len(DEFAULT_LAW_NAMES) else f"法则{i + 1}"
            score = law.get("score", 0)
            if not isinstance(score, (int, float)):
                score = 0.0
            law["score"] = max(0.0, min(1.0, float(score)))
            law.setdefault("description", "")
            law.setdefault("suggestion", "")

        return {
            "s_curve": s_curve,
            "laws": laws,
            "suggestions": result.get("suggestions", []),
            "key_insights": result.get("key_insights", []),
        }
