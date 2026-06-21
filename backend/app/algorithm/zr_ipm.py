"""
ZR-IPM (智融创新问题映射) 算法引擎

四层架构:
  1. 多维语义解析 → 提取问题核心要素
  2. 创新问题分类 → 识别问题类型与矛盾
  3. 专利RAG增强 → 检索相似专利路径
  4. 结构化建模 → 输出冲突图谱 + 创新原理
"""

import json
import logging
from .ai_client import chat_completion
from .model_resolver import model_resolver

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个创新问题分析专家。分析用户的技术问题，输出JSON：
{
  "centerConflict": "核心矛盾描述",
  "satellites": [
    {"label": "方面名", "sublabel": "方向", "description": "详细描述"}
  ],
  "principles": ["推荐创新原理名"],
  "patentKeywords": ["检索关键词"]
}"""

SOLUTION_PROMPT = "根据以下创新方向和参考专利，为每个方向生成至少一个创新解决方案，返回JSON数组"

SOLUTION_SYSTEM = """你是一个创新方案专家。根据用户问题、创新方向和参考专利，生成创新解决方案。
要求：
1. 每个创新方向至少生成一个方案
2. 重点参考用户高评分的专利（标记为★的专利），这些是用户认为最相关的专利
3. 高评分专利的技术方案应优先融入解决方案中
4. 方案应说明如何借鉴或改进专利中的技术
5. 每个方案只参考与它对应的创新方向最相关的那一个专利
返回JSON数组，每个元素包含：
- title: 方案标题
- direction: 本方案对应的创新方向（原文）
- description: 方案详细描述（说明如何借鉴或改进专利中的技术）
- principles: 使用的创新原理（数组）
- referencedPatents: 本方案借鉴了哪个专利的技术（数组，只含一个专利名）"""

EVALUATE_PROMPT = "评估以下创新方案，返回四维评分JSON"

REPORT_SYSTEM = """你是一个创新分析报告专家。根据以下完整分析流程的数据，生成一份结构化的创新分析报告。
报告要求：
1. 用中文撰写，语言专业清晰
2. 包含完整的技术分析链路：需求→建模→专利→方案→评估
3. 对方案进行综合排序和推荐
4. 给出可落地的实施建议

返回JSON，包含：
- title: 报告标题
- summary: 执行摘要（200字以内）
- sections: [
    {heading: "章节标题", content: "章节内容"}
  ]
