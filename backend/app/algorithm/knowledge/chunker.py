"""
文档分块器 — 借鉴 CherryStudio chunk.ts 的分块策略

分块策略：
1. 优先按段落分割（\n\n）
2. 段落过长则按句子分割（。！？\n）
3. 句子过长则按字符分割
4. 相邻块之间保持 overlap 个字符的重叠
"""
from __future__ import annotations
import re


def chunk_document(
    content: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    separators: list[str] | None = None,
) -> list[dict]:
    """将文档分块，返回 [{text, start, end}, ...]。"""
    if not content or not content.strip():
        return []

    if separators is None:
        separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "]

    raw_chunks = _recursive_split(content, separators, 0)
    merged = _merge_chunks(raw_chunks, chunk_size)
    overlapped = _add_overlap(merged, chunk_overlap)
    return [
        {"text": t.strip(), "index": i}
        for i, t in enumerate(overlapped)
        if t.strip()
    ]


def _recursive_split(text: str, separators: list[str], depth: int) -> list[str]:
    """递归按分隔符拆分文本。"""
    if depth >= len(separators) or len(text) <= 512:
        return [text]

    sep = separators[depth]
    parts = text.split(sep)
    result = []
    for part in parts:
        if len(part) <= 512:
            result.append(part)
        else:
            result.extend(_recursive_split(part, separators, depth + 1))
    # 用原分隔符拼接回去，保留语义边界
    if len(result) > 1:
        return [result[0]] + [sep + r for r in result[1:]]
    return result


def _merge_chunks(chunks: list[str], max_size: int) -> list[str]:
    """将过小的块合并到相邻块。"""
    if not chunks:
        return []

    merged = []
    buffer = ""

    for chunk in chunks:
        if len(buffer) + len(chunk) <= max_size:
            buffer += chunk
        else:
            if buffer:
                merged.append(buffer)
            buffer = chunk

    if buffer:
        merged.append(buffer)

    return merged if merged else chunks


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    """为相邻块添加重叠窗口。"""
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1][-overlap:]
        result.append(prev_tail + chunks[i])

    return result
