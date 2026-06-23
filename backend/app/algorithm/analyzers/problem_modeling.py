"""
问题建模编排器 — 综合 6 种分析器并行分析，生成创新方向列表（用户评分）
"""

import asyncio
import json
import logging
from typing import Any

from app.algorithm.analyzers.evolution_analyzer import EvolutionAnalyzer
from app.algorithm.analyzers.resource_analyzer import ResourceAnalyzer
from app.algorithm.analyzers.sufield_analyzer import SuFieldAnalyzer
from app.algorithm.base import AIBase

logger = logging.getLogger(__name__)

INNOVATION_SYSTEM_PROMPT = """你是一个TRIZ创新方向生成专家。基于各分析工具结果，生成技术方向。

⚠️ 关键原则：
1. 创新方向是"技术手段方向"，不是"产品应用"。如"外壳降温"、"减少产热"、"产热转移"、"相变储能"，而不是"给手机加散热片"。
2. 必须脱离具体产品领域，提炼通用技术方向。如手机发热问题，应提炼为"热传导优化"、"热辐射增强"、"热对流设计"等通用方向，而非"手机散热"。
3. 每个方向要足够通用，能跨越不同领域（航天、汽车、电子、建筑等）找到相关专利。

每个方向必须回答"什么技术手段"，不回答"用在什么产品上"。
必须标注来源于哪个分析器（只能是：资源分析/进化趋势/物-场分析/功能分析/因果链分析/裁剪分析 之一）。
必须附带所依据的TRIZ原理。

至少列出 6 条不同的方向。

只输出JSON：
{{"innovations": [{{"id": "in1", "source_analyzer": "资源分析", "description": "热传导路径优化", "principle": "局部质量原理", "expected_effect": "预期效果描述"}}]}}"""


