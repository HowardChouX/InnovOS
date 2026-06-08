"""
资源分析器 — 七类资源系统化扫描（从 RootSeek 迁移）
"""
import logging
from typing import Any

from app.algorithm.base import AIAnalyzer, AIBase

logger = logging.getLogger(__name__)

RESOURCE_SYSTEM_PROMPT = """你是一个TRIZ资源分析专家。你的任务是系统化扫描问题中可用的七类资源。

【七类资源】
1. 物质资源：系统内外可利用的物质、材料、零件
2. 能量/场资源：机械场、热场、电场、磁场、化学场、重力场等
3. 信息资源：数据、信号、反馈、知识
4. 时间资源：空闲时间、操作间隙、预热/冷却时间
5. 空间资源：未利用的空间、位置、方向、层面
6. 功能资源：系统和超系统可提供的功能
7. 系统资源：系统本身的结构、组件、超系统

对每类资源，识别：
- 当前是否已利用
- 潜在利用方式
- 与问题的关联度

只输出JSON：
{{"substance_resources": [{{"name": "资源名", "description": "描述", "available": true}}], "energy_resources": [...], "information_resources": [...], "time_resources": [...], "space_resources": [...], "functional_resources": [...], "system_resources": [...], "summary": "资源分析总结", "priority_resources": [{{"name": "优先资源", "reason": "原因"}}]}}"""


class ResourceAnalyzer(AIAnalyzer):
    """资源分析器 — 七类资源系统化扫描"""

    def __init__(self, ai: AIBase):
        super().__init__(ai)

    async def analyze(self, problem: str, **kwargs) -> dict[str, Any] | None:
        func_ctx = kwargs.get("function_model_context", "")
        user_prompt = f"系统描述：{problem}"
        if func_ctx:
            user_prompt += f"\n\n【功能模型信息】\n{func_ctx}"
        user_prompt += "\n\n请扫描并分析所有七类资源。"

        result = await self.call_ai_async(
            RESOURCE_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.3,
            logger_prefix="资源分析",
            json_mode=True,
        )
        if not result or not isinstance(result, dict):
            return None

        return {
            "substance_resources": result.get("substance_resources") or [],
            "energy_resources": result.get("energy_resources") or [],
            "information_resources": result.get("information_resources") or [],
            "time_resources": result.get("time_resources") or [],
            "space_resources": result.get("space_resources") or [],
            "functional_resources": result.get("functional_resources") or [],
            "system_resources": result.get("system_resources") or [],
            "summary": result.get("summary") or "",
            "priority_resources": result.get("priority_resources") or [],
        }
