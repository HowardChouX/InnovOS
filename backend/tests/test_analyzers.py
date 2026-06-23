"""
测试 analyzers 包 — DemandPortraitAnalyzer 和 ProblemModelingAnalyzer

Mock AIBase/AIAnalyzer 的子类，验证编排、并行执行、异常容忍、聚合逻辑。
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ═══════════════════════════════════════════════════════════════════
# 共享 Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_ai_base():
    """Mock AIBase 实例"""
    ai = MagicMock()
    ai.call_ai_async = AsyncMock()
    return ai


class AsyncIterator:
    """用于 asyncio.gather 中可控 side_effect 的辅助"""
    def __init__(self, items):
        self.items = list(items)
        self.idx = 0

    async def next(self):
        if self.idx >= len(self.items):
            raise StopAsyncIteration()
        val = self.items[self.idx]
        self.idx += 1
        if isinstance(val, Exception):
            raise val
        return val


# ═══════════════════════════════════════════════════════════════════
# DemandPortraitAnalyzer
# ═══════════════════════════════════════════════════════════════════

class TestDemandPortraitAnalyzer:
    """测试需求画像编排器"""

    def test_init_creates_sub_analyzers(self, mock_ai_base):
        from app.algorithm.analyzers.demand_portrait import DemandPortraitAnalyzer

        dp = DemandPortraitAnalyzer(mock_ai_base)
        assert dp.resource_analyzer is not None
        assert dp.ifr_generator is not None
        assert dp.nine_screens is not None
        assert dp.goldfish is not None
        assert dp.stc is not None

    @pytest.mark.asyncio
    async def test_analyze_parallel_execution(self, mock_ai_base):
        """analyze 应并行运行 5 个子分析器并汇总需求"""
        # Provide enough results: 5 sub-analyzers + 1 aggregation
        mock_ai_base.call_ai_async.side_effect = [
            {"substance_resources": [], "energy_resources": [], "summary": "r"},
            {"ifr_1_statement": "test", "key_parameters": [], "measurement_criteria": []},
            {"screens": {}, "insights": [], "contradictions": []},
            {"fantasy_solution": "test", "final_solution": "test", "iterations": [],
             "achievable_parts": [], "breakthrough_parts": [], "constraints": [], "insights": []},
            {"size_zero": "", "size_infinite": "", "time_zero": "", "time_infinite": "",
             "cost_zero": "", "cost_infinite": "", "insights": [], "contradictions": []},
            {"demands": [{"id": "d1", "description": "需求1"}]},
        ]

        from app.algorithm.analyzers.demand_portrait import DemandPortraitAnalyzer

        dp = DemandPortraitAnalyzer(mock_ai_base)
        result = await dp.analyze("手机发热问题")

        for key in ("resource_analysis", "ideal_final_result", "nine_screens",
                     "goldfish", "stc"):
            assert key in result
        assert "demands" in result

    @pytest.mark.asyncio
    async def test_sub_analyzer_failure_does_not_crash(self, mock_ai_base):
        """某个子分析器失败不应影响整体"""
        mock_ai_base.call_ai_async.side_effect = [
            {"substance_resources": [], "summary": "resource ok"},
            Exception("IFR failed"),
            {"screens": {}, "insights": [], "contradictions": []},
            {"fantasy_solution": "t", "final_solution": "t", "iterations": [],
             "achievable_parts": [], "breakthrough_parts": [], "constraints": [], "insights": []},
            {"size_zero": "", "size_infinite": "", "time_zero": "", "time_infinite": "",
             "cost_zero": "", "cost_infinite": "", "insights": [], "contradictions": []},
            {"demands": [{"id": "d1", "description": "需求1"}]},
        ]

        from app.algorithm.analyzers.demand_portrait import DemandPortraitAnalyzer

        dp = DemandPortraitAnalyzer(mock_ai_base)
        result = await dp.analyze("测试问题")

        assert result["resource_analysis"] is not None
        assert result["ideal_final_result"] is None  # IFR failed
        assert result["nine_screens"] is not None
        assert len(result["demands"]) == 1

    @pytest.mark.asyncio
    async def test_aggregate_demands(self, mock_ai_base):
        mock_ai_base.call_ai_async.return_value = {
            "demands": [
                {"id": "d1", "source": "资源分析", "category": "功能需求",
                 "description": "不发烫", "priority": 0.9},
                {"id": "d2", "source": "IFR", "category": "性能需求",
                 "description": "更流畅", "priority": 0.7},
            ]
        }

        from app.algorithm.analyzers.demand_portrait import DemandPortraitAnalyzer

        dp = DemandPortraitAnalyzer(mock_ai_base)
        demands = await dp._aggregate_demands(
            "问题", {"summary": "r"}, {"ifr_1_statement": "i"},
            {"screens": {}}, {"fantasy_solution": "g"}, {"insights": ["s"]},
        )

        assert len(demands) == 2
        assert demands[0]["description"] == "不发烫"
        assert demands[0].get("user_rating") is None

    @pytest.mark.asyncio
    async def test_aggregate_fills_defaults(self, mock_ai_base):
        mock_ai_base.call_ai_async.return_value = {
            "demands": [
                {"description": "只有描述"},
            ]
        }
        from app.algorithm.analyzers.demand_portrait import DemandPortraitAnalyzer

        dp = DemandPortraitAnalyzer(mock_ai_base)
        demands = await dp._aggregate_demands("问题", None, None, None, None, None)

        assert len(demands) == 1
        assert demands[0]["id"] == "d1"
        assert demands[0]["source"] == "综合分析"
        assert demands[0]["category"] == "功能需求"
        assert demands[0]["priority"] == 0.5
        assert demands[0]["user_rating"] is None

    @pytest.mark.asyncio
    async def test_aggregate_failure_returns_empty(self, mock_ai_base):
        mock_ai_base.call_ai_async.return_value = None

        from app.algorithm.analyzers.demand_portrait import DemandPortraitAnalyzer

        dp = DemandPortraitAnalyzer(mock_ai_base)
        demands = await dp._aggregate_demands("问题", None, None, None, None, None)
        assert demands == []

    @pytest.mark.asyncio
    async def test_aggregate_non_dict_demands_returns_empty(self, mock_ai_base):
        mock_ai_base.call_ai_async.return_value = {"demands": "not a list"}

        from app.algorithm.analyzers.demand_portrait import DemandPortraitAnalyzer

        dp = DemandPortraitAnalyzer(mock_ai_base)
        demands = await dp._aggregate_demands("问题", None, None, None, None, None)
        assert demands == []


# ═══════════════════════════════════════════════════════════════════
# ProblemModelingAnalyzer
# ═══════════════════════════════════════════════════════════════════

class TestProblemModelingAnalyzer:
    """测试问题建模编排器"""

    def test_init_creates_sub_analyzers(self, mock_ai_base):
        from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

        pm = ProblemModelingAnalyzer(mock_ai_base)
        assert pm.resource_analyzer is not None
        assert pm.evolution_analyzer is not None
        assert pm.sufield_analyzer is not None

    @pytest.mark.asyncio
    async def test_analyze_runs_parallel_analyzers(self, mock_ai_base):
        """analyze 应并行运行所有子分析器并生成创新方向"""

        # Provide mock results for all AI calls in the expected order of consumption
        # ResourceAnalyzer: 1 call → needs all resource keys + default processing
        resource_ai_result = {"substance_resources": [], "energy_resources": [],
                              "functional_resources": [], "information_resources": [],
                              "time_resources": [], "space_resources": [],
                              "system_resources": [], "priority_resources": [],
                              "summary": "资源分析完成"}
        # EvolutionAnalyzer: 1 call
        evolution_ai_result = {"s_curve_stage": "growth", "law_analysis": {}, "conclusion": ""}
        # SuFieldAnalyzer: 1 call
        sufield_ai_result = {"s1": "A", "s2": "B", "f": "mechanical",
                             "problem_type": "", "effect_type": ""}
        # simple_function_analysis: 1 call
        function_result = {"system_components": [{"name": "CPU", "description": "处理器"}],
                           "supersystem_components": [], "key_interactions": []}
        # simple_root_cause: 1 call
        root_cause_result = {"root_causes": [{"id": "rc1", "text": "过热"}],
                             "key_insights": [], "initial_defect": "发热"}
        # Trimming analysis: 1 call
        trimming_result = {"trimming_candidates": [], "summary": "无需裁剪"}
        # Innovation generation: 1 call
        innovation_result = {"innovations": [
            {"source_analyzer": "资源分析", "description": "热传导优化",
             "principle": "局部质量", "expected_effect": "降温"},
        ]}

        async def side_effect_fn(*args, **kwargs):
            """Return based on prompt content so concurrent order doesn't matter"""
            user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
            if "资源分析" in str(kwargs.get("logger_prefix", "")):
                return resource_ai_result
            if "进化趋势" in str(kwargs.get("logger_prefix", "")):
                return evolution_ai_result
            if "物-场" in str(kwargs.get("logger_prefix", "")):
                return sufield_ai_result
            if "功能分析" in str(kwargs.get("logger_prefix", "")):
                return function_result
            if "因果链" in str(kwargs.get("logger_prefix", "")):
                return root_cause_result
            if "裁剪分析" in str(kwargs.get("logger_prefix", "")):
                return trimming_result
            if "创新方向" in str(kwargs.get("logger_prefix", "")):
                return innovation_result
            # Try simple_function_analysis / simple_root_cause which use hardcoded prompts
            if "系统组件" in user_prompt or "超系统组件" in user_prompt:
                return function_result
            if "根因" in user_prompt or "根本原因" in user_prompt:
                return root_cause_result
            if "裁剪" in user_prompt:
                return trimming_result
            return {"innovations": []}

        mock_ai_base.call_ai_async.side_effect = side_effect_fn

        from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

        pm = ProblemModelingAnalyzer(mock_ai_base)
        result = await pm.analyze("手机发热问题")

        assert result["resource_analysis"] is not None
        assert result["evolution_trend"] is not None
        assert result["sufield_analysis"] is not None
        assert result["function_analysis"] is not None
        assert result["root_cause_analysis"] is not None
        assert len(result["innovations"]) == 1

    @pytest.mark.asyncio
    async def test_analyzer_failure_returns_empty_dict(self, mock_ai_base):
        """子分析器失败时返回空 dict，创新方向生成应返回空列表"""
        async def side_effect_fn(*args, **kwargs):
            prefix = str(kwargs.get("logger_prefix", ""))
            user_prompt = args[1] if len(args) > 1 else ""

            # All sub-analyzers fail
            if prefix not in ("创新方向生成",):
                raise Exception(f"Analyzer failed: {prefix}")
            # Return valid data for innovation generation
            return {"innovations": []}

        mock_ai_base.call_ai_async.side_effect = side_effect_fn

        from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

        pm = ProblemModelingAnalyzer(mock_ai_base)
        result = await pm.analyze("测试")

        assert result["resource_analysis"] == {}
        assert result["evolution_trend"] == {}
        assert result["sufield_analysis"] == {}
        assert isinstance(result.get("function_analysis"), dict)
        assert isinstance(result.get("root_cause_analysis"), dict)
        assert result["innovations"] == []

    @pytest.mark.asyncio
    async def test_trimming_with_empty_components(self, mock_ai_base):
        """没有系统组件时裁剪分析仍会调用 AI，返回结果"""
        async def side_effect_fn(*args, **kwargs):
            prefix = str(kwargs.get("logger_prefix", ""))
            user_prompt = args[1] if len(args) > 1 else ""

            # Order matters — more specific checks first
            if "裁剪分析" in prefix:
                return {"trimming_candidates": [], "summary": "无组件可裁剪"}
            if "创新方向" in prefix:
                return {"innovations": [
                    {"source_analyzer": "资源分析", "description": "方向1",
                     "principle": "分割", "expected_effect": "效果1"},
                ]}
            if "资源" in prefix:
                return {"substance_resources": [], "energy_resources": [],
                        "functional_resources": [], "information_resources": [],
                        "time_resources": [], "space_resources": [],
                        "system_resources": [], "priority_resources": [], "summary": "r"}
            if "进化" in prefix:
                return {"s_curve_stage": "growth", "law_analysis": {}, "conclusion": ""}
            if "物-场" in prefix:
                return {"s1": "A", "s2": "B", "f": "mechanical", "problem_type": "", "effect_type": ""}
            if "功能分析" in prefix or ("系统组件" in user_prompt):
                return {"system_components": [], "supersystem_components": [], "key_interactions": []}
            if "因果链" in prefix or ("根因" in user_prompt):
                return {"root_causes": [], "key_insights": [], "initial_defect": ""}
            return {"innovations": []}

        mock_ai_base.call_ai_async.side_effect = side_effect_fn

        from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

        pm = ProblemModelingAnalyzer(mock_ai_base)
        result = await pm.analyze("测试")

        # Trimming IS still called (code doesn't check for empty components before calling AI)
        # It just passes empty lists in the prompt
        assert result["trimming_analysis"] == {"trimming_candidates": [], "summary": "无组件可裁剪"}
        assert len(result["innovations"]) == 1

    @pytest.mark.asyncio
    async def test_generate_innovations_builds_context(self, mock_ai_base):
        mock_ai_base.call_ai_async.return_value = {
            "innovations": [
                {"source_analyzer": "资源分析", "description": "散热优化",
                 "principle": "分割", "expected_effect": "降温"},
            ]
        }

        from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

        pm = ProblemModelingAnalyzer(mock_ai_base)
        innovations = await pm._generate_innovations(
            "手机发热",
            {"summary": "资源丰富"},
            {"s_curve_stage": "成长期"},
            {"s1": "A"},
            {"system_components": []},
            {"root_causes": [{"id": "rc1", "text": "过热"}]},
            {"trimming_candidates": [{"component": "风扇", "reason": "可替代"}]},
            [{"description": "不发烫", "priority": 0.9}],
        )

        assert len(innovations) == 1
        assert innovations[0]["id"] == "in1"
        assert innovations[0].get("user_rating") is None

        call_args = mock_ai_base.call_ai_async.call_args
        # Positional args: system_prompt, user_prompt
        user_prompt = call_args[0][1] if len(call_args[0]) > 1 else ""
        assert "资源分析" in user_prompt
        assert "进化趋势分析" in user_prompt
        assert "用户需求评分参考" in user_prompt

    @pytest.mark.asyncio
    async def test_generate_innovations_sets_defaults(self, mock_ai_base):
        mock_ai_base.call_ai_async.return_value = {
            "innovations": [
                {"description": "只有描述"},
                {},
            ]
        }
        from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

        pm = ProblemModelingAnalyzer(mock_ai_base)
        innovations = await pm._generate_innovations("问题", None, None, None, None, None, None, None)

        assert len(innovations) == 2
        assert innovations[0]["id"] == "in1"
        assert innovations[0]["source_analyzer"] == "综合分析"
        assert innovations[0]["principle"] == ""
        assert innovations[0]["expected_effect"] == ""
        assert innovations[0].get("user_rating") is None
        assert innovations[1]["id"] == "in2"

    @pytest.mark.asyncio
    async def test_generate_innovations_non_dict_returns_empty(self, mock_ai_base):
        mock_ai_base.call_ai_async.return_value = None

        from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

        pm = ProblemModelingAnalyzer(mock_ai_base)
        innovations = await pm._generate_innovations("问题", None, None, None, None, None, None, None)
        assert innovations == []

    @pytest.mark.asyncio
    async def test_generate_innovations_non_list_returns_empty(self, mock_ai_base):
        mock_ai_base.call_ai_async.return_value = {"innovations": "not a list"}

        from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

        pm = ProblemModelingAnalyzer(mock_ai_base)
        innovations = await pm._generate_innovations("问题", None, None, None, None, None, None, None)
        assert innovations == []
