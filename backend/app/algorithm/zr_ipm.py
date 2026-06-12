"""
ZR-IPM (智融创新问题映射) 算法引擎

四层架构:
  1. 多维语义解析 → 提取问题核心要素
  2. 创新问题分类 → 识别问题类型与矛盾
  3. 专利RAG增强 → 检索相似专利路径
  4. 结构化建模 → 输出冲突图谱 + 创新原理
"""

import json
from .ai_client import chat_completion
from .model_resolver import model_resolver

SYSTEM_PROMPT = """你是一个创新问题分析专家。分析用户的技术问题，输出JSON：
{
  "centerConflict": "核心矛盾描述",
  "satellites": [
    {"label": "方面名", "sublabel": "方向", "description": "详细描述"}
  ],
  "principles": ["推荐创新原理名"],
  "patentKeywords": ["检索关键词"]
}"""

SOLUTION_PROMPT = "为以下问题生成3个创新解决方案，返回JSON数组"

SOLUTION_SYSTEM = "你是一个创新方案专家。返回JSON数组，每个元素包含 title, description, principles(数组), confidenceScore(0-100)"

EVALUATE_PROMPT = "评估以下创新方案，返回四维评分JSON"

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
                print(f"[WARN] AI returned string, not dict: {result[:200]}", flush=True)
                result = {}
        return self._build_conflict_graph(result)

    async def generate_solutions(self, task_description: str) -> list[dict]:
        """生成解决方案"""
        result = await chat_completion(
            system_prompt=SOLUTION_SYSTEM,
            user_prompt=f"{SOLUTION_PROMPT}：\n{task_description}",
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

    @staticmethod
    def _build_conflict_graph(ai_result: dict) -> dict:
        if not isinstance(ai_result, dict):
            print(f"[WARN] _build_conflict_graph received non-dict: {type(ai_result).__name__}", flush=True)
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
