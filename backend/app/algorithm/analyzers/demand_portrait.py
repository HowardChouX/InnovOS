"""
需求画像编排器 — 并行运行多种分析工具，汇总需求列表
"""
import asyncio
import json
import logging
from typing import Any

from app.algorithm.base import AIBase
from app.algorithm.analyzers.resource_analyzer import ResourceAnalyzer
from app.algorithm.analyzers.ifr_generator import IFRGenerator
from app.algorithm.analyzers.thinking_tools.nine_screens import NineScreensAnalyzer
from app.algorithm.analyzers.thinking_tools.goldfish_analyzer import GoldfishAnalyzer
from app.algorithm.analyzers.thinking_tools.stc_operator import STCAnalyzer

logger = logging.getLogger(__name__)

DEMAND_SYSTEM_PROMPT = """你是一个TRIZ需求分析专家。你的任务是基于多种分析工具的结果，提取用户最关心、最需要被解决的**用户需求**。

⚠️ 关键要求：
- 用户需求是**用户视角**的期望或痛点（如"希望手机不发烫"、"别卡顿"），**不是**技术解决方案（如"加均热板"、"改散热材料"）
- 例如✅："玩游戏时手机不烫手" → 这是需求
- 例如❌："在手机内部布置均热板" → 这是方案，不要
- 每个需求必须是用户说的出来的话，简洁直接
- 需求类型包括：功能需求、性能需求、成本需求、安全需求、用户体验需求、外观需求、续航需求等
- 至少列出 6 条不同的需求，覆盖不同维度
- 如果有多条相似需求，合并为一条

只输出JSON：
{{"demands": [{{"id": "d1", "source": "来源分析器", "category": "需求类型", "description": "用户视角的需求描述", "priority": 0.8}}]}}"""


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
            context_parts.append(f"【资源分析完整结果】\n{json.dumps(resource, ensure_ascii=False, indent=2)}")

        if ifr:
            context_parts.append(f"【IFR理想解完整结果】\n{json.dumps(ifr, ensure_ascii=False, indent=2)}")

        if nine_screens:
            context_parts.append(f"【九屏幕法完整结果】\n{json.dumps(nine_screens, ensure_ascii=False, indent=2)}")

        if goldfish:
            context_parts.append(f"【金鱼法完整结果】\n{json.dumps(goldfish, ensure_ascii=False, indent=2)}")

        if stc:
            context_parts.append(f"【STC算子完整结果】\n{json.dumps(stc, ensure_ascii=False, indent=2)}")

        user_prompt = "\n\n".join(context_parts) + "\n\n请基于以上所有分析结果，从用户视角列出用户的原始需求。需求是用户想要什么效果（如'手机不发烫'），而不是技术上怎么做（如'加散热片'）。至少列出 6 条不同维度的需求。"


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
