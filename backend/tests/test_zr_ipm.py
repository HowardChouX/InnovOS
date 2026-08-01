"""
测试 zr_ipm.py — ZR-IPM 算法引擎

Mock chat_completion（新签名：user_id/purpose/messages），测试分析、方案生成、
评估、报告生成流程。
"""

import json
import pytest
from unittest.mock import AsyncMock


# ── Helper ──

def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


def _env(obj) -> dict:
    """把已解析的 AI 结果包装成新 chat_completion 的返回信封。"""
    return {"content": json.dumps(obj, ensure_ascii=False)}


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine.analyze — 问题分析
# ═══════════════════════════════════════════════════════════════════

class TestAnalyze:
    def test_analyze_returns_conflict_graph(self, monkeypatch):
        """analyze 应返回冲突图谱结构"""
        ai_result = {
            "centerConflict": "性能与成本的矛盾",
            "satellites": [
                {"label": "性能", "sublabel": "提升", "description": "需要更高性能"},
            ],
            "principles": ["分割原理"],
            "patentKeywords": ["散热"],
        }
        mock_chat = AsyncMock(return_value=_env(ai_result))
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().analyze("手机发热问题", user_id=1))

        assert "centerNode" in result
        assert result["centerNode"]["description"] == "性能与成本的矛盾"
        assert "satelliteNodes" in result
        assert len(result["satelliteNodes"]) == 1
        assert result["satelliteNodes"][0]["label"] == "性能"
        assert "edges" in result
        assert "principles" in result
        assert result["principles"] == ["分割原理"]

    def test_analyze_string_result_parsed_as_json(self, monkeypatch):
        """AI 返回 JSON 字符串时，应解析为冲突图谱"""
        ai_result_str = json.dumps({
            "centerConflict": "冲突",
            "satellites": [],
            "principles": [],
            "patentKeywords": [],
        })
        mock_chat = AsyncMock(return_value={"content": ai_result_str})
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().analyze("test", user_id=1))
        assert result["centerNode"]["description"] == "冲突"

    def test_analyze_invalid_string_falls_back(self, monkeypatch):
        """AI 返回无法解析的内容时，应生成空图谱"""
        mock_chat = AsyncMock(return_value={"content": "this is not json at all"})
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().analyze("test", user_id=1))
        assert result["centerNode"]["description"] == ""

    def test_analyze_empty_result(self, monkeypatch):
        """AI 返回空内容时，图谱仍应生成但为空"""
        mock_chat = AsyncMock(return_value={"content": ""})
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().analyze("test", user_id=1))
        assert result["centerNode"]["description"] == ""
        assert result["satelliteNodes"] == []
        assert result["edges"] == []

    def test_analyze_passes_user_and_messages(self, monkeypatch):
        """analyze 应以新签名（user_id/purpose/messages）调用"""
        mock_chat = AsyncMock(return_value={
            "content": json.dumps({"centerConflict": "x", "satellites": [], "principles": [], "patentKeywords": []}),
        })
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        asyncio_run(ZRIPMEngine().analyze("test", user_id=7))

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["user_id"] == 7
        assert call_kwargs["purpose"] == "chat"
        assert call_kwargs["response_format"] == {"type": "json_object"}
        assert call_kwargs["messages"][0]["role"] == "system"
        assert "你是一个创新问题分析专家" in call_kwargs["messages"][0]["content"]
        assert call_kwargs["messages"][1] == {"role": "user", "content": "test"}


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine.generate_solutions — 方案生成
# ═══════════════════════════════════════════════════════════════════

class TestGenerateSolutions:
    def test_generates_with_innovations_and_patents(self, monkeypatch):
        """有创新方向和专利时应构建完整上下文"""
        mock_chat = AsyncMock(return_value=_env({
            "solutions": [
                {"title": "方案A", "description": "描述A", "direction": "方向1",
                 "principles": ["分割"], "referencedPatents": ["CN123"]},
            ]
        }))
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().generate_solutions(
            task_description="手机发热",
            innovations=[{"description": "热传导优化"}],
            patents=[{"title": "散热专利", "relevance": 0.8}],
            user_id=1,
        ))
        assert len(result) == 1
        assert result[0]["title"] == "方案A"

    def test_returns_list_when_result_is_list(self, monkeypatch):
        """AI 返回列表时，直接返回"""
        mock_chat = AsyncMock(return_value=_env([
            {"title": "方案X", "description": "desc"},
        ]))
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().generate_solutions(task_description="test", user_id=1))
        assert len(result) == 1

    def test_returns_empty_when_result_invalid(self, monkeypatch):
        """AI 返回非 dict/list 内容时，返回空列表"""
        mock_chat = AsyncMock(return_value={"content": "invalid"})
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().generate_solutions(task_description="test", user_id=1))
        assert result == []

    def test_patent_rating_scoring(self, monkeypatch):
        """测试专利评分算法的正确性"""
        mock_chat = AsyncMock(return_value=_env({"solutions": []}))
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        patents = [
            {"title": "P1", "relevance": 1.0},
            {"title": "P2", "relevance": 0.5},
        ]
        ratings = {0: 5, 1: 1}  # user ratings

        asyncio_run(ZRIPMEngine().generate_solutions(
            task_description="test",
            patents=patents,
            patent_ratings=ratings,
            user_id=1,
        ))

        call_kwargs = mock_chat.call_args[1]
        user_prompt = call_kwargs["messages"][1]["content"]

        # High-rated patent should be in "重点参考" section
        assert "★" in user_prompt
        assert "P1" in user_prompt

    def test_direction_patents_used(self, monkeypatch):
        """当 direction_patents 存在时，优先使用它而非 patents"""
        mock_chat = AsyncMock(return_value=_env({"solutions": []}))
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        asyncio_run(ZRIPMEngine().generate_solutions(
            task_description="test",
            patents=[{"title": "P1", "relevance": 1.0}],
            direction_patents={"方向1": ["专利X"]},
            user_id=1,
        ))

        call_kwargs = mock_chat.call_args[1]
        user_prompt = call_kwargs["messages"][1]["content"]

        # "方向-专利对应关系" should be in prompt
        assert "方向-专利对应关系" in user_prompt
        # "参考专利" should NOT be in prompt (skipped when direction_patents exists)
        assert "参考专利（按用户评分加权排序）" not in user_prompt


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine.evaluate — 方案评估
# ═══════════════════════════════════════════════════════════════════