- recommendations: [具体建议1, 建议2, ...]
- topSolutions: [排名靠前的方案标题]
"""

EVALUATE_SYSTEM = "你是一个创新评估专家。返回JSON: scores(innovation/feasibility/completeness/conversion 0-100), overall, grade(A+/A/B+/B/C), strengths(数组), weaknesses(数组), recommendations(数组)"


class ZRIPMEngine:

    @staticmethod
    def _get_model_id() -> str:
        """从全局设置中获取分配的对话模型 ID"""
        s = model_resolver.get_assigned_settings()
        return s.get("chat_model") or ""

    async def analyze(self, task_description: str) -> dict:
        """分析问题，返回冲突图谱"""
        result = await chat_completion(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=task_description,
            response_format=dict,
            model_id=self._get_model_id(),
        )
        # 防御：AI 可能返回字符串而非 dict（JSON 解析异常等）
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"AI returned string, not dict: {result[:200]}")
                result = {}
        return self._build_conflict_graph(result)

    async def generate_solutions(self, task_description: str, patents: list[dict] | None = None,
                                  innovations: list[dict] | None = None, direction_patents: dict | None = None,
                                  patent_ratings: dict | None = None) -> list[dict]:
        """生成解决方案，按创新方向生成，每个方向至少一个方案
        
        Args:
            patent_ratings: 专利索引->评分的映射，用于算法加权
        """
        context_parts = [task_description]

        if innovations:
            dir_lines = []
            for i, inn in enumerate(innovations):
                desc = inn.get("description", "")
                if desc:
                    dir_lines.append(f"  方向{i+1}: {desc}")
            if dir_lines:
                context_parts.append("\n创新方向：\n" + "\n".join(dir_lines))

        if direction_patents:
            dp_lines = []
            for direction, p_list in direction_patents.items():
                if p_list:
                    dp_lines.append(f"  [{direction[:50]}] → {p_list[0]}")
            if dp_lines:
                context_parts.append("\n方向-专利对应关系：\n" + "\n".join(dp_lines))
        elif patents:
            # 使用用户评分进行算法加权：高评分专利更突出
            scored_patents = []
            for i, p in enumerate(patents):
                title = p.get("title") or p.get("_title") or "未知专利"
                rel = p.get("relevance", 0)
                user_rating = patent_ratings.get(i, 0) if patent_ratings else 0
                # 综合得分 = 相关度 * 0.4 + 用户评分 * 0.6（用户评分权重更高）
                combined_score = rel * 0.4 + (user_rating / 5.0) * 0.6
                scored_patents.append({
                    "title": title,
                    "relevance": rel,
                    "user_rating": user_rating,
                    "combined_score": combined_score,
                    "abstract": p.get("abstract", "")[:200] if p.get("abstract") else "",
                })
            
            # 按综合得分降序排序
            scored_patents.sort(key=lambda x: x["combined_score"], reverse=True)
            
            # 高评分专利（用户评分>=4）放在最前面，用特殊标记
            high_rated = [p for p in scored_patents if p["user_rating"] >= 4]
            normal_rated = [p for p in scored_patents if p["user_rating"] < 4]
            
            patent_lines = []
            if high_rated:
                patent_lines.append("【重点参考专利（用户高评分）】")
                for i, p in enumerate(high_rated, 1):
                    patent_lines.append(f"  ★ 专利{i}: {p['title']} (用户评分: {p['user_rating']}/5, 相关度: {p['relevance']:.0%})")
                    if p["abstract"]:
                        patent_lines.append(f"     摘要: {p['abstract']}")
            
            if normal_rated:
                patent_lines.append("【一般参考专利】")
                for i, p in enumerate(normal_rated, len(high_rated) + 1):
                    patent_lines.append(f"  专利{i}: {p['title']} (用户评分: {p['user_rating']}/5, 相关度: {p['relevance']:.0%})")
            
            if patent_lines:
                context_parts.append("\n参考专利（按用户评分加权排序）：\n" + "\n".join(patent_lines))

        user_prompt = f"{SOLUTION_PROMPT}：\n" + "\n".join(context_parts)

        result = await chat_completion(
            system_prompt=SOLUTION_SYSTEM,
            user_prompt=user_prompt,
            response_format=dict,
            model_id=self._get_model_id(),
        )
        if isinstance(result, dict) and "solutions" in result:
            return result["solutions"]
        if isinstance(result, list):
            return result
        return []

    async def evaluate(self, solution_description: str) -> dict:
        """评估方案"""
        return await chat_completion(
            system_prompt=EVALUATE_SYSTEM,
            user_prompt=f"{EVALUATE_PROMPT}：\n{solution_description}",
            response_format=dict,
            model_id=self._get_model_id(),
        )

    async def generate_report(self, task_description: str, innovations: list,
                               patents: list, solutions: list, evaluations: list) -> dict:
        """生成完整分析报告"""
        context_parts = [f"用户问题：{task_description}"]

        if innovations:
            inn_lines = [f"  - {inn.get('description', '')}" for inn in innovations[:10]]
            context_parts.append("\n创新方向：\n" + "\n".join(inn_lines))

        if patents:
            p_lines = [f"  - {p.get('title', '')}" for p in patents[:10]]
            context_parts.append("\n检索到的专利：\n" + "\n".join(p_lines))

        if solutions:
            s_lines = [f"  - {sol.get('title', '')}: {sol.get('description', '')[:100]}"
                       for sol in solutions[:10]]
            context_parts.append("\n生成的方案：\n" + "\n".join(s_lines))

        if evaluations:
            e_lines = [f"  - {e.get('solution_title', '')}: 总分{e.get('evaluation', {}).get('overall', 0)}"
                       for e in evaluations[:10]]
            context_parts.append("\n方案评估：\n" + "\n".join(e_lines))

        user_prompt = "\n".join(context_parts)

        result = await chat_completion(
            system_prompt=REPORT_SYSTEM,
            user_prompt=user_prompt,
            response_format=dict,
            model_id=self._get_model_id(),
        )
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                result = {"title": "创新分析报告", "summary": result, "sections": [], "recommendations": [], "topSolutions": []}
        return result if isinstance(result, dict) else {
            "title": "创新分析报告", "summary": "", "sections": [], "recommendations": [], "topSolutions": []
        }

    @staticmethod
    def _build_conflict_graph(ai_result: dict) -> dict:
        if not isinstance(ai_result, dict):
            logger.warning(f"_build_conflict_graph received non-dict: {type(ai_result).__name__}")
            ai_result = {}
        satellites = []
        colors = ["#60a5fa", "#4ade80", "#a78bfa", "#fbbf24"]
        positions = ["top", "right", "bottom", "left"]
        for i, s in enumerate(ai_result.get("satellites", [])):
            satellites.append({
                "id": f"s{i+1}",
                "label": s.get("label", ""),
                "sublabel": s.get("sublabel", ""),
                "description": s.get("description", ""),
                "type": "satellite",
                "color": colors[i % len(colors)],
                "position": positions[i % len(positions)],
            })

        return {
            "centerNode": {
                "id": "center",
                "label": "核心冲突",
                "description": ai_result.get("centerConflict", ""),
                "type": "center",
            },
            "satelliteNodes": satellites,
            "edges": [
                {"sourceId": "center", "targetId": s["id"], "label": "冲突" if i < 2 else ("关联" if i < 3 else "导致")}
                for i, s in enumerate(satellites)
            ],
            "principles": ai_result.get("principles", []),
            "patentKeywords": ai_result.get("patentKeywords", []),
        }
