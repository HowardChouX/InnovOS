"""
问题建模编排器 — 综合 6 种分析器并行分析，生成创新方向列表（用户评分）
"""
import asyncio
import json
import logging
from typing import Any

from app.algorithm.base import AIBase
from app.algorithm.analyzers.resource_analyzer import ResourceAnalyzer
from app.algorithm.analyzers.evolution_analyzer import EvolutionAnalyzer
from app.algorithm.analyzers.sufield_analyzer import SuFieldAnalyzer
from app.algorithm.analyzers.function_analyzer import FunctionAnalyzer
from app.algorithm.analyzers.root_cause_analyzer import RootCauseAnalyzer
from app.algorithm.analyzers.trimming_analyzer import TrimmingAnalyzer

logger = logging.getLogger(__name__)

INNOVATION_SYSTEM_PROMPT = """你是一个TRIZ创新方向生成专家。基于功能分析、资源分析、因果链、物-场、裁剪分析和进化趋势的完整结果，生成创新方向列表。

⚠️ 关键要求：
- 创新方向是**用户视角的具体创新方向**（如"采用智能温控材料"、"优化散热风道设计"）
- 每个方向必须是具体的、可操作的，不是笼统的目标
- 必须标注来源分析器和所依据的 TRIZ 原理/法则
- 至少列出 4 条不同的创新方向

只输出JSON：
{{"innovations": [{{"id": "in1", "source": "来源分析器", "description": "创新方向描述", "principle": "依据的TRIZ原理", "expected_effect": "预期效果"}}]}}"""


class ProblemModelingAnalyzer:
    """问题建模编排器 — 6 路并行分析，生成创新方向"""

    def __init__(self, ai: AIBase):
        self.ai = ai
        self.resource_analyzer = ResourceAnalyzer(ai)
        self.evolution_analyzer = EvolutionAnalyzer(ai)
        self.sufield_analyzer = SuFieldAnalyzer(ai)
        self.function_analyzer = FunctionAnalyzer(ai)
        self.root_cause_analyzer = RootCauseAnalyzer(ai)
        self.trimming_analyzer = TrimmingAnalyzer(ai)

    async def analyze(self, problem: str, demand_results: dict | None = None) -> dict[str, Any]:
        logger.info(f"问题建模分析启动: {problem[:50]}...")

        resource_task = self.resource_analyzer.analyze(problem)
        evolution_task = self.evolution_analyzer.analyze(problem)
        sufield_task = self.sufield_analyzer.analyze(problem)
        function_task = self.function_analyzer.analyze(problem)
        root_cause_task = self.root_cause_analyzer.analyze(problem)

        # 先跑不需要依赖的 5 路并行
        results = await asyncio.gather(
            resource_task, evolution_task, sufield_task,
            function_task, root_cause_task,
            return_exceptions=True,
        )

        def _safe(idx):
            return results[idx] if not isinstance(results[idx], Exception) else None

        resource_result = _safe(0)
        evolution_result = _safe(1)
        sufield_result = _safe(2)
        function_result = _safe(3)
        root_cause_result = _safe(4)

        # 裁剪分析依赖功能分析结果，有条件地执行
        trimming_result = None
        if isinstance(function_result, dict):
            sys_comps = function_result.get("system_components", [])
            sys_names = [c["name"] if isinstance(c, dict) else c for c in sys_comps]
            super_comps = function_result.get("supersystem_components", [])
            super_names = [c["name"] if isinstance(c, dict) else c for c in super_comps]
            try:
                trimming_result = await self.trimming_analyzer.analyze_with_hints(
                    problem, sys_names, super_names, [], [], "", ""
                )
            except Exception as e:
                logger.warning(f"裁剪分析失败: {e}")

        innovations = await self._generate_innovations(
            problem, resource_result, evolution_result, sufield_result,
            function_result, root_cause_result, trimming_result,
            demand_results,
        )

        logger.info(f"问题建模分析完成: {len(innovations)} 个创新方向")

        return {
            "resource_analysis": resource_result,
            "evolution_trend": evolution_result,
            "sufield_analysis": sufield_result,
            "function_analysis": function_result,
            "root_cause_analysis": root_cause_result,
            "trimming_analysis": trimming_result,
            "innovations": innovations,
        }

    async def _generate_innovations(
        self, problem, resource, evolution, sufield,
        function_result, root_cause, trimming, demands
    ) -> list[dict]:
        context_parts = [f"系统描述：{problem}"]

        if function_result:
            context_parts.append(f"【功能分析完整结果】\n{json.dumps(function_result, ensure_ascii=False, indent=2)}")

        if resource:
            context_parts.append(f"【资源分析完整结果】\n{json.dumps(resource, ensure_ascii=False, indent=2)}")

        if root_cause:
            rc_summary = {
                "initial_defect": root_cause.get("initial_defect", ""),
                "root_causes": root_cause.get("root_cause_details", []),
                "total_nodes": len(root_cause.get("nodes", [])),
            }
            context_parts.append(f"【因果链分析结果】\n{json.dumps(rc_summary, ensure_ascii=False, indent=2)}")

        if sufield:
            context_parts.append(f"【物-场分析完整结果】\n{json.dumps(sufield, ensure_ascii=False, indent=2)}")

        if trimming:
            trim_summary = {
                "candidates": trimming.get("trimming_candidates", []),
                "summary": trimming.get("summary", ""),
            }
            context_parts.append(f"【裁剪分析结果】\n{json.dumps(trim_summary, ensure_ascii=False, indent=2)}")

        if evolution:
            context_parts.append(f"【进化趋势分析完整结果】\n{json.dumps(evolution, ensure_ascii=False, indent=2)}")

        if demands:
            context_parts.append(f"【用户需求】\n{json.dumps(demands, ensure_ascii=False, indent=2)}")

        user_prompt = "\n\n".join(context_parts) + "\n\n请基于以上所有分析结果，生成具体可行的创新方向列表。"

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
            inn.setdefault("expected_effect", "")
            inn["user_rating"] = None

        return innovations
