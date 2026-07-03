"""
专利搜索优化器 — 自动关键词提取、查询生成、相关度评分
完全自动化，无需用户干预。
"""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  IPC 分类号映射（从关键词推断）
# ══════════════════════════════════════════════════════════

IPC_KEYWORD_MAP: dict[str, list[str]] = {
    # 能源与电池
    "电池": ["H01M", "H02J"],
    "储能": ["H01M", "H02J"],
    "燃料电池": ["H01M"],
    "充电": ["H02J", "H01M"],
    "放电": ["H01M"],
    "电极": ["H01M"],
    "电解质": ["H01M"],
    # 热管理
    "散热": ["F28F", "F28D", "H05K"],
    "热管理": ["F28F", "F28D"],
    "导热": ["F28F", "C08K"],
    "冷却": ["F28D", "F28F"],
    "加热": ["F28F", "F24H"],
    "温度": ["F28F", "G01K"],
    "热": ["F28F", "F28D"],
    # 新材料
    "石墨烯": ["C01B", "C08K"],
    "碳材料": ["C01B"],
    "高分子": ["C08K", "C08L"],
    "复合材料": ["C08K", "B32B"],
    "纳米": ["B82Y", "C01B"],
    "材料": ["C08K", "B32B"],
    # 电子元器件
    "半导体": ["H01L"],
    "芯片": ["H01L"],
    "电路": ["H01L", "H05K"],
    "传感器": ["G01D", "G01N"],
    "显示器": ["G02F", "G09G"],
    # 机械结构
    "结构": ["B29C", "F16B"],
    "连接": ["F16B", "F16L"],
    "焊接": ["B23K"],
    "切割": ["B23K"],
    "制造": ["B29C", "B23P"],
    # 化学
    "分离": ["B01D"],
    "过滤": ["B01D"],
    "催化": ["B01J"],
    "有机": ["C07C", "C07D"],
    "无机": ["C01D", "C01B"],
    # 通信
    "无线": ["H04W"],
    "通信": ["H04L", "H04W"],
    "网络": ["H04L"],
    "天线": ["H01Q"],
    # 控制
    "控制": ["G05B"],
    "自动化": ["G05B"],
    "机器人": ["B25J"],
    "人工智能": ["G06N"],
    "算法": ["G06N", "G06F"],
}

# 中文停用词（搜索时过滤）
STOP_WORDS = set(
    "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 "
    "自己 这 他 她 它 们 那 些 什么 怎么 如何 可以 通过 采用 实现 提高 降低 减少 增加 "
    "进行 以及 或者 但是 而且 因为 所以 如果 虽然 对于 关于 根据".split()
)


# ══════════════════════════════════════════════════════════
#  关键词提取器
# ══════════════════════════════════════════════════════════

class KeywordExtractor:
    """从创新方向描述中自动提取关键词"""

    def extract(self, description: str, max_keywords: int = 5) -> list[str]:
        """
        从描述中提取核心关键词。

        Args:
            description: 创新方向描述
            max_keywords: 最多返回几个关键词

        Returns:
            关键词列表（按重要性排序）
        """
        if not description or not description.strip():
            return []

        # 1. 提取技术关键词（匹配 IPC 映射中的词）
        tech_keywords = self._extract_tech_keywords(description)

        # 2. 提取实体词（中英文术语）
        entity_keywords = self._extract_entities(description)

        # 3. 合并去重，保留顺序
        seen = set()
        result = []
        for kw in tech_keywords + entity_keywords:
            if kw not in seen and kw not in STOP_WORDS and len(kw) >= 2:
                seen.add(kw)
                result.append(kw)

        return result[:max_keywords]

    def _extract_tech_keywords(self, text: str) -> list[str]:
        """从 IPC 映射中匹配技术关键词"""
        found = []
        for keyword in IPC_KEYWORD_MAP:
            if keyword in text:
                found.append(keyword)
        # 按匹配词长度排序（长词优先，更精确）
        found.sort(key=len, reverse=True)
        return found

    def _extract_entities(self, text: str) -> list[str]:
        """提取实体词（中英文技术术语）"""
        entities = []

        # 提取中文词组（2-6字）
        cn_words = re.findall(r"[一-龥]{2,6}", text)
        for w in cn_words:
            if w not in STOP_WORDS and len(w) >= 2:
                entities.append(w)

        # 提取英文术语（含连字符）
        en_words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,20}", text)
        for w in en_words:
            if len(w) >= 3:
                entities.append(w)

        return entities


# ══════════════════════════════════════════════════════════
#  查询生成器
# ══════════════════════════════════════════════════════════

class QueryGenerator:
    """根据关键词生成 PatentHub 最优查询"""

    def generate(
        self,
        keywords: list[str],
        ipc_codes: list[str] | None = None,
    ) -> list[str]:
        """
        生成多个搜索查询（按相关度从高到低排列）。

        策略：
        1. 标题搜索（相关度最高）
        2. 标题 + IPC 组合搜索
        3. 摘要搜索（补充）

        Args:
            keywords: 关键词列表
            ipc_codes: IPC分类号列表（可选）

        Returns:
            查询列表
        """
        if not keywords:
            return []

        queries = []

        # 策略1：标题搜索（最核心关键词）
        if keywords:
            title_q = f"title:{keywords[0]}"
            queries.append(title_q)

        # 策略2：标题 + 多个关键词
        if len(keywords) >= 2:
            title_multi = f"title:{keywords[0]} AND title:{keywords[1]}"
            queries.append(title_multi)

        # 策略3：标题关键词 + IPC 分类号
        if keywords and ipc_codes:
            ipc_q = f"title:{keywords[0]} AND ipc:{ipc_codes[0]}"
            queries.append(ipc_q)

        # 策略4：摘要搜索（更宽泛）
        if len(keywords) >= 2:
            summary_q = f"summary:{keywords[0]} AND summary:{keywords[1]}"
            queries.append(summary_q)

        # 策略5：单关键词摘要搜索
        if keywords:
            summary_single = f"summary:{keywords[0]}"
            if summary_single not in queries:
                queries.append(summary_single)

        # 去重并保持顺序
        seen = set()
        unique = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique.append(q)

        return unique

    def get_ipc_codes(self, keywords: list[str]) -> list[str]:
        """从关键词推断 IPC 分类号"""
        codes = set()
        for kw in keywords:
            if kw in IPC_KEYWORD_MAP:
                codes.update(IPC_KEYWORD_MAP[kw])
        return list(codes)[:3]  # 最多3个


