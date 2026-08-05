"""
本地专利检索服务测试

覆盖：patent_service（工作流检索、详情）、api/patents（搜索、详情接口）
策略：patch db_session / db_session 内的连接对象，避免真实数据库
"""

import json
import pytest
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════
#  测试数据辅助
# ═══════════════════════════════════════════════════════════════

def _row(**overrides) -> dict:
    """模拟 patents 表的一行"""
    base = {
        "id": 1,
        "title": "电池散热结构",
        "abstract": "一种新型电池散热结构",
        "applicants": json.dumps(["华为"]),
        "inventors": json.dumps(["张三"]),
        "ipc_codes": json.dumps(["H01M"]),
        "filing_date": "2024-01-01",
        "publication_date": "2024-06-01",
        "patent_number": "CN111",
        "publication_number": "CN111A",
        "relevance_score": 90,
        "claims": "权利要求",
        "description": "说明书",
    }
    base.update(overrides)
    return base


class _FakeCursor:
    """按顺序返回预设的 fetchone/fetchall 结果"""

    def __init__(self, fetchall_results=None, fetchone_results=None):
        self._fetchall = list(fetchall_results or [])
        self._fetchone = list(fetchone_results or [])
        self.executed: list[tuple[str, list]] = []

    def execute(self, sql, params=None):
        self.executed.append((sql, list(params or [])))
        return self

    def fetchall(self):
        return self._fetchall.pop(0) if self._fetchall else []

    def fetchone(self):
        return self._fetchone.pop(0) if self._fetchone else None


class _FakeSession:
    """模拟 db_session 上下文：db.execute(...).fetchall()/fetchone()"""

    def __init__(self, cursor):
        self.cursor = cursor
        self.committed = False

    def execute(self, sql, params=None):
        return self.cursor.execute(sql, params)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


def _patch_session(cursor):
    """patch app.algorithm.patent_service.db_session 返回假连接"""
    session = _FakeSession(cursor)

    class _CM:
        def __enter__(self):
            return session

        def __exit__(self, *args):
            return False

    return patch("app.algorithm.patent_service.db_session", lambda: _CM())


# ═══════════════════════════════════════════════════════════════
#  extract_keywords
# ═══════════════════════════════════════════════════════════════

class TestExtractKeywords:

    def test_extract_tech_keywords(self):
        """从描述中提取技术关键词"""
        from app.algorithm.patent_service import extract_keywords
        keywords = extract_keywords("利用石墨烯材料进行电池散热")
        # jieba 分词：复合词可能切成更短词元（石墨烯→石墨/烯），均为有效检索词
        assert any(kw in keywords for kw in ("石墨烯", "石墨"))
        assert "电池" in keywords or "散热" in keywords

    def test_extract_empty_input(self):
        """空描述返回空列表"""
        from app.algorithm.patent_service import extract_keywords
        assert extract_keywords("") == []
        assert extract_keywords("   ") == []

    def test_extract_max_keywords(self):
        """限制返回关键词数量"""
        from app.algorithm.patent_service import extract_keywords
        keywords = extract_keywords("电池散热石墨烯芯片半导体传感器", max_keywords=3)
        assert len(keywords) <= 3

    def test_extract_filters_stop_words(self):
        """过滤停用词"""
        from app.algorithm.patent_service import extract_keywords
        keywords = extract_keywords("这是一个可以通过采用石墨烯的方法")
        assert "通过" not in keywords
        assert "采用" not in keywords
        assert "方法" not in keywords

    def test_extract_english_terms(self):
        """提取英文/数字术语"""
        from app.algorithm.patent_service import extract_keywords
        keywords = extract_keywords("使用LiFePO4电池进行Energy存储")
        assert any(kw in keywords for kw in ["LiFePO4", "Energy"])


# ═══════════════════════════════════════════════════════════════
#  patent_search（工作流检索，纯本地）
# ═══════════════════════════════════════════════════════════════

