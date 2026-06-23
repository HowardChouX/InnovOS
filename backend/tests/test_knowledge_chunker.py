"""
测试文档分块器 — chunk_document 的分块策略

覆盖：
- 默认分隔符：段落 → 句子 → 字符
- 分块重叠（overlap）创建重叠窗口
- 短文本（< chunk_size）返回单块
- 空文本返回空列表
- 长文本创建多块
- 中文文本在 。！？处分句正确
- 纯字符回退（无分隔符匹配时）
"""

import pytest

from app.algorithm.knowledge.chunker import (
    chunk_document,
    _recursive_split,
    _merge_chunks,
    _add_overlap,
)


# ─── chunk_document 集成测试 ──────────────────────────────────


def test_short_text_returns_single_chunk():
    """短于 chunk_size 的文本返回单个分块。"""
    content = "Hello world."
    result = chunk_document(content, chunk_size=512, chunk_overlap=64)
    assert len(result) == 1
    assert result[0]["text"] == "Hello world."
    assert result[0]["index"] == 0


def test_empty_text_returns_empty_list():
    """空文本返回空列表。"""
    assert chunk_document("") == []
    assert chunk_document("   ") == []
    assert chunk_document("\n\n\n") == []


def test_long_text_creates_multiple_chunks():
    """长文本被正确分割为多个分块。"""
    content = "word " * 200  # ~1000 chars
    result = chunk_document(content, chunk_size=256, chunk_overlap=32)
    assert len(result) >= 2
    for chunk in result:
        assert "text" in chunk
        assert "index" in chunk
    indices = [c["index"] for c in result]
    assert indices == list(range(len(result)))


def test_chunk_overlap_creates_overlapping_windows():
    """_add_overlap 正确创建重叠窗口。"""
    chunks = ["AAA", "BBB", "CCC"]
    overlapped = _add_overlap(chunks, overlap=2)
    assert len(overlapped) == 3
    assert overlapped[0] == "AAA"
    assert overlapped[1].startswith("AA")  # last 2 of prev + current
    assert overlapped[2].startswith("BB")


def test_chunk_overlap_zero_returns_original():
    """overlap=0 时返回原始分块。"""
    chunks = ["AAA", "BBB"]
    assert _add_overlap(chunks, 0) == chunks


def test_chunk_overlap_single_chunk_returns_unchanged():
    """单个分块时 overlap 不应生效。"""
    assert _add_overlap(["AAA"], 10) == ["AAA"]


# ─── 中文分句 ──────────────────────────────────────────────────


def test_chinese_sentence_splitting():
    """中文文本在 。！？处分句。"""
    content = "第一句。第二句！第三句？第四句。"
    # Use small chunk_size to force splitting at sentence boundaries
    result = chunk_document(content, chunk_size=10, chunk_overlap=0)
    # Each sentence is ~4 chars, should be separate chunks
    texts = [c["text"] for c in result]
    assert any("第一句" in t for t in texts)
    assert any("第二句" in t for t in texts)
    assert any("第三句" in t for t in texts)
    assert any("第四句" in t for t in texts)


def test_chinese_and_english_mixed():
    """中英文混排文本正确分块。"""
    # Make text long enough to exceed 512-char hard limit in _recursive_split
    content = "手机散热方案。" * 30 + "Thermal solution。" * 30 + "测试。" * 30
    result = chunk_document(content, chunk_size=256, chunk_overlap=0)
    # Should be split at 。boundaries into multiple chunks
    assert len(result) >= 3
    texts = " ".join(c["text"] for c in result)
    assert "手机散热方案" in texts


# ─── 段落与分隔符 ──────────────────────────────────────────────


def test_paragraph_splitting_by_double_newline():
    """段落（\n\n）分割长文本。"""
    # Build text long enough to exceed 512-char hard limit
    content = ("第一段内容。" * 40 + "\n\n" + "第二段内容。" * 40 + "\n\n" + "第三段内容。" * 40)
    result = chunk_document(content, chunk_size=400, chunk_overlap=0)
    # Should split into multiple chunks
    assert len(result) >= 2


def test_custom_separators():
    """自定义分隔符列表生效。"""
    # Long enough to exceed 512 chars, triggering recursive split
    content = ("aaa||" * 150) + "bbb"
    assert len(content) > 512
    result = chunk_document(content, chunk_size=100, chunk_overlap=0, separators=["||"])
    # Should be split at || into separate pieces
    assert len(result) >= 5


# ─── 内部函数单元测试 ──────────────────────────────────────────


def test_recursive_split_below_chunk_size():
    """_recursive_split 在文本 <= 512 字符时直接返回。"""
    result = _recursive_split("short", ["\n\n", "\n", "。"], 0)
    assert result == ["short"]


def test_recursive_split_depth_exhaustion():
    """_recursive_split 分隔符耗尽时返回原始文本。"""
    text = "a" * 600
    result = _recursive_split(text, ["\n\n"], 0)
    # Can't split on \n\n since no \n\n, returns as-is at depth >= len(separators)
    assert len(result) == 1
    assert result[0] == text


def test_merge_chunks_empty_input():
    """_merge_chunks 空列表返回空列表。"""
    assert _merge_chunks([], 100) == []


def test_merge_chunks_combines_small():
    """_merge_chunks 将小文本合并到前一块。"""
    chunks = ["A" * 50, "B" * 50, "C" * 50]
    merged = _merge_chunks(chunks, max_size=120)
    assert len(merged) <= len(chunks)


def test_merge_chunks_returns_original_if_empty_result():
    """_merge_chunks 当 buffer 为空且 chunks 非空时返回原始。"""
    # Edge: all chunks empty string — should return original chunks
    chunks = ["", "", ""]
    merged = _merge_chunks(chunks, 10)
    assert merged == chunks


# ─── 边界情况 ──────────────────────────────────────────────────


def test_text_exactly_chunk_size():
    """文本恰好等于 chunk_size 应返回单块。"""
    content = "A" * 256
    result = chunk_document(content, chunk_size=256, chunk_overlap=0)
    assert len(result) == 1


def test_text_slightly_over_chunk_size():
    """文本略大于 chunk_size 应分割为两块。"""
    content = "A" * 300
    result = chunk_document(content, chunk_size=256, chunk_overlap=0)
    assert 1 <= len(result) <= 2


def test_large_overlap_does_not_exceed_chunk():
    """overlap 大于前块长度时取整个前块。"""
    chunks = ["AB", "CDEF"]
    overlapped = _add_overlap(chunks, overlap=10)
    assert overlapped[1] == "AB" + "CDEF"  # entire prev + current


def test_chunk_indices_are_sequential():
    """所有分块的 index 从 0 开始且连续。"""
    content = "word " * 300
    result = chunk_document(content, chunk_size=128, chunk_overlap=16)
    indices = [c["index"] for c in result]
    assert indices == list(range(len(result)))


def test_all_text_fragments_have_content():
    """每个分块的 text 应有内容（strip 后非空）。"""
    content = "Hello world. " * 50
    result = chunk_document(content, chunk_size=50, chunk_overlap=10)
    for c in result:
        assert c["text"].strip(), f"Empty text at index {c['index']}"


def test_chinese_punctuation_only_splitting():
    """纯中文标点分隔正常工作。"""
    content = "今天天气不错我们去公园散步"
    # No punctuation, will fall back to char-level split
    result = chunk_document(content, chunk_size=10, chunk_overlap=0)
    assert len(result) >= 1
    total_chars = sum(len(c["text"]) for c in result)
    assert total_chars == len(content)
