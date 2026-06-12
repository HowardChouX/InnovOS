"""
专利结构化提取器 — 从 PDF 文本中提取专利元数据字段

策略：
  1. 正则提取结构化字段（免费，覆盖 90% 中国专利格式）
  2. AI 兜底：仅当关键字段缺失时调用 LLM 补充

支持两种输入格式：
  - pdfminer: 半角括号，顺序从左到右 (19)(12)(10)...
  - PaddleOCR: 全角/半角括号混合，版面排序（(54)(57)可能在IPC后面）

中国发明专利/实用新型标准格式：
  (10)申请公布号  (21)申请号  (22)申请日  (71)申请人
  (72)发明人  (74)专利代理  (51)Int.Cl.  (54)发明名称  (57)摘要
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── 通用正则（兼容全角/半角括号） ──

# (10) 或 （10）
_RE_BRACKET = r"[（(]"

# 申请公布号: CN122158040A
RE_PUB_NUM = re.compile(rf"{_RE_BRACKET}10[）)]\s*申请公布号\s*(CN[\s\dA-Z]+)")

# 申请号: 202610608176.8
RE_APP_NUM = re.compile(rf"{_RE_BRACKET}21[）)][^0-9]*?(\d{{12}}\.?\d*)")

# 申请日: 2026.05.06
RE_FILING_DATE = re.compile(rf"{_RE_BRACKET}22[）)][^0-9]*?(\d{{4}}\.\d{{2}}\.\d{{2}})")

# 公开日
RE_PUB_DATE = re.compile(rf"{_RE_BRACKET}43[）)][^0-9]*?(\d{{4}}\.\d{{2}}\.\d{{2}})")

# IPC 分类号: G16H 40/20
RE_IPC = re.compile(r"([A-Z]\d+\w*\s+\d+/\d+)")

# 发明名称 — 从 (54) 到 (57)摘要 或末尾
RE_TITLE = re.compile(rf"{_RE_BRACKET}54[）)]发明名称\s*(.+?)(?={_RE_BRACKET}57[）)]摘要|\Z)", re.DOTALL)

# 摘要 — 从 (57)摘要 到 "CN" 页码标记或 "1." 权利要求开头
RE_ABSTRACT = re.compile(rf"{_RE_BRACKET}57[）)]摘要\s*(.+?)(?=\n\s*CN[^书]|\n\s*[1．\.]\s|权利要求书|\Z)", re.DOTALL)

# 权利要求书 — 从 "1." 到 "技术领域" 或 "发明内容"
RE_CLAIMS = re.compile(r"1[．\.]\s*(.+?)(?=技术领域|发明内容|附图说明|\Z)", re.DOTALL)

# 说明书 — 从 "技术领域" 或 "发明内容" 到 "附图说明"
RE_DESC = re.compile(r"(?:技术领域|发明内容)\s*(.+?)(?=附图说明|\Z)", re.DOTALL)


def _clean_pdfminer_noise(text: str) -> str:
    """清理 pdfminer 提取的页码噪声。
    
    pdfminer 会在每页之间插入孤立的数字/字母标记：
      A\\n0\\n4\\n0\\n8  → 移除
      权\\u3000利\\u3000要\\u3000求\\u3000书 → 合并
    """
    if not text:
        return ""
    # 移除孤立的分页字符序列（单字拆分加空格）
    text = re.sub(r"\b(?:说|明|书|页|权|利|要|求|图|附)\b", "", text)
    # 移除孤立的页码数字（单独一行的数字）
    text = re.sub(r"\n\d+\s*$", "\n", text, flags=re.MULTILINE)
    # 移除 CN 122158040 A + 数字 的页脚标记
    text = re.sub(r"\nCN\s*\d+\s*[A-Z].*", "\n", text)
    # 移除 \\u000c 换页符
    text = text.replace("\f", "\n")
    # 移除多个孤立的单个字符行（A、B、C等）
    text = re.sub(r"\n[A-Z]\n", "\n", text)
    # 压缩连续空格和空行
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_patent_fields(text: str) -> dict:
    """从专利文本中提取结构化字段。

    Args:
        text: pdfminer/PyPDF2 提取的纯文本。

    Returns:
        {
            "title": str,
            "patent_number": str,       # 申请号
            "filing_date": str,         # 申请日
            "publication_number": str,  # 公开号
            "publication_date": str,    # 公开日
            "ipc_codes": list[str],
            "applicants": list[str],
            "inventors": list[str],
            "priority_number": str,
            "abstract": str,
            "claims": str,
            "description": str,
            "patent_agency": str,
            "patent_agent": str,
            "_missing": list[str],      # 正则未能提取的字段名
        }
    """
    text = _clean_pdfminer_noise(text)

    fields: dict = {
        "title": "",
        "patent_number": "",
        "filing_date": "",
        "publication_date": "",
        "publication_number": "",
        "ipc_codes": [],
        "applicants": [],
        "inventors": [],
        "priority_number": "",
        "abstract": "",
        "claims": "",
        "description": "",
        "patent_agency": "",
        "patent_agent": "",
        "_missing": [],
    }

    # 申请公布号: CN122158040A
    m = re.search(rf"[（(]10[）)]\s*申请公布号\s*(CN[\s\dA-Z]+)", text)
    if m:
        fields["publication_number"] = m.group(1).replace(" ", "")
    else:
        m = re.search(r"(CN\s*\d{9,12}\s*[A-Z])", text)
        if m:
            fields["publication_number"] = m.group(1).replace(" ", "")

    # (21) 申请号
    m = RE_APP_NUM.search(text)
    if m:
        fields["patent_number"] = m.group(1).replace(" ", "")

    # (22) 申请日
    m = RE_FILING_DATE.search(text)
    if m:
        fields["filing_date"] = m.group(1)

    # (43) 申请公布日
    m = RE_PUB_DATE.search(text)
    if m:
        fields["publication_date"] = m.group(1)
    if not fields["publication_date"]:
        # 全文中的第二个 YYYY.MM.DD 日期
        dates = re.findall(r"\d{4}\.\d{2}\.\d{2}", text)
        filing = fields["filing_date"]
        for d in dates:
            if d != filing:
                fields["publication_date"] = d
                break

    # (54) 发明名称
    m = RE_TITLE.search(text)
    if m:
        fields["title"] = _clean_text(m.group(1))

    # (57) 摘要
    m = RE_ABSTRACT.search(text)
    if m:
        fields["abstract"] = _clean_text(m.group(1))

    # (51) IPC 分类号
    ipc_matches = RE_IPC.findall(text)
    # 去重 + 保留顺序
    seen = set()
    for ipc in ipc_matches:
        clean = ipc.strip()
        if clean not in seen:
            seen.add(clean)
            fields["ipc_codes"].append(clean)

    # (71) 申请人 — 到 (72) 之前
    m = re.search(r"[（(]71[）)]\s*(.*?)(?=[（(]72[）)])", text, re.DOTALL)
    if m:
        block = m.group(1)
        # 从块中提取所有 "申请人 XXX" 格式的名称
        for name in re.findall(r"申请人\s*([^\d(]+?)(?:\s*(?=申请人|地址|\Z))", block):
            name = name.strip().rstrip("\u3000")
            if name:
                fields["applicants"].append(name)
        # 也检查没有前缀的直接人名（某些格式）
        if not fields["applicants"]:
            for line in block.split("\n"):
                line = line.strip()
                if "地址" not in line and line:
                    fields["applicants"].append(line.lstrip("申请人").strip())

    # (72) 发明人 — 到 (74) 之前
    m = re.search(r"[（(]72[）)]\s*(.*?)(?=[（(]74[）)]|[（(]51[）)]|\Z)", text, re.DOTALL)
    if m:
        raw = m.group(1).strip()
        raw = re.sub(r"^\s*发明人[\s\u3000:：]*", "", raw)  # 去掉前缀
        raw = re.sub(r"\d+$", "", raw).strip()
        inventors = _split_inventors(raw)
        fields["inventors"] = [i for i in inventors if i and len(i) > 1 and "发明人" not in i]

    # (74) 专利代理 — 兼容全角/半角括号
    m = re.search(r"[（(]74[）)]\s*(.*?)(?=[（(]51[）)]|\Z)", text, re.DOTALL)
    if m:
        block = m.group(1)
        m_agency = re.search(r"专利代理机构\s*(.+?)(?:\s+\d{3,}|$)", block)
        if m_agency:
            fields["patent_agency"] = m_agency.group(1).strip()
        m_agent = re.search(r"专利代理师\s*(.+?)$", block, re.MULTILINE)
        if m_agent:
            fields["patent_agent"] = m_agent.group(1).strip()

    # 权利要求书
    m = RE_CLAIMS.search(text)
    if m:
        fields["claims"] = _clean_text(m.group(1))

    # 说明书
    m = RE_DESC.search(text)
    if m:
        desc = m.group(1)
        # 去掉开头可能的标点噪声
        desc = re.sub(r"^[，,、。\s]+", "", desc)
        fields["description"] = _clean_text(desc)

    # 检查缺失的关键字段
    required = ["title", "patent_number", "filing_date"]
    for key in required:
        if not fields.get(key):
            fields["_missing"].append(key)

    return fields


# ── 百家姓（扩展版，覆盖98%中国人口）──
_SURNAMES = (
    "王李张刘陈杨赵黄周吴徐孙马胡朱郭何罗高林"
    "梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕"
    "苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任"
    "姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦"
    "江史顾侯邵孟龙万段漕钱汤尹黎易常武乔贺"
    "赖龚文庞樊兰殷施陶洪翟安颜倪严牛温芦"
    "季俞章鲁葛韦申尤毕聂丛焦向柳邢骆岳齐"
    "宫卞栗"
)


def _split_inventors(raw: str) -> list[str]:
    """智能分割发明人列表，处理 PaddleOCR 无空格拼接的情况"""
    if not raw:
        return []

    # 1. 先按换行分割
    parts = raw.replace("\r", "").split("\n")
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 2. 有空格 → 按空格分割
        if " " in part or "\u3000" in part:
            for name in re.split(r"[\s\u3000]+", part):
                name = name.strip().rstrip("\u3000")
                if name and len(name) > 1:
                    result.append(name)
        else:
            # 3. 无空格 → 用姓氏分割
            names = _split_by_surname(part)
            result.extend(n for n in names if n and len(n) > 1)
    return result


def _split_by_surname(text: str) -> list[str]:
    """用百家姓分割连续人名。逐个字符扫描，发现姓氏即截取2-4字为一个人名。"""
    names = []
    i = 0
    while i < len(text):
        # 检查当前位置是否是姓氏（优先2字姓）
        surname_len = 2 if i + 1 < len(text) and text[i:i+2] in _SURNAMES else (1 if text[i] in _SURNAMES else 0)
        if surname_len > 0:
            # 取 2-4 字（姓名长度通常范围）
            for name_len in range(4, 1, -1):
                end = i + name_len
                if end > len(text):
                    continue
                # 仅当末尾是另一个姓氏或字符串结束时截断
                if end >= len(text):
                    names.append(text[i:end])
                    i = end
                    break
                next_is_surname = (text[end] in _SURNAMES or (end+1 < len(text) and text[end:end+2] in _SURNAMES)
                                   or text[end] in "、，,")
                if next_is_surname:
                    names.append(text[i:end])
                    i = end
                    break
            else:
                i += 1  # 无法确定长度，跳过
        else:
            i += 1  # 不是姓氏
    return names


def _find_name_end(text: str, start: int) -> int:
    """找到中文姓名的结束位置，在下一个姓氏前停止"""
    max_len = min(4, len(text) - start)
    for l in range(max_len, 1, -1):
        end = start + l
        if end >= len(text):
            return end
        # 检查下个位置是否为新姓氏
        if text[end] in _SURNAMES or (end + 1 < len(text) and text[end:end+2] in _SURNAMES):
            return end
        # 常见分隔符
        if text[end] in "、，, \n\t\r":
            return end
    return start + 4


def _clean_text(text: str) -> str:
    """清理提取文本中的格式噪声"""
    if not text:
        return ""
    # 修正 OCR 常见误识别
    text = re.sub(r"^-(?=种)", "一", text)  # PaddleOCR: -种 → 一种
    # 移除页码标记
    text = re.sub(r"---\s*第\s*\d+\s*页\s*---", "", text)
    # 移除页面脚注标记：书N/N页N、CN 号码 A
    text = re.sub(r"[权权]+\s*利\s*[要要]+\s*[求求]+\s*书\s*\d+/\d+页\s*\d+", "", text)
    text = re.sub(r"说?\s*明?\s*书?\s*\d+/\d+页\s*\d+", "", text)
    text = re.sub(r"\nCN\s*\d+\s*[A-Z](?:\s*\d+)?", "\n", text)
    text = re.sub(r"\n[A-Z]\s*\n", "\n", text)
    # 移除孤立的页脚数字行
    text = re.sub(r"\n\d+\s*$", "\n", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    # 折叠多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_with_ai_fallback(text: str, ai_call_fn=None) -> dict:
    """提取字段，对正则失败的字段用 AI 补充。

    Args:
        text: 专利文本
        ai_call_fn: 异步调用函数，async (system_prompt, user_prompt) → dict

    Returns:
        同 extract_patent_fields()
    """
    fields = extract_patent_fields(text)

    # 如果有关键字段缺失且有 AI 回调，尝试 AI 提取
    if fields["_missing"] and ai_call_fn:
        try:
            import asyncio
            system_prompt = "你是一个专利文档解析专家。从以下专利文本中提取指定字段。只输出JSON。"
            user_prompt = f"""从以下专利文本中提取缺失字段: {fields['_missing']}

文本内容:
{text[:8000]}

输出格式:
{{"title": "…", "patent_number": "…", "filing_date": "…"}}
只输出缺失的字段。
"""
            result = asyncio.run(ai_call_fn(system_prompt, user_prompt))
            if isinstance(result, dict):
                for key in fields["_missing"]:
                    if key in result and result[key]:
                        fields[key] = result[key]
                fields["_missing"] = [k for k in fields["_missing"] if not fields.get(k)]
        except Exception as e:
            logger.warning(f"AI 补充提取失败: {e}")

    return fields
