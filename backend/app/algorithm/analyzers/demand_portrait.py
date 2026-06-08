"""
需求画像编排器 — 并行运行多种分析工具，汇总需求列表
"""
import asyncio
import logging
from typing import Any

from app.algorithm.base import AIBase
from app.algorithm.analyzers.resource_analyzer import ResourceAnalyzer
from app.algorithm.analyzers.ifr_generator import IFRGenerator
from app.algorithm.analyzers.thinking_tools.nine_screens import NineScreensAnalyzer
from app.algorithm.analyzers.thinking_tools.goldfish_analyzer import GoldfishAnalyzer
from app.algorithm.analyzers.thinking_tools.stc_operator import STCAnalyzer

logger = logging.getLogger(__name__)

DEMAND_SYSTEM_PROMPT = """你是一个TRIZ需求分析专家。基于多种分析工具的结果，提取并整理用户可能的需求。

对每个需求，标注来源分析工具和优先级。
需求类型包括：功能需求、性能需求、成本需求、安全需求、用户体验需求等。

只输出JSON：
{{"demands": [{{"id": "d1", "source": "来源工具", "category": "需求类型", "description": "需求描述", "priority": 0.8}}]}}"""


class DemandPortraitAnalyzer:
    """需求画像编排器 — 并行运行所有分析工具，汇总需求列表"""

    def __init__(self, ai: AIBase):
        self.ai = ai
        self.resource_analyzer = ResourceAnalyzer(ai)
        self.ifr_generator = IFRGenerator(ai)
        self.nine_screens = NineScreensAnalyzer(ai)
        self.goldfish = GoldfishAnalyzer(ai)
        self.stc = STCAnalyzer(ai)

    async def analyze(self, problem: str, knowledge_context: str = "") -> dict[str, Any]:
        logger.info(f"需求画像分析启动: {problem[:50]}...")

        results = await asyncio.gather(
            self.resource_analyzer.analyze(problem),
            self.ifr_generator.analyze(problem),
            self.nine_screens.analyze(problem),
            self.goldfish.analyze(problem),
            self.stc.analyze(problem),
            return_exceptions=True,
        )

        resource_result = results[0] if not isinstance(results[0], Exception) else None
        ifr_result = results[1] if not isinstance(results[1], Exception) else None
        nine_screens_result = results[2] if not isinstance(results[2], Exception) else None
        goldfish_result = results[3] if not isinstance(results[3], Exception) else None
        stc_result = results[4] if not isinstance(results[4], Exception) else None

        demands = await self._aggregate_demands(
            problem, resource_result, ifr_result, nine_screens_result, goldfish_result, stc_result
        )

        logger.info(f"需求画像分析完成: {len(demands)} 个需求")

        return {
            "resource_analysis": resource_result,
            "ideal_final_result": ifr_result,
            "nine_screens": nine_screens_result,
            "goldfish": goldfish_result,
            "stc": stc_result,
            "demands": demands,
        }

    async def _aggregate_demands(
        self, problem, resource, ifr, nine_screens, goldfish, stc
    ) -> list[dict]:
        context_parts = [f"系统描述：{problem}"]
        if resource:
            context_parts.append(f"资源分析：{resource.get('summary', '')}")
        if ifr:
            context_parts.append(f"IFR-1：{ifr.get('ifr_1_statement', '')}")
        if nine_screens:
            context_parts.append(f"九屏幕洞察：{nine_screens.get('insights', [])}")
        if goldfish:
            context_parts.append(f"金鱼法方案：{goldfish.get('final_solution', '')}")
        if stc:
            context_parts.append(f"STC洞察：{stc.get('insights', [])}")

        user_prompt = "\n".join(context_parts) + "\n\n请基于以上分析结果，提取用户可能的需求列表。"

        result = await self.ai.call_ai_async(
            DEMAND_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.3,
            logger_prefix="需求汇总",
            json_mode=True,
        )

        if not result or not isinstance(result, dict):
            return []

        demands = result.get("demands", [])
        if not isinstance(demands, list):
            return []

        for i, d in enumerate(demands):
            if not d.get("id"):
                d["id"] = f"d{i + 1}"
            d.setdefault("source", "综合分析")
            d.setdefault("category", "功能需求")
            d.setdefault("description", "")
            d.setdefault("priority", 0.5)
            d["user_rating"] = None

        return demands
