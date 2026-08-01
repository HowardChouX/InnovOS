"""
AI 分析器基类 — 提供 JSON 解析工具 + AIAnalyzer 基类。

AIBase 已移除（2026-08-01），所有 AI 调用走 FailoverRouter 路径。
分析器现在接收任意实现了 call_ai() / call_ai_async() 接口的对象（duck typing）。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON 解析工具函数
# ---------------------------------------------------------------------------

_THINK_TAG_RE = re.compile(r"<(think|thinking)>.*?</\1>", re.IGNORECASE | re.DOTALL)
_THINK_BRACKET_RE = re.compile(r"\[thinking\].*?\[/thinking\]", re.IGNORECASE | re.DOTALL)


def strip_think_tags(content: str) -> str:
    """清理各种 think 标签（尖括号和方括号两种写法）。"""
    content = content.replace("＜", "<").replace("＞", ">")
    content = _THINK_TAG_RE.sub("", content)
    content = _THINK_BRACKET_RE.sub("", content)
    return content


def extract_json_str(content: str) -> str | None:
    """从 AI 响应文本中提取第一个 JSON 对象字符串。

    优先级：
    1. ```json ... ``` / ``` ... ``` markdown 代码块
    2. 从文本中找到第一个完整闭合的 { ... } 对象
    3. 尝试提取不完整的 JSON（从第一个 { 开始到结尾）
    4. 返回 None
    """
    if not content:
        return None

    content = content.strip()
    content = _THINK_BRACKET_RE.sub("", content)

    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if m:
        json_str = m.group(1).strip()
    else:
        json_str = _find_json_boundary(content)

    if not json_str:
        first_brace = content.find("{")
        if first_brace >= 0:
            json_str = content[first_brace:].strip()
            repaired = repair_json(json_str)
            if repaired:
                return repaired
        return None

    json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)
    return json_str


def _find_json_boundary(content: str) -> str:
    """栈匹配找到文本中第一个完整闭合的 JSON 值。"""
    result_obj = _scan_for_json(content, "{", "}")
    result_arr = _scan_for_json(content, "[", "]")

    if result_obj and result_arr:
        return result_obj if content.find("{") < content.find("[") else result_arr
    return result_obj or result_arr or ""


def _scan_for_json(content: str, open_ch: str, close_ch: str) -> str | None:
    """在文本中扫描第一个完整闭合的 JSON 结构。"""
    i = 0
    while i < len(content):
        start = content.find(open_ch, i)
        if start < 0:
            return None

        stack = 0
        in_string = False
        escaped = False
        for j in range(start, len(content)):
            ch = content[j]
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_string:
                escaped = True
                continue
            if ch == '"' and not escaped:
                in_string = not in_string
                continue
            if not in_string:
                if ch == open_ch:
                    stack += 1
                elif ch == close_ch:
                    stack -= 1
                    if stack == 0:
                        candidate = content[start : j + 1]
                        if open_ch == "[" or '"' in candidate:
                            return candidate
                        break
        i = start + 1
    return None


def repair_json(json_str: str) -> str | None:
    """尝试修复被截断或格式错误的 JSON 字符串。"""
    if not json_str:
        return None

    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass

    json_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", json_str)

    stack: list[str] = []
    in_string = False
    escaped = False
    for ch in json_str:
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_string:
            escaped = True
            continue
        if ch == '"' and not escaped:
            in_string = not in_string
            continue
        if not in_string:
            if ch in "{[":
                stack.append(ch)
            elif ch == "}" and stack and stack[-1] == "{" or ch == "]" and stack and stack[-1] == "[":
                stack.pop()

    if in_string:
        json_str += '"'
    while stack:
        ch = stack.pop()
        json_str += "}" if ch == "{" else "]"

    json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)
    json_str = re.sub(r",\s*$", "", json_str.strip())

    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass

    max_scan = min(100, len(json_str))
    for end_pos in range(len(json_str), len(json_str) - max_scan, -1):
        candidate = json_str[:end_pos]
        sc: list[str] = []
        for ch in candidate:
            if ch in "{[":
                sc.append(ch)
            elif ch == "}" and sc and sc[-1] == "{" or ch == "]" and sc and sc[-1] == "[":
                sc.pop()
        while sc:
            ch = sc.pop()
            candidate += "}" if ch == "{" else "]"
        candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue

    return None


def parse_ai_json(content: str) -> dict | str | None:
    """从 AI 响应中解析 JSON，返回解析后的 dict 或原始文本。"""
    content = strip_think_tags(content or "").strip()
    if not content:
        return None

    json_str = extract_json_str(content)
    if not json_str:
        return {"content": content}

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        repaired = repair_json(json_str)
        if repaired:
            parsed = json.loads(repaired)
        else:
            return {"content": content}

    return parsed if isinstance(parsed, dict) else {"content": str(parsed)}


# ---------------------------------------------------------------------------
# AIAnalyzer — 分析器基类
# ---------------------------------------------------------------------------


class AIAnalyzer:
    """AI 分析器基类 — 所有领域分析器的父类。

    接收任意实现了以下接口的对象（duck typing）：
        call_ai(system_prompt, user_prompt, ...) -> str | dict | None
        call_ai_async(system_prompt, user_prompt, ...) -> str | dict | None
    """

    def __init__(self, ai):
        self.ai = ai

    def call_ai(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        logger_prefix: str = "",
        raw: bool = False,
        json_mode: bool = False,
    ) -> str | dict | None:
        return self.ai.call_ai(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            logger_prefix=logger_prefix,
            raw=raw,
            json_mode=json_mode,
        )

    async def call_ai_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        logger_prefix: str = "",
        raw: bool = False,
        json_mode: bool = False,
    ) -> str | dict | None:
        return await self.ai.call_ai_async(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            logger_prefix=logger_prefix,
            raw=raw,
            json_mode=json_mode,
        )