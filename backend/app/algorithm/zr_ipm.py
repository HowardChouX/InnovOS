"""
ZR-IPM (智融创新问题映射) 算法引擎

四层架构:
  1. 多维语义解析 → 提取问题核心要素
  2. 创新问题分类 → 识别问题类型与矛盾
  3. 专利RAG增强 → 检索相似专利路径
  4. 结构化建模 → 输出冲突图谱 + TRIZ原理

需要配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量。
"""

from .ai_client import ai_available, chat_completion

SYSTEM_PROMPT = """你是一个TRIZ创新问题分析专家。分析用户的技术问题，输出JSON：
{
  "centerConflict": "核心矛盾描述",
  "satellites": [
    {"label": "方面名", "sublabel": "方向", "description": "详细描述"}
  ],
  "principles": ["推荐TRIZ原理名"],
  "patentKeywords": ["检索关键词"]
}"""


class ZRIPMEngine:

    def analyze(self, task_description: str) -> dict | None:
        if not ai_available():
            return None
        return self._ai_analyze(task_description)

    def generate_solutions(self, task_description: str) -> list[dict] | None:
        if not ai_available():
            return None
        return self._ai_solutions(task_description)

    def evaluate(self, solution_description: str) -> dict | None:
        if not ai_available():
            return None
        return self._ai_evaluate(solution_description)

    async def _ai_analyze(self, description: str) -> dict:
        result = await chat_completion(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=description,
            response_format=dict,
        )
        return self._build_conflict_graph(result)

    async def _ai_solutions(self, description: str) -> list[dict]:
        prompt = f"为以下问题生成3个创新解决方案，返回JSON数组：\n{description}"
        result = await chat_completion(
            system_prompt="你是一个创新方案专家。返回JSON数组，每个元素包含 title, description, principles(数组), confidenceScore(0-100)。",
            user_prompt=prompt,
            response_format=dict,
        )
        if isinstance(result, dict) and "solutions" in result:
            return result["solutions"]
        if isinstance(result, list):
            return result
        return []

    async def _ai_evaluate(self, description: str) -> dict:
        prompt = f"评估以下创新方案，返回四维评分JSON：\n{description}"
        return await chat_completion(
            system_prompt="你是一个创新评估专家。返回JSON: scores(innovation/feasibility/completeness/conversion 0-100), overall, grade(A+/A/B+/B/C), strengths(数组), weaknesses(数组), recommendations(数组)。",
            user_prompt=prompt,
            response_format=dict,
        )

    @staticmethod
    def _build_conflict_graph(ai_result: dict) -> dict:
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
        }