# ══════════════════════════════════════════════════════════
#  相关度评分器
# ══════════════════════════════════════════════════════════

class RelevanceScorer:
    """计算搜索结果的相关度分数"""

    def score(
        self,
        patent: dict,
        keywords: list[str],
        ipc_codes: list[str] | None = None,
    ) -> float:
        """
        计算单个专利的相关度分数（0.0 ~ 1.0）。

        评分维度：
        - 标题匹配度（40%）
        - 摘要匹配度（30%）
        - IPC匹配度（20%）
        - 申请人/类型相关性（10%）

        Args:
            patent: 专利数据
            keywords: 搜索关键词
            ipc_codes: 目标 IPC 分类号

        Returns:
            相关度分数（0.0 ~ 1.0）
        """
        if not keywords:
            return 0.0

        score = 0.0

        # 1. 标题匹配度（40%）
        title = patent.get("title", "")
        title_score = self._text_match_score(title, keywords)
        score += title_score * 0.4

        # 2. 摘要匹配度（30%）
        summary = patent.get("summary", patent.get("abstract", ""))
        summary_score = self._text_match_score(summary, keywords)
        score += summary_score * 0.3

        # 3. IPC 匹配度（20%）
        patent_ipc = patent.get("mainIpc", patent.get("ipc", ""))
        ipc_score = self._ipc_match_score(patent_ipc, ipc_codes or [])
        score += ipc_score * 0.2

        # 4. 申请人/类型加分（10%）
        type_bonus = self._type_bonus(patent)
        score += type_bonus * 0.1

        return round(min(score, 1.0), 3)

    def _text_match_score(self, text: str, keywords: list[str]) -> float:
        """文本与关键词的匹配度"""
        if not text or not keywords:
            return 0.0

        text_lower = text.lower()
        matched = sum(1 for kw in keywords if kw.lower() in text_lower)

        return matched / len(keywords) if keywords else 0.0

    def _ipc_match_score(self, patent_ipc: str, target_ipcs: list[str]) -> float:
        """IPC 分类号匹配度"""
        if not target_ipcs:
            return 0.5  # 无目标 IPC 时给中等分

        if not patent_ipc:
            return 0.0

        for ipc in target_ipcs:
            if ipc in patent_ipc:
                return 1.0

        return 0.0

    def _type_bonus(self, patent: dict) -> float:
        """专利类型加分（发明授权 > 发明公开 > 实用新型）"""
        pat_type = patent.get("type", patent.get("patType", ""))
        legal = patent.get("legalStatus", "")

        if "发明授权" in legal or "有效" in legal:
            return 1.0
        elif "发明" in pat_type or "发明公开" in legal:
            return 0.8
        elif "实用新型" in pat_type:
            return 0.6
        else:
            return 0.5


# ══════════════════════════════════════════════════════════
#  优化搜索主流程
# ══════════════════════════════════════════════════════════

async def optimized_patent_search(
    innovations: list[dict],
    max_results: int = 50,
) -> list[dict]:
    """
    自动优化的专利搜索主流程。

    流程：
    1. 按用户评分排序创新方向（高分优先）
    2. 为每个创新方向提取关键词
    3. 生成 PatentHub 查询
    4. 执行搜索
    5. 计算相关度分数
    6. 合并去重并排序

    Args:
        innovations: 创新方向列表（含 description, user_rating）
        max_results: 最大返回数量

    Returns:
        带相关度分数的专利列表
    """
    from app.algorithm.patent_hub_client import search_patents

    extractor = QueryGenerator()
    scorer = RelevanceScorer()
    kw_extractor = KeywordExtractor()

    # 1. 按评分排序（高分优先搜索）
    sorted_innovations = sorted(
        innovations,
        key=lambda x: x.get("user_rating") or 0,
        reverse=True,
    )

    all_results = []
    seen_ids = set()

    for innovation in sorted_innovations:
        description = innovation.get("description", "")
        if not description:
            continue

        # 2. 提取关键词
        keywords = kw_extractor.extract(description)
        if not keywords:
            continue

        # 3. 推断 IPC 分类号
        ipc_codes = extractor.get_ipc_codes(keywords)

        # 4. 生成查询（最多尝试3个查询策略）
        queries = extractor.generate(keywords, ipc_codes)

        for query in queries[:2]:  # 每个创新方向最多2个查询，控制API调用量
            try:
                result = await search_patents(q=query, page=1, page_size=15)
            except Exception as e:
                logger.warning(f"PatentHub 搜索失败(q={query[:30]}): {e}")
                continue

            patents = result.get("patents", [])
            for patent in patents:
                pid = patent.get("id", "")
                if not pid or pid in seen_ids:
                    continue

                # 5. 计算相关度分数
                relevance = scorer.score(patent, keywords, ipc_codes)
                patent["relevance_score"] = relevance
                patent["source_innovation"] = description[:50]
                patent["search_query"] = query

                seen_ids.add(pid)
                all_results.append(patent)

    # 6. 按相关度排序
    all_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    return all_results[:max_results]
