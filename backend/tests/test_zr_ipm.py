"""
测试 zr_ipm.py — ZR-IPM 算法引擎

Mock chat_completion 和 model_resolver，测试分析、方案生成、评估、报告生成流程。
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ── Helper ──

def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def mock_model_resolver_settings(monkeypatch):
    """Mock model_resolver.get_assigned_settings to return a known chat model"""
    monkeypatch.setattr(
        "app.algorithm.zr_ipm.model_resolver.get_assigned_settings",
        lambda: {"chat_model": "silicon:deepseek-v3"},
    )


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
        mock_chat = AsyncMock(return_value=ai_result)
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().analyze("手机发热问题"))

        assert "centerNode" in result
        assert result["centerNode"]["description"] == "性能与成本的矛盾"
        assert "satelliteNodes" in result
        assert len(result["satelliteNodes"]) == 1
        assert result["satelliteNodes"][0]["label"] == "性能"
        assert "edges" in result
        assert "principles" in result
        assert result["principles"] == ["分割原理"]

    def test_analyze_string_result_parsed_as_json(self, monkeypatch):
        """AI 返回字符串时，应尝试 JSON 解析"""
        ai_result_str = json.dumps({
            "centerConflict": "冲突",
            "satellites": [],
            "principles": [],
            "patentKeywords": [],
        })
        mock_chat = AsyncMock(return_value=ai_result_str)
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().analyze("test"))
        assert result["centerNode"]["description"] == "冲突"

    def test_analyze_invalid_string_falls_back(self, monkeypatch):
        """AI 返回无法解析的字符串时，应生成空图谱"""
        mock_chat = AsyncMock(return_value="this is not json at all")
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().analyze("test"))
        assert result["centerNode"]["description"] == ""

    def test_analyze_empty_result(self, monkeypatch):
        """AI 返回空 dict 时，图谱仍应生成但为空"""
        mock_chat = AsyncMock(return_value={})
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().analyze("test"))
        assert result["centerNode"]["description"] == ""
        assert result["satelliteNodes"] == []
        assert result["edges"] == []

    def test_analyze_model_id_resolved(self, monkeypatch):
        """analyze 应通过 model_id 调用"""
        mock_chat = AsyncMock(return_value={
            "centerConflict": "x", "satellites": [], "principles": [], "patentKeywords": [],
        })
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        asyncio_run(ZRIPMEngine().analyze("test"))

        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs["model_id"] == "silicon:deepseek-v3"
        assert call_kwargs["response_format"] is dict


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine.generate_solutions — 方案生成
# ═══════════════════════════════════════════════════════════════════

class TestGenerateSolutions:
    def test_generates_with_innovations_and_patents(self, monkeypatch):
        """有创新方向和专利时应构建完整上下文"""
        mock_chat = AsyncMock(return_value={
            "solutions": [
                {"title": "方案A", "description": "描述A", "direction": "方向1",
                 "principles": ["分割"], "referencedPatents": ["CN123"]},
            ]
        })
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().generate_solutions(
            task_description="手机发热",
            innovations=[{"description": "热传导优化"}],
            patents=[{"title": "散热专利", "relevance": 0.8}],
        ))
        assert len(result) == 1
        assert result[0]["title"] == "方案A"

    def test_returns_list_when_result_is_list(self, monkeypatch):
        """AI 返回列表时，直接返回"""
        mock_chat = AsyncMock(return_value=[
            {"title": "方案X", "description": "desc"},
        ])
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().generate_solutions(task_description="test"))
        assert len(result) == 1

    def test_returns_empty_when_result_invalid(self, monkeypatch):
        """AI 返回非 dict/list 时，返回空列表"""
        mock_chat = AsyncMock(return_value="invalid")
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().generate_solutions(task_description="test"))
        assert result == []

    def test_patent_rating_scoring(self, monkeypatch):
        """测试专利评分算法的正确性"""
        mock_chat = AsyncMock(return_value=[])
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
        ))

        call_kwargs = mock_chat.call_args[1]
        user_prompt = call_kwargs["user_prompt"]

        # High-rated patent should be in "重点参考" section
        assert "★" in user_prompt
        assert "P1" in user_prompt

    def test_direction_patents_used(self, monkeypatch):
        """当 direction_patents 存在时，优先使用它而非 patents"""
        mock_chat = AsyncMock(return_value=[])
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        asyncio_run(ZRIPMEngine().generate_solutions(
            task_description="test",
            patents=[{"title": "P1", "relevance": 1.0}],
            direction_patents={"方向1": ["专利X"]},
        ))

        call_kwargs = mock_chat.call_args[1]
        user_prompt = call_kwargs["user_prompt"]

        # "方向-专利对应关系" should be in prompt
        assert "方向-专利对应关系" in user_prompt
        # "参考专利" should NOT be in prompt (skipped when direction_patents exists)
        assert "参考专利（按用户评分加权排序）" not in user_prompt


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine.evaluate — 方案评估
# ═══════════════════════════════════════════════════════════════════

class TestEvaluate:
    def test_evaluate_calls_chat_completion(self, monkeypatch):
        mock_chat = AsyncMock(return_value={"overall": 85})
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().evaluate("某方案描述"))
        assert result["overall"] == 85

        # Verify prompt construction
        call_kwargs = mock_chat.call_args[1]
        assert "评估" in call_kwargs["user_prompt"]
        assert call_kwargs["response_format"] is dict
        assert call_kwargs["model_id"] == "silicon:deepseek-v3"


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine.generate_report — 报告生成
# ═══════════════════════════════════════════════════════════════════

class TestGenerateReport:
    def test_generates_report_with_all_sections(self, monkeypatch):
        mock_chat = AsyncMock(return_value={
            "title": "分析报告",
            "summary": "摘要",
            "sections": [{"heading": "分析", "content": "内容"}],
            "recommendations": ["建议1"],
            "topSolutions": ["方案A"],
        })
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        innovations = [{"description": "方向1"}]
        patents = [{"title": "专利1"}]
        solutions = [{"title": "方案A", "description": "描述"}]
        evaluations = [{"solution_title": "方案A", "evaluation": {"overall": 85}}]

        result = asyncio_run(ZRIPMEngine().generate_report(
            task_description="问题描述", innovations=innovations,
            patents=patents, solutions=solutions, evaluations=evaluations,
        ))
        assert result["title"] == "分析报告"
        assert result["summary"] == "摘要"
        assert len(result["sections"]) == 1

    def test_report_fallback_on_string_result(self, monkeypatch):
        """AI 返回字符串时，应尝试解析 JSON，失败时生成默认报告"""
        mock_chat = AsyncMock(return_value="this is not json")
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        result = asyncio_run(ZRIPMEngine().generate_report(
            task_description="test", innovations=[], patents=[], solutions=[], evaluations=[],
        ))
        assert result["title"] == "创新分析报告"
        assert isinstance(result["sections"], list)
        assert isinstance(result["recommendations"], list)

    def test_report_context_built_correctly(self, monkeypatch):
        mock_chat = AsyncMock(return_value={
            "title": "R", "summary": "S", "sections": [], "recommendations": [], "topSolutions": [],
        })
        monkeypatch.setattr("app.algorithm.zr_ipm.chat_completion", mock_chat)

        from app.algorithm.zr_ipm import ZRIPMEngine

        asyncio_run(ZRIPMEngine().generate_report(
            task_description="手机发热",
            innovations=[{"description": "散热优化"}],
            patents=[{"title": "散热专利"}],
            solutions=[{"title": "方案A", "description": "使用均热板"}],
            evaluations=[{"solution_title": "方案A", "evaluation": {"overall": 90}}],
        ))

        call_kwargs = mock_chat.call_args[1]
        user_prompt = call_kwargs["user_prompt"]
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


# ═══════════════════════════════════════════════════════════════════
# ZRIPMEngine._get_model_id — 模型 ID 解析
# ═══════════════════════════════════════════════════════════════════

class TestGetModelId:
    def test_returns_chat_model(self, monkeypatch):
        monkeypatch.setattr(
            "app.algorithm.zr_ipm.model_resolver.get_assigned_settings",
            lambda: {"chat_model": "openai:gpt-4"},
        )
        from app.algorithm.zr_ipm import ZRIPMEngine
        assert ZRIPMEngine._get_model_id() == "openai:gpt-4"

    def test_returns_empty_when_not_set(self, monkeypatch):
        monkeypatch.setattr(
            "app.algorithm.zr_ipm.model_resolver.get_assigned_settings",
            lambda: {"chat_model": None},
        )
        from app.algorithm.zr_ipm import ZRIPMEngine
        assert ZRIPMEngine._get_model_id() == ""