class ProblemModelingAnalyzer:
    """问题建模编排器 — 6 路并行分析，生成创新方向"""

    def __init__(self, ai: AIBase):
        self.ai = ai
        self.resource_analyzer = ResourceAnalyzer(ai)
        self.evolution_analyzer = EvolutionAnalyzer(ai)
        self.sufield_analyzer = SuFieldAnalyzer(ai)

    async def analyze(self, problem: str, demand_results: dict | None = None) -> dict[str, Any]:
        logger.info(f"问题建模分析启动: {problem[:50]}...")

        # 资源/进化/物-场：1 次 AI 调用即可，直接使用
        resource_task = self.resource_analyzer.analyze(problem)
        evolution_task = self.evolution_analyzer.analyze(problem)
        sufield_task = self.sufield_analyzer.analyze(problem)

        # 功能分析：简化版，1 次 AI 调用完成组件识别和交互摘要
        async def simple_function_analysis():
            prompt = f"""分析以下系统，识别所有系统内部组件、超系统组件，以及关键组件间的交互关系。

系统描述：{problem}

只输出JSON：
{{"system_components": [{{"name": "组件名", "description": "功能描述"}}], "supersystem_components": [{{"name": "超系统组件", "description": "与系统的交互"}}], "key_interactions": [{{"tool": "组件A", "receiver": "组件B", "type": "有害/不足/正常", "verb": "交互动词"}}]}}"""
            result = await self.ai.call_ai_async(
                "", prompt, temperature=0.1, logger_prefix="功能分析(简化)", json_mode=True
            )
            return result if isinstance(result, dict) else None

        # 因果链分析：简化版，1 次 AI 调用直接识别根因
        async def simple_root_cause():
            prompt = f"""分析以下问题，直接识别根本原因。

系统描述：{problem}

只输出JSON：
{{"root_causes": [{{"id": "rc1", "text": "根因描述"}}], "key_insights": ["关键洞察1"], "initial_defect": "初始问题描述"}}"""
            result = await self.ai.call_ai_async(
                "", prompt, temperature=0.2, logger_prefix="因果链(简化)", json_mode=True
            )
            return result if isinstance(result, dict) else None

        function_task = simple_function_analysis()
        root_cause_task = simple_root_cause()

        # 并行运行 5 路
        results = await asyncio.gather(
            resource_task,
            evolution_task,
            sufield_task,
            function_task,
            root_cause_task,
            return_exceptions=True,
        )

        def _safe(idx):
            return results[idx] if not isinstance(results[idx], Exception) else None

        def _ensure_dict(d):
            return d if isinstance(d, dict) else {}

        resource_result = _ensure_dict(_safe(0))
        evolution_result = _ensure_dict(_safe(1))
        sufield_result = _ensure_dict(_safe(2))
        function_result = _ensure_dict(_safe(3))
        root_cause_result = _ensure_dict(_safe(4))

        # 裁剪分析：简化版，1 次 AI 调用
        trimming_result = None
        sys_comps = function_result.get("system_components", [])
        sys_names = [c["name"] if isinstance(c, dict) else c for c in sys_comps]
        super_comps = function_result.get("supersystem_components", [])
        super_names = [c["name"] if isinstance(c, dict) else c for c in super_comps]
        try:
            trim_prompt = f"""分析以下系统，判断哪些组件可以被裁剪（消除）而功能可由其他组件或超系统承接。

系统描述：{problem}
系统组件：{", ".join(sys_names) if sys_names else "无"}
超系统组件：{", ".join(super_names) if super_names else "无"}

只输出JSON：
{{"trimming_candidates": [{{"component": "组件名", "reason": "裁剪理由", "transferred_to": "承接方"}}], "summary": "裁剪分析总结"}}"""
            trim_result = await self.ai.call_ai_async(
                "", trim_prompt, temperature=0.2, logger_prefix="裁剪分析(简化)", json_mode=True
            )
            trimming_result = trim_result if isinstance(trim_result, dict) else None
        except Exception as e:
            logger.warning(f"裁剪分析失败: {e}")

        innovations = await self._generate_innovations(
            problem,
            resource_result,
            evolution_result,
            sufield_result,
            function_result,
            root_cause_result,
            trimming_result,
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
        self, problem, resource, evolution, sufield, function_result, root_cause, trimming, demands
    ) -> list[dict]:
        context_parts = [f"系统描述：{problem}"]

        if resource:
            context_parts.append(f"【资源分析】\n{json.dumps(resource, ensure_ascii=False, indent=2)}")
        if evolution:
            context_parts.append(f"【进化趋势分析】\n{json.dumps(evolution, ensure_ascii=False, indent=2)}")
        if sufield:
            context_parts.append(f"【物-场分析】\n{json.dumps(sufield, ensure_ascii=False, indent=2)}")
        if function_result:
            context_parts.append(f"【功能分析】\n{json.dumps(function_result, ensure_ascii=False, indent=2)}")
        if root_cause:
            rc_summary = {
                "initial_defect": root_cause.get("initial_defect", ""),
                "root_causes": root_cause.get("root_causes", []),
            }
            context_parts.append(f"【因果链分析】\n{json.dumps(rc_summary, ensure_ascii=False, indent=2)}")
        if trimming:
            context_parts.append(f"【裁剪分析】\n{json.dumps(trimming, ensure_ascii=False, indent=2)}")
        if demands:
            context_parts.append(f"【用户需求评分参考】\n{json.dumps(demands, ensure_ascii=False, indent=2)}")

        prompt = (
            "\n\n".join(context_parts)
            + "\n\n请基于以上所有分析结果，生成创新方向。创新方向是解决核心问题的思路和策略，不是具体实施方案。至少 5 条，每条标注来源于哪个分析器。"
        )

        result = await self.ai.call_ai_async(
            INNOVATION_SYSTEM_PROMPT,
            prompt,
            temperature=0.4,
            logger_prefix="创新方向生成",
            json_mode=True,
        )

        result = result if isinstance(result, dict) else {}
        innovations = result.get("innovations", [])
        if not isinstance(innovations, list):
            return []

        for i, inn in enumerate(innovations):
            inn["id"] = f"in{i + 1}"
            inn.setdefault("source_analyzer", "综合分析")
            inn.setdefault("description", "")
            inn.setdefault("principle", "")
            inn.setdefault("expected_effect", "")
            inn["user_rating"] = None

        return innovations
