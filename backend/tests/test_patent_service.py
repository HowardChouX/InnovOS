"""
专利检索服务测试

覆盖：patent_service（统一检索）, patent_hub_client, patent_search_optimizer
策略：mock API 调用和数据库，避免真实请求
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════
#  patent_hub_client 测试
# ═══════════════════════════════════════════════════════════════

class TestPatentHubClient:

    @pytest.mark.asyncio
    async def test_search_patents_success(self):
        """PatentHub 搜索成功返回标准化结果"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 200,
            "total": 158813,
            "totalPages": 15882,
            "page": 1,
            "patents": [
                {
                    "id": "CN111344253A",
                    "title": "一种电池散热结构",
                    "summary": "本发明公开了一种电池散热结构",
                    "applicant": "华为技术有限公司",
                    "inventor": "张三",
                    "applicationDate": "2020-01-01",
                    "documentDate": "2021-06-01",
                    "mainIpc": "H01M10/6556",
                    "type": "发明授权",
                    "legalStatus": "有效",
                }
            ],
        }

        with patch("app.algorithm.patent_hub_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.algorithm.patent_hub_client._get_token", return_value="test_token"):
                from app.algorithm.patent_hub_client import search_patents
                result = await search_patents(q="title:电池散热", page=1, page_size=10)

        assert result["total"] == 158813
        assert len(result["patents"]) == 1
        assert result["patents"][0]["id"] == "CN111344253A"
        assert result["patents"][0]["title"] == "一种电池散热结构"
        assert result["patents"][0]["source"] == "patenthub"

    @pytest.mark.asyncio
    async def test_search_patents_empty_query(self):
        """空查询返回空结果"""
        from app.algorithm.patent_hub_client import search_patents
        result = await search_patents(q="", page=1, page_size=10)
        assert result["total"] == 0
        assert result["patents"] == []

    @pytest.mark.asyncio
    async def test_search_patents_api_error(self):
        """API 错误返回空结果"""
        import httpx
        with patch("app.algorithm.patent_hub_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.algorithm.patent_hub_client._get_token", return_value="test_token"):
                from app.algorithm.patent_hub_client import search_patents
                result = await search_patents(q="title:测试", page=1, page_size=10)

        assert result["total"] == 0
        assert result["patents"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_patents_wrong_code(self):
        """API 返回非 200 code"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 401,
            "message": "Token 无效",
        }

        with patch("app.algorithm.patent_hub_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.algorithm.patent_hub_client._get_token", return_value="bad_token"):
                from app.algorithm.patent_hub_client import search_patents
                result = await search_patents(q="title:测试", page=1, page_size=10)

        assert result["total"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_patent_base_success(self):
        """获取专利基本信息成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 200,
            "patent": {"id": "CN111344253A", "title": "电池散热"},
        }

        with patch("app.algorithm.patent_hub_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.algorithm.patent_hub_client._get_token", return_value="test_token"):
                from app.algorithm.patent_hub_client import get_patent_base
                result = await get_patent_base("CN111344253A")

        assert result is not None
        assert result["id"] == "CN111344253A"

    @pytest.mark.asyncio
    async def test_get_patent_base_not_found(self):
        """专利不存在返回 None"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 404}

        with patch("app.algorithm.patent_hub_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.algorithm.patent_hub_client._get_token", return_value="test_token"):
                from app.algorithm.patent_hub_client import get_patent_base
                result = await get_patent_base("INVALID_ID")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_patent_claims_empty_id(self):
        """空 ID 返回空字符串"""
        from app.algorithm.patent_hub_client import get_patent_claims
        result = await get_patent_claims("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_get_patent_full_combines_data(self):
        """get_patent_full 组合 base + claims + description"""
        with patch("app.algorithm.patent_hub_client.get_patent_base", new_callable=AsyncMock) as mock_base:
            with patch("app.algorithm.patent_hub_client.get_patent_claims", new_callable=AsyncMock) as mock_claims:
                with patch("app.algorithm.patent_hub_client.get_patent_description", new_callable=AsyncMock) as mock_desc:
                    mock_base.return_value = {"id": "CN1", "title": "测试"}
                    mock_claims.return_value = "权利要求全文"
                    mock_desc.return_value = "说明书全文"

                    from app.algorithm.patent_hub_client import get_patent_full
                    result = await get_patent_full("CN1")

        assert result["id"] == "CN1"
        assert result["claims"] == "权利要求全文"
        assert result["description"] == "说明书全文"

    def test_normalize_patent(self):
        """标准化专利数据"""
        from app.algorithm.patent_hub_client import _normalize_patent

        raw = {
            "id": "CN111",
            "title": "散热结构",
            "summary": "摘要内容",
            "applicant": "华为",
            "inventor": "张三",
            "applicationDate": "2020-01-01",
            "documentDate": "2021-01-01",
            "mainIpc": "H01M",
            "type": "发明授权",
            "legalStatus": "有效",
        }
        result = _normalize_patent(raw)
        assert result["id"] == "CN111"
        assert result["title"] == "散热结构"
        assert result["source"] == "patenthub"
        assert result["mainIpc"] == "H01M"


# ═══════════════════════════════════════════════════════════════
#  patent_search_optimizer 测试
# ═══════════════════════════════════════════════════════════════

class TestKeywordExtractor:

    def test_extract_tech_keywords(self):
        """从描述中提取技术关键词"""
        from app.algorithm.patent_search_optimizer import KeywordExtractor
        ext = KeywordExtractor()
        keywords = ext.extract("利用石墨烯材料进行电池散热")
        assert "石墨烯" in keywords
        assert "电池" in keywords or "散热" in keywords

    def test_extract_empty_input(self):
        """空描述返回空列表"""
        from app.algorithm.patent_search_optimizer import KeywordExtractor
        ext = KeywordExtractor()
        assert ext.extract("") == []
        assert ext.extract("   ") == []

    def test_extract_max_keywords(self):
        """限制返回关键词数量"""
        from app.algorithm.patent_search_optimizer import KeywordExtractor
        ext = KeywordExtractor()
        keywords = ext.extract("电池散热石墨烯芯片半导体传感器", max_keywords=3)
        assert len(keywords) <= 3

    def test_extract_filters_stop_words(self):
        """过滤停用词"""
        from app.algorithm.patent_search_optimizer import KeywordExtractor
        ext = KeywordExtractor()
        keywords = ext.extract("这是一个可以通过采用石墨烯的方法")
        # 停用词不应该出现
        assert "通过" not in keywords
        assert "采用" not in keywords

    def test_extract_entities(self):
        """提取中英文实体词"""
        from app.algorithm.patent_search_optimizer import KeywordExtractor
        ext = KeywordExtractor()
        keywords = ext.extract("使用LiFePO4电池进行Energy存储")
        # 应提取到一些英文术语
        assert any(kw in keywords for kw in ["LiFePO4", "Energy"])


class TestQueryGenerator:

    def test_generate_basic(self):
        """基本查询生成"""
        from app.algorithm.patent_search_optimizer import QueryGenerator
        gen = QueryGenerator()
        queries = gen.generate(["散热", "电池"])
        assert len(queries) > 0
        assert "title:散热" in queries

    def test_generate_with_ipc(self):
        """带 IPC 分类号的查询生成"""
        from app.algorithm.patent_search_optimizer import QueryGenerator
        gen = QueryGenerator()
        queries = gen.generate(["散热", "电池"], ipc_codes=["H01M", "F28F"])
        assert any("ipc:H01M" in q or "ipc:F28F" in q for q in queries)

    def test_generate_empty_keywords(self):
        """空关键词返回空列表"""
        from app.algorithm.patent_search_optimizer import QueryGenerator
        gen = QueryGenerator()
        assert gen.generate([]) == []

    def test_generate_no_duplicates(self):
        """查询不重复"""
        from app.algorithm.patent_search_optimizer import QueryGenerator
        gen = QueryGenerator()
        queries = gen.generate(["散热", "电池"])
        assert len(queries) == len(set(queries))

    def test_get_ipc_codes(self):
        """从关键词推断 IPC 分类号"""
        from app.algorithm.patent_search_optimizer import QueryGenerator
        gen = QueryGenerator()
        codes = gen.get_ipc_codes(["电池", "散热"])
        assert len(codes) > 0
        assert any(c.startswith("H") or c.startswith("F") for c in codes)


class TestRelevanceScorer:

    def test_score_high_relevance(self):
        """高相关度专利"""
        from app.algorithm.patent_search_optimizer import RelevanceScorer
        scorer = RelevanceScorer()
        patent = {
            "title": "电池散热结构及方法",
            "summary": "本发明涉及一种电池散热结构",
            "mainIpc": "H01M10/6556",
            "type": "发明授权",
            "legalStatus": "有效",
        }
        score = scorer.score(patent, ["电池", "散热"], ["H01M"])
        assert score > 0.5

    def test_score_no_match(self):
        """不相关专利"""
        from app.algorithm.patent_search_optimizer import RelevanceScorer
        scorer = RelevanceScorer()
        patent = {
            "title": "一种鞋子的设计",
            "summary": "本发明涉及一种鞋子",
            "mainIpc": "A43B",
            "type": "实用新型",
            "legalStatus": "",
        }
        score = scorer.score(patent, ["电池", "散热"], ["H01M"])
        assert score < 0.3

    def test_score_empty_keywords(self):
        """空关键词返回 0"""
        from app.algorithm.patent_search_optimizer import RelevanceScorer
        scorer = RelevanceScorer()
        assert scorer.score({"title": "test"}, []) == 0.0

    def test_score_text_match(self):
        """文本匹配度计算"""
        from app.algorithm.patent_search_optimizer import RelevanceScorer
        scorer = RelevanceScorer()
        # 标题完全匹配
        patent = {"title": "电池散热", "summary": "", "mainIpc": "", "type": ""}
        score = scorer.score(patent, ["电池", "散热"])
        assert score > 0.3  # 标题匹配 2/2 * 0.4 = 0.4

    def test_ipc_match(self):
        """IPC 分类号匹配"""
        from app.algorithm.patent_search_optimizer import RelevanceScorer
        scorer = RelevanceScorer()
        patent = {"title": "", "summary": "", "mainIpc": "H01M10/6556", "type": ""}
        score = scorer.score(patent, ["电池"], ["H01M"])
        assert score >= 0.2  # IPC 匹配 * 0.2

    def test_type_bonus(self):
        """专利类型加分"""
        from app.algorithm.patent_search_optimizer import RelevanceScorer
        scorer = RelevanceScorer()

        patent_valid = {"title": "", "summary": "", "mainIpc": "", "legalStatus": "有效", "type": ""}
        patent_utility = {"title": "", "summary": "", "mainIpc": "", "legalStatus": "", "type": "实用新型"}

        bonus_valid = scorer._type_bonus(patent_valid)
        bonus_utility = scorer._type_bonus(patent_utility)
        assert bonus_valid > bonus_utility


# ═══════════════════════════════════════════════════════════════
#  patent_service 测试
# ═══════════════════════════════════════════════════════════════

class TestPatentService:

    @pytest.mark.asyncio
    async def test_patent_search_with_innovations(self):
        """有创新方向时使用 PatentHub 智能搜索"""
        mock_patents = [
            {
                "id": "CN111",
                "title": "电池散热结构",
                "relevance_score": 0.8,
                "source_innovation": "电池散热技术",
            }
        ]

        with patch("app.algorithm.patent_search_optimizer.optimized_patent_search", new_callable=AsyncMock) as mock_opt:
            mock_opt.return_value = mock_patents

            from app.algorithm.patent_service import patent_search
            result = await patent_search(
                innovations=[{"description": "电池散热技术", "user_rating": 5}],
                task_description="测试任务",
            )

        assert result["source"] == "patenthub"
        assert len(result["patents"]) == 1
        assert result["total_found"] == 1
        assert "电池散热技术" in result["direction_patents"]

    @pytest.mark.asyncio
    async def test_patent_search_fallback_to_local(self):
        """PatentHub 失败时降级到本地数据库"""
        with patch("app.algorithm.patent_search_optimizer.optimized_patent_search", new_callable=AsyncMock) as mock_opt:
            mock_opt.side_effect = RuntimeError("PatentHub API 失败")

            with patch("app.algorithm.patent_service._local_like_search") as mock_local:
                mock_local.return_value = [
                    {"id": "1", "title": "本地专利", "source": "local"}
                ]

                from app.algorithm.patent_service import patent_search
                result = await patent_search(
                    innovations=[{"description": "电池散热技术"}],
                    task_description="测试任务",
                )

        assert result["source"] == "local"
        assert len(result["patents"]) == 1

    @pytest.mark.asyncio
    async def test_patent_search_empty_innovations(self):
        """无创新方向时使用任务描述搜索"""
        mock_result = {"patents": [{"id": "CN222", "title": "测试专利"}]}

        with patch("app.algorithm.patent_search_optimizer.optimized_patent_search", new_callable=AsyncMock) as mock_opt:
            mock_opt.return_value = []

            with patch("app.algorithm.patent_hub_client.search_patents", new_callable=AsyncMock) as mock_ph:
                mock_ph.return_value = mock_result

                from app.algorithm.patent_service import patent_search
                result = await patent_search(
                    innovations=[],
                    task_description="电池散热技术研究",
                )

        assert "patents" in result

    @pytest.mark.asyncio
    async def test_patent_search_fallback_also_fails(self):
        """PatentHub 和本地搜索都失败"""
        with patch("app.algorithm.patent_search_optimizer.optimized_patent_search", new_callable=AsyncMock) as mock_opt:
            mock_opt.side_effect = RuntimeError("PatentHub failed")

            with patch("app.algorithm.patent_service._local_like_search") as mock_local:
                mock_local.side_effect = RuntimeError("DB failed")

                from app.algorithm.patent_service import patent_search
                result = await patent_search(
                    innovations=[{"description": "测试"}],
                    task_description="测试",
                )

        assert result["source"] == "none"
        assert result["patents"] == []

    @pytest.mark.asyncio
    async def test_get_patent_detail_from_patenthub(self):
        """优先从 PatentHub 获取详情"""
        mock_patent = {"id": "CN111", "title": "电池散热", "source": "patenthub"}

        with patch("app.algorithm.patent_hub_client.get_patent_full", new_callable=AsyncMock) as mock_ph:
            mock_ph.return_value = mock_patent

            from app.algorithm.patent_service import get_patent_detail
            result = await get_patent_detail("CN111")

        assert result is not None
        assert result["source"] == "patenthub"
        mock_ph.assert_called_once_with("CN111")

    @pytest.mark.asyncio
    async def test_get_patent_detail_fallback_to_local(self):
        """PatentHub 失败时从本地数据库获取"""
        with patch("app.algorithm.patent_hub_client.get_patent_full", new_callable=AsyncMock) as mock_ph:
            mock_ph.side_effect = RuntimeError("API failed")

            with patch("app.algorithm.patent_service._get_local_patent") as mock_local:
                mock_local.return_value = {"id": "123", "title": "本地专利", "source": "local"}

                from app.algorithm.patent_service import get_patent_detail
                result = await get_patent_detail("123")

        assert result is not None
        assert result["source"] == "local"

    def test_local_like_search(self):
        """本地 LIKE 搜索"""
        mock_row = {
            "id": 1,
            "title": "电池散热结构",
            "abstract": "一种新型电池散热结构",
            "applicants": '["华为"]',
            "inventors": '["张三"]',
            "patent_number": "CN111",
            "created_at": "2024-01-01",
        }

        with patch("app.algorithm.patent_service.get_db") as mock_get_db:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchall.return_value = [mock_row]
            mock_get_db.return_value = mock_conn

            from app.algorithm.patent_service import _local_like_search
            results = _local_like_search("电池散热", ["电池", "散热"])

        assert len(results) == 1
        assert results[0]["title"] == "电池散热结构"
        assert results[0]["source"] == "local"
        assert results[0]["applicant"] == "华为"

    def test_get_local_patent(self):
        """从本地数据库获取单个专利"""
        mock_row = {
            "id": 1,
            "title": "电池散热",
            "abstract": "散热结构",
            "applicants": '["华为", "中兴"]',
            "inventors": '["张三"]',
            "ipc_codes": '["H01M"]',
            "patent_number": "CN111",
            "claims": "权利要求",
            "description": "说明书",
        }

        with patch("app.algorithm.patent_service.get_db") as mock_get_db:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = mock_row
            mock_get_db.return_value = mock_conn

            from app.algorithm.patent_service import _get_local_patent
            result = _get_local_patent("1")

        assert result is not None
        assert result["title"] == "电池散热"
        assert result["applicant"] == "华为, 中兴"
        assert result["claims"] == "权利要求"

    def test_get_local_patent_not_found(self):
        """本地数据库未找到"""
        with patch("app.algorithm.patent_service.get_db") as mock_get_db:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_get_db.return_value = mock_conn

            from app.algorithm.patent_service import _get_local_patent
            result = _get_local_patent("999")

        assert result is None