class TestEvaluate:
    def test_evaluate_calls_chat_completion(self, monkeypatch):
        mock_chat = AsyncMock(return_value=_env({"overall": 85}))
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().evaluate("某方案描述", user_id=1))
        assert result["overall"] == 85

        # Verify prompt construction with the new signature
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["purpose"] == "evaluation"
        assert "评估" in call_kwargs["messages"][1]["content"]
        assert call_kwargs["response_format"] == {"type": "json_object"}


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine.generate_report — 报告生成
# ═══════════════════════════════════════════════════════════════════

class TestGenerateReport:
    def test_generates_report_with_all_sections(self, monkeypatch):
        mock_chat = AsyncMock(return_value=_env({
            "title": "分析报告",
            "summary": "摘要",
            "sections": [{"heading": "分析", "content": "内容"}],
            "recommendations": ["建议1"],
            "topSolutions": ["方案A"],
        }))
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        innovations = [{"description": "方向1"}]
        patents = [{"title": "专利1"}]
        solutions = [{"title": "方案A", "description": "描述"}]
        evaluations = [{"solution_title": "方案A", "evaluation": {"overall": 85}}]

        result = asyncio_run(ZRIPMEngine().generate_report(
            task_description="问题描述", innovations=innovations,
            patents=patents, solutions=solutions, evaluations=evaluations,
            user_id=1,
        ))
        assert result["title"] == "分析报告"
        assert result["summary"] == "摘要"
        assert len(result["sections"]) == 1

    def test_report_fallback_on_string_result(self, monkeypatch):
        """AI 返回无法解析的内容时，应生成默认报告"""
        mock_chat = AsyncMock(return_value={"content": "this is not json"})
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().generate_report(
            task_description="test", innovations=[], patents=[], solutions=[], evaluations=[],
            user_id=1,
        ))
        assert result["title"] == "创新分析报告"
        assert isinstance(result["sections"], list)
        assert isinstance(result["recommendations"], list)

    def test_report_context_built_correctly(self, monkeypatch):
        mock_chat = AsyncMock(return_value=_env({
            "title": "R", "summary": "S", "sections": [], "recommendations": [], "topSolutions": [],
        }))
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        asyncio_run(ZRIPMEngine().generate_report(
            task_description="手机发热",
            innovations=[{"description": "散热优化"}],
            patents=[{"title": "散热专利"}],
            solutions=[{"title": "方案A", "description": "使用均热板"}],
            evaluations=[{"solution_title": "方案A", "evaluation": {"overall": 90}}],
            user_id=1,
        ))

        call_kwargs = mock_chat.call_args[1]
        user_prompt = call_kwargs["messages"][1]["content"]
        assert "手机发热" in user_prompt
        assert "散热优化" in user_prompt
        assert "散热专利" in user_prompt
        assert "方案A" in user_prompt


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine._build_conflict_graph — 冲突图谱构建
# ═══════════════════════════════════════════════════════════════════

class TestBuildConflictGraph:
    def test_builds_from_ai_result(self):
        from app.algorithm.zr_ipm import ZRIPMEngine

        ai_result = {
            "centerConflict": "核心冲突",
            "satellites": [
                {"label": "L1", "sublabel": "S1", "description": "D1"},
                {"label": "L2", "sublabel": "S2", "description": "D2"},
                {"label": "L3", "sublabel": "S3", "description": "D3"},
                {"label": "L4", "sublabel": "S4", "description": "D4"},
                {"label": "L5", "sublabel": "S5", "description": "D5"},
            ],
            "principles": ["P1"],
            "patentKeywords": ["KW"],
        }

        result = ZRIPMEngine._build_conflict_graph(ai_result)

        assert result["centerNode"]["description"] == "核心冲突"
        assert len(result["satelliteNodes"]) == 5
        assert len(result["edges"]) == 5

        # Colors cycle for 4+ satellites
        assert result["satelliteNodes"][4]["color"] == "#60a5fa"  # cycle back

    def test_non_dict_input(self):
        """非 dict 输入应返回空图谱"""
        from app.algorithm.zr_ipm import ZRIPMEngine

        result = ZRIPMEngine._build_conflict_graph({"invalid": True})  # type: ignore[arg-type]
        assert result["centerNode"]["description"] == ""
        assert result["satelliteNodes"] == []

    def test_empty_satellites(self):
        from app.algorithm.zr_ipm import ZRIPMEngine

        result = ZRIPMEngine._build_conflict_graph({"centerConflict": "test"})
        assert result["satelliteNodes"] == []
        assert result["edges"] == []