class TestPatentSearch:

    def test_search_with_innovations(self):
        """有创新方向时按方向检索本地专利并分组"""
        cursor = _FakeCursor(fetchall_results=[[_row()]])
        with _patch_session(cursor):
            from app.algorithm.patent_service import patent_search
            result = patent_search(
                innovations=[{"description": "电池散热技术"}],
                task_description="测试任务",
            )

        assert result["total_found"] == 1
        assert result["patents"][0]["title"] == "电池散热结构"
        assert result["patents"][0]["source_innovation"] == "电池散热技术"
        assert "电池散热技术" in result["direction_patents"]
        assert result["direction_patents"]["电池散热技术"] == ["电池散热结构"]
        # 不再返回供应商 source 字段
        assert "source" not in result

    def test_search_dedup_across_directions(self):
        """同一专利被多个方向命中时只保留一次"""
        same = _row()
        cursor = _FakeCursor(fetchall_results=[[same], [same]])
        with _patch_session(cursor):
            from app.algorithm.patent_service import patent_search
            result = patent_search(
                innovations=[{"description": "电池散热"}, {"description": "散热结构"}],
            )

        assert result["total_found"] == 1

    def test_search_empty_innovations_uses_task_description(self):
        """无创新方向时用任务描述兜底"""
        cursor = _FakeCursor(fetchall_results=[[_row()]])
        with _patch_session(cursor):
            from app.algorithm.patent_service import patent_search
            result = patent_search(innovations=[], task_description="电池散热技术研究")

        assert result["total_found"] == 1
        assert result["direction_patents"] == {}

    def test_search_empty_everything(self):
        """无任何输入时返回空结果，不查库"""
        cursor = _FakeCursor()
        with _patch_session(cursor):
            from app.algorithm.patent_service import patent_search
            result = patent_search(innovations=[], task_description="")

        assert result["total_found"] == 0
        assert result["patents"] == []
        assert cursor.executed == []

    def test_search_no_match_returns_empty(self):
        """本地无匹配结果时返回空结果"""
        cursor = _FakeCursor(fetchall_results=[[]])
        with _patch_session(cursor):
            from app.algorithm.patent_service import patent_search
            result = patent_search(
                innovations=[{"description": "量子计算"}],
            )

        assert result["total_found"] == 0
        assert result["patents"] == []


# ═══════════════════════════════════════════════════════════════
#  get_patent_detail（纯本地详情）
# ═══════════════════════════════════════════════════════════════

class TestGetPatentDetail:

    def test_detail_by_internal_id(self):
        """按内部 ID 查找"""
        cursor = _FakeCursor(fetchone_results=[_row(id=42)])
        with _patch_session(cursor):
            from app.algorithm.patent_service import get_patent_detail
            result = get_patent_detail("42")

        assert result is not None
        assert result["id"] == "42"
        assert result["claims"] == "权利要求"
        assert result["description"] == "说明书"

    def test_detail_by_patent_number(self):
        """按专利号查找"""
        cursor = _FakeCursor(fetchone_results=[None, _row(patent_number="CN111")])
        with _patch_session(cursor):
            from app.algorithm.patent_service import get_patent_detail
            result = get_patent_detail("CN111")

        assert result is not None
        assert result["patentNumber"] == "CN111"
        # 第一条 SQL 按 patent_number 查询
        assert "patent_number" in cursor.executed[0][0]

    def test_detail_by_publication_number(self):
        """按公开号查找"""
        cursor = _FakeCursor(fetchone_results=[None, _row(publication_number="CN111A")])
        with _patch_session(cursor):
            from app.algorithm.patent_service import get_patent_detail
            result = get_patent_detail("CN111A")

        assert result is not None
        assert "publication_number" in cursor.executed[1][0]

    def test_detail_not_found(self):
        """未找到返回 None"""
        cursor = _FakeCursor(fetchone_results=[None, None, None])
        with _patch_session(cursor):
            from app.algorithm.patent_service import get_patent_detail
            assert get_patent_detail("CN999999") is None

    def test_detail_empty_id(self):
        """空 ID 直接返回 None，不查库"""
        cursor = _FakeCursor()
        with _patch_session(cursor):
            from app.algorithm.patent_service import get_patent_detail
            assert get_patent_detail("  ") is None
        assert cursor.executed == []


# ═══════════════════════════════════════════════════════════════
#  row_to_patent_dict
# ═══════════════════════════════════════════════════════════════

class TestRowToPatentDict:

    def test_maps_fields(self):
        """字段映射与 JSON 解析"""
        from app.algorithm.patent_service import row_to_patent_dict
        d = row_to_patent_dict(_row())

        assert d["id"] == "1"
        assert d["title"] == "电池散热结构"
        assert d["applicants"] == ["华为"]
        assert d["applicant"] == "华为"
        assert d["inventors"] == ["张三"]
        assert d["mainIpc"] == "H01M"
        assert d["ipcCodes"] == ["H01M"]
        assert d["patentNumber"] == "CN111"
        assert d["filingDate"] == "2024-01-01"
        assert d["relevance_score"] == 90
        assert "source" not in d

    def test_invalid_json_falls_back(self):
        """非法 JSON 字段回退为单元素列表"""
        from app.algorithm.patent_service import row_to_patent_dict
        d = row_to_patent_dict(_row(applicants="华为公司", ipc_codes="H01M"))

        assert d["applicants"] == ["华为公司"]
        assert d["ipcCodes"] == ["H01M"]
