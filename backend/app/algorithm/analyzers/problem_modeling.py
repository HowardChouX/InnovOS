"""
问题建模编排器 — 综合多种分析器，生成创新方向
"""
import asyncio
import logging
from typing import Any

from app.algorithm.base import AIBase
from app.algorithm.analyzers.resource_analyzer import ResourceAnalyzer
from app.algorithm.analyzers.evolution_analyzer import EvolutionAnalyzer
from app.algorithm.analyzers.sufield_analyzer import SuFieldAnalyzer

logger = logging.getLogger(__name__)

INNOVATION_SYSTEM_PROMPT = """你是一个TRIZ创新方向生成专家。基于功能分析、因果链、物-场分析和进化趋势，生成创新方向。

每个创新方向应包含：
1. 具体的技术方案描述
2. 基于的TRIZ原理或法则
3. 预期效果

只输出JSON：
{{"innovations": [{{"id": "in1", "source": "来源分析", "description": "方案描述", "principle": "TRIZ原理"}}]}}"""


class ProblemModelingAnalyzer:
    """问题建模编排器"""

    def __init__(self, ai: AIBase):
        self.ai = ai
        self.resource_analyzer = ResourceAnalyzer(ai)
        self.evolution_analyzer = EvolutionAnalyzer(ai)
        self.sufield_analyzer = SuFieldAnalyzer(ai)

    async def analyze(self, problem: str, demand_results: dict | None = None) -> dict[str, Any]:
        logger.info(f"问题建模分析启动: {problem[:50]}...")

        resource_result, evolution_result, sufield_result = await asyncio.gather(
            self.resource_analyzer.analyze(problem),
            self.evolution_analyzer.analyze(problem),
            self.sufield_analyzer.analyze(problem),
            return_exceptions=True,
        )

        resource_result = resource_result if not isinstance(resource_result, Exception) else None
        evolution_result = evolution_result if not isinstance(evolution_result, Exception) else None
        sufield_result = sufield_result if not isinstance(sufield_result, Exception) else None

        innovations = await self._generate_innovations(
            problem, resource_result, evolution_result, sufield_result, demand_results
        )

        logger.info(f"问题建模分析完成: {len(innovations)} 个创新方向")

        return {
            "resource_analysis": resource_result,
            "evolution_trend": evolution_result,
            "sufield_analysis": sufield_result,
            "innovations": innovations,
        }

    async def _generate_innovations(
        self, problem, resource, evolution, sufield, demands
    ) -> list[dict]:
        context_parts = [f"系统描述：{problem}"]
        if resource:
            context_parts.append(f"资源分析：{resource.get('summary', '')}")
        if evolution:
            stage = evolution.get("s_curve", {}).get("current_stage", "未知")
            context_parts.append(f"S曲线阶段：{stage}")
        if sufield:
            context_parts.append(f"物-场模型：S1={sufield.get('s1','')}, S2={sufield.get('s2','')}, F={sufield.get('f','')}")

        user_prompt = "\n".join(context_parts) + "\n\n请基于以上分析生成创新方向。"

        result = await self.ai.call_ai_async(
            INNOVATION_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.4,
            logger_prefix="创新方向生成",
            json_mode=True,
        )

        if not result or not isinstance(result, dict):
            return []

        innovations = result.get("innovations", [])
        if not isinstance(innovations, list):
            return []

        for i, inn in enumerate(innovations):
            if not inn.get("id"):
                inn["id"] = f"in{i + 1}"
            inn.setdefault("source", "综合分析")
            inn.setdefault("description", "")
            inn.setdefault("principle", "")
            inn["user_rating"] = None

        return innovations
