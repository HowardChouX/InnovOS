"""
测试 evaluation_service.py — AI 四维方案评估服务

Mock chat_completion 和数据库，测试评估逻辑、错误处理、结果格式化。
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ── Fixtures ──

@pytest.fixture
def mock_db_solution_found(monkeypatch):
    """模拟数据库返回方案记录"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "title": "测试方案",
        "description": "方案描述",
        "principles": '["分割原理"]',
        "patent_references": '["CN12345"]',
        "task_title": "测试任务",
        "task_description": "任务描述内容",
    }
    mock_conn.execute.return_value = mock_cursor
    monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
    return mock_conn


@pytest.fixture
def mock_db_solution_not_found(monkeypatch):
    """模拟数据库未找到方案"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.execute.return_value = mock_cursor
    monkeypatch.setattr("app.database.get_db", lambda: mock_conn)
    return mock_conn


@pytest.fixture
def mock_ai_result():
    """模拟 AI 评估结果（新 chat_completion 返回信封，content 为 JSON 字符串）"""
    return {
        "content": json.dumps({
            "innovation": {"score": 85, "strengths": ["技术新颖"], "weaknesses": ["实现复杂"]},
            "feasibility": {"score": 70, "strengths": ["成本可控"], "weaknesses": []},
            "completeness": {"score": 90, "strengths": ["逻辑完整"], "weaknesses": ["缺少验证"]},
            "conversion": {"score": 75, "strengths": ["产业契合"], "weaknesses": []},
            "overall": 80,
            "recommendations": ["加强验证", "降低成本"],
        })
    }


# ── Tests ──

class TestEvaluateSolution:
    """测试 evaluate_solution 函数"""

    @pytest.mark.asyncio
    async def test_successful_evaluation(self, mock_db_solution_found, mock_ai_result, monkeypatch):
        """正常评估流程应返回正确格式的结果"""
        # Mock AI call
        mock_chat = AsyncMock(return_value=mock_ai_result)
        monkeypatch.setattr("app.algorithm.evaluation_service.chat_completion", mock_chat)

        from app.algorithm.evaluation_service import evaluate_solution

        result = await evaluate_solution(solution_id=1, user_id=1)

        # Verify result structure
        assert "scores" in result
        assert result["scores"]["innovation"] == 85
        assert result["scores"]["feasibility"] == 70
        assert result["scores"]["completeness"] == 90
        assert result["scores"]["conversion"] == 75
        assert result["overall"] == 80
        assert "strengths" in result
        assert "weaknesses" in result
        assert "recommendations" in result
        assert "加强验证" in result["recommendations"]

        # Verify strengths are merged from innovation + feasibility
        assert "技术新颖" in result["strengths"]
        assert "成本可控" in result["strengths"]

    @pytest.mark.asyncio
    async def test_stores_evaluation_in_db(self, mock_db_solution_found, mock_ai_result, monkeypatch):
        """评估结果应写入 evaluations 表"""
        mock_chat = AsyncMock(return_value=mock_ai_result)
        monkeypatch.setattr("app.algorithm.evaluation_service.chat_completion", mock_chat)

        mock_conn = mock_db_solution_found
        # Second get_db() call for storing
        mock_conn2 = MagicMock()
        monkeypatch.setattr("app.database.get_db", lambda: mock_conn2)

        from app.algorithm.evaluation_service import evaluate_solution

        await evaluate_solution(solution_id=1, user_id=1)

        # Verify INSERT was called
        insert_calls = [
            c for c in mock_conn2.execute.call_args_list
            if "INSERT INTO evaluations" in str(c)
        ]
        assert len(insert_calls) >= 1

        # Verify commit
        assert mock_conn2.commit.called

    @pytest.mark.asyncio
    async def test_solution_not_found(self, mock_db_solution_not_found, monkeypatch):
        """方案不存在时应抛出 ValueError"""
        from app.algorithm.evaluation_service import evaluate_solution

        with pytest.raises(ValueError, match="方案不存在"):
            await evaluate_solution(solution_id=999, user_id=1)

    @pytest.mark.asyncio
    async def test_ai_failure_propagates_as_runtime_error(
        self, mock_db_solution_found, monkeypatch
    ):
        """AI 调用失败时应抛出 RuntimeError"""
        mock_chat = AsyncMock(side_effect=RuntimeError("API key invalid"))
        monkeypatch.setattr("app.algorithm.evaluation_service.chat_completion", mock_chat)

        from app.algorithm.evaluation_service import evaluate_solution

        with pytest.raises(RuntimeError, match="AI评估失败"):
            await evaluate_solution(solution_id=1, user_id=1)

    @pytest.mark.asyncio
    async def test_ai_returns_partial_data(self, mock_db_solution_found, monkeypatch):
        """AI 返回不完整数据时应有默认值"""
        partial_result = {
            "innovation": {"score": 80, "strengths": [], "weaknesses": []},
            # missing feasibility, completeness, conversion
            "overall": 75,
            "recommendations": [],
        }
        mock_chat = AsyncMock(return_value={"content": json.dumps(partial_result)})
        monkeypatch.setattr("app.algorithm.evaluation_service.chat_completion", mock_chat)

        from app.algorithm.evaluation_service import evaluate_solution

        result = await evaluate_solution(solution_id=1, user_id=1)

        # Missing fields should default to 0 / empty lists
        assert result["scores"]["feasibility"] == 0
        assert result["scores"]["completeness"] == 0
        assert result["scores"]["conversion"] == 0
        assert result["strengths"] == []
        assert result["weaknesses"] == []

    @pytest.mark.asyncio
    async def test_correct_prompt_built(self, mock_db_solution_found, monkeypatch):
        """AI 调用应使用正确的新签名（user_id/purpose/messages）与 prompt 内容"""
        mock_chat = AsyncMock(return_value={
            "content": json.dumps({
                "innovation": {"score": 1, "strengths": [], "weaknesses": []},
                "feasibility": {"score": 1, "strengths": [], "weaknesses": []},
                "completeness": {"score": 1, "strengths": [], "weaknesses": []},
                "conversion": {"score": 1, "strengths": [], "weaknesses": []},
                "overall": 1,
                "recommendations": [],
            })
        })
        monkeypatch.setattr("app.algorithm.evaluation_service.chat_completion", mock_chat)

        from app.algorithm.evaluation_service import evaluate_solution

        await evaluate_solution(solution_id=1, user_id=1)

        # Verify chat_completion was called with expected args
        call_args = mock_chat.call_args[1]
        assert call_args["user_id"] == 1
        assert call_args["purpose"] == "evaluation"
        assert call_args["temperature"] == 0.3
        assert call_args["response_format"] == {"type": "json_object"}
        messages = call_args["messages"]
        assert messages[0]["role"] == "system"
        assert "专业" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "测试方案" in messages[1]["content"]
        assert "任务描述内容" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_db_closed_after_query(self, mock_db_solution_found, monkeypatch):
        """查询数据库后应关闭连接"""
        mock_chat = AsyncMock(return_value={
            "innovation": {"score": 1, "strengths": [], "weaknesses": []},
            "feasibility": {"score": 1, "strengths": [], "weaknesses": []},
            "completeness": {"score": 1, "strengths": [], "weaknesses": []},
            "conversion": {"score": 1, "strengths": [], "weaknesses": []},
            "overall": 1,
            "recommendations": [],
        })
        monkeypatch.setattr("app.algorithm.evaluation_service.chat_completion", mock_chat)

        mock_conn = mock_db_solution_found

        from app.algorithm.evaluation_service import evaluate_solution

        await evaluate_solution(solution_id=1, user_id=1)

        # close() should be called on the first DB connection
        assert mock_conn.close.called
