"""
专利结构化提取器 — 从 PDF 文本中提取专利元数据字段

策略：
  1. AI 模型提取结构化字段（使用已配置的对话模型）
  2. 正则兜底（AI 不可用时）
"""

import logging
import re

EXTRACT_SYSTEM_PROMPT = """你是一个专利文档结构化提取器。从专利文本中提取以下字段，只输出JSON：

{{
  "title": "发明名称",
  "patent_number": "申请号",
  "filing_date": "申请日",
  "publication_number": "公开号",
  "publication_date": "公开日",
  "ipc_codes": ["IPC分类号"],
  "applicants": ["申请人"],
  "inventors": ["发明人"],
  "abstract": "摘要内容",
  "claims": "权利要求书内容",
  "description": "说明书内容",
  "patent_agency": "专利代理机构",
  "patent_agent": "专利代理人"
}}

如果某个字段在文本中不存在，用空字符串或空数组代替。
不要输出任何其他文字。"""


async def extract_patent_fields_ai(text: str) -> dict | None:
    """使用 extract_model 提取专利结构化字段"""
    try:
        from app.algorithm.model_resolver import model_resolver

        s = model_resolver.get_assigned_settings()
        extract_model_id = s.get("extract_model") or ""

        if not extract_model_id:
            logger.info("extract_model 未配置，跳过 AI 提取")
            return None
        if ":" not in extract_model_id:
            logger.warning(f"extract_model 格式无效: {extract_model_id}")
            return None

        from app.algorithm.ai_client import chat_completion

        result = await chat_completion(
            system_prompt=EXTRACT_SYSTEM_PROMPT,
            user_prompt=f"请从以下专利文本中提取结构化字段：\n\n{text[:8000]}",
            response_format=dict,
            temperature=0.05,
            max_retries=2,
            model_id=extract_model_id,
        )

        if isinstance(result, dict):
            for arr_field in ["ipc_codes", "applicants", "inventors"]:
                if not isinstance(result.get(arr_field), list):
                    result[arr_field] = [result[arr_field]] if result.get(arr_field) else []
            for str_field in ["title", "patent_number", "abstract", "claims"]:
                if not isinstance(result.get(str_field), str):
                    result[str_field] = str(result.get(str_field, ""))
            return result
    except Exception as e:
        logger.warning(f"AI 提取失败: {e}")
    return None


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

# IPC 分类号: G16H 40/20 或 LOC(15)Cl.23-04
RE_IPC = re.compile(r"(?:[A-Z]\d+\w*\s+\d+/\d+|\d+-\d+)")

# 发明名称 — 从 (54) 到 (57)摘要 或下一个括号标记，匹配完整内容
RE_TITLE = re.compile(
    rf"{_RE_BRACKET}54[）)](?:发明名称|实用新型名称|专利名称|使用外观设计的产品名称)?\s*([\s\S]+?)(?={_RE_BRACKET}5[78][）)]|\Z)",
    re.DOTALL,
)

# 摘要 — 从 (57)摘要 到下一个章节，不对 CN 专利号截断
RE_ABSTRACT = re.compile(
    rf"{_RE_BRACKET}57[）)](?:摘要|外观设计简要说明)\s*(.+?)(?=\n技术领域|\n背景技术|权利要求书|\n\s*[1．\.]\s|\Z)", re.DOTALL
)

# 权利要求书 — 从 "1." 到 "技术领域" 或 "发明内容"
RE_CLAIMS = re.compile(r"(?:^|\n)([1．\.]\s*.+?)(?=技术领域|发明内容|附图说明|\Z)", re.DOTALL)

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

    优先使用 AI 提取（调用已配置的 chat_model），
    AI 不可用时回退到正则提取。

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
            "abstract": str,
            "claims": str,
            "description": str,
            "patent_agency": str,
            "patent_agent": str,
            "_missing": list[str],
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
        "abstract": "",
        "claims": "",
        "description": "",
        "patent_agency": "",
        "patent_agent": "",
        "_missing": [],
    }

    # 申请公布号: CN122158040A
    m = re.search(r"[（(]10[）)]\s*申请公布号\s*(CN[\s\dA-Z]+)", text)
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
        title = _clean_text(m.group(1))
        # 外观设计专利：去掉 "立体图" 之后的格式描述
        title = re.sub(r"(?:立体图|图片|照片)[\s\S]*", "", title, flags=re.DOTALL)
        title = title.split("\n")[0].strip()
        title = re.sub(r"^(?:发明名称|实用新型名称|使用外观设计的产品名称)\s*", "", title)  # 只取第一行
        fields["title"] = title.strip().rstrip("（")

    # (57) 摘要（设计专利无此字段，可选）
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

    # (71) 申请人 — 到 (72) 之前，或 (73) 专利权人（实用新型/外观设计）
    m = re.search(r"[（(]71[）)]\s*(.*?)(?=[（(]72[）)])", text, re.DOTALL)
    if not m:
        m = re.search(r"[（(]73[）)]\s*(.*?)(?=[（(]72[）)])", text, re.DOTALL)
    if m:
        block = m.group(1)
        # 从块中提取所有 "申请人 XXX" 格式的名称
        for name in re.findall(r"(?:申请人|专利权人)\s*([^\d(]+?)(?:\s*(?=申请人|专利权人|地址|\Z))", block):
            name = name.strip().rstrip("\u3000")
            if name:
                fields["applicants"].append(name)
        # 也检查没有前缀的直接人名（某些格式）
        if not fields["applicants"]:
            for line in block.split("\n"):
                line = line.strip()
                if "地址" not in line and line:
                    fields["applicants"].append(re.sub(r"^(?:申请人|专利权人)\s*", "", line).strip())

    # (72) 发明人/设计人 — 到 (74) 之前
    m = re.search(r"[（(]72[）)]\s*(.*?)(?=[（(]74[）)]|[（(]51[）)]|\Z)", text, re.DOTALL)
    if m:
        raw = m.group(1).strip()
        raw = re.sub(r"^\s*(?:发明人|设计人)[\s\u3000:：]*", "", raw)  # 去掉前缀
        raw = re.sub(r"\d+$", "", raw).strip()
        inventors = _split_inventors(raw)
        fields["inventors"] = [i for i in inventors if i and len(i) > 1 and i not in ("发明人", "设计人")]

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


def extract_deepseek_fields(text: str) -> dict:
    """专用于 DeepSeek-OCR 输出的字段提取

    DeepSeek-OCR 格式特点：
      - (54)(57) 在 (51) 后面
      - 可能缺少 "权利要求书" 章节标记
      - (74) 代理编号被空行包裹
    """
    fields = dict(_empty_fields().items())
    text = _clean_deepseek_text(text)

    # (10) 申请公布号
    m = re.search(r"[（(]10[）)]\s*申请公布号\s*(CN[\s\dA-Z]+)", text)
    if m:
        fields["publication_number"] = m.group(1).replace(" ", "")

    # (21) 申请号
    m = re.search(r"[（(]21[）)][^0-9]*?(\d{12}\.?\d*)", text)
    if m:
        fields["patent_number"] = m.group(1).replace(" ", "")

    # (22) 申请日
    m = re.search(r"[（(]22[）)][^0-9]*?(\d{4}\.\d{2}\.\d{2})", text)
    if m:
        fields["filing_date"] = m.group(1)

    # (43) 公开日
    m = re.search(r"[（(]43[）)][^0-9]*?(\d{4}\.\d{2}\.\d{2})", text)
    if m:
        fields["publication_date"] = m.group(1)

    # (54) 发明名称 — 到 (57)摘要
    m = re.search(r"[（(]54[）)]发明名称\s*(.+?)(?=[（(]57[）)]摘要|\Z)", text, re.DOTALL)
    if m:
        fields["title"] = _clean_text(m.group(1))

    # (57) 摘要 — 到下一个章节
    m = re.search(r"[（(]57[）)]摘要\s*(.+?)(?=\n技术领域|\n背景技术|权利要求书|\n\s*1[．\.]\s|\Z)", text, re.DOTALL)
    if m:
        abstract = m.group(1)
        if len(abstract) > 500:
            abstract = abstract[: abstract.find("。") + 1] if "。" in abstract[:500] else abstract[:300]
        fields["abstract"] = _clean_text(abstract)

    # (51) 全部 IPC
    ipcs = re.findall(r"([A-Z]\d+\w*\s+\d+/\d+)", text)
    seen = set()
    for ipc in ipcs:
        clean = ipc.strip()
        if clean not in seen:
            seen.add(clean)
            fields["ipc_codes"].append(clean)

    # (71) 申请人
    m = re.search(r"[（(]71[）)]\s*(.*?)(?=[（(]72[）)])", text, re.DOTALL)
    if m:
        block = m.group(1)
        for name in re.findall(r"申请人\s*([^\d(]+?)(?:\s*(?=申请人|地址|\Z))", block):
            name = name.strip().rstrip("\u3000")
            if name:
                fields["applicants"].append(name)
        if not fields["applicants"]:
            for line in block.split("\n"):
                line = line.strip()
                if "地址" not in line and line and "申请人" not in line:
                    fields["applicants"].append(line)

    # (72) 发明人
    m = re.search(r"[（(]72[）)]\s*(.*?)(?=[（(]74[）)]|[（(]51[）)]|\Z)", text, re.DOTALL)
    if m:
        raw = m.group(1).strip()
        raw = re.sub(r"^\s*发明人[\s\u3000:：]*", "", raw)
        inventors = _split_inventors(raw)
        fields["inventors"] = [i for i in inventors if i and len(i) > 1]

    # (74) 专利代理
    m = re.search(r"[（(]74[）)]\s*(.*?)(?=[（(]51[）)]|\Z)", text, re.DOTALL)
    if m:
        block = m.group(1)
        m_a = re.search(r"专利代理机构\s+(.+?)(?=\n+专利代理师|\Z)", block, re.DOTALL)
        if m_a:
            agency = re.sub(r"\s+", " ", m_a.group(1)).strip()
            # 去掉末尾的注册号（纯数字）
            agency = re.sub(r"\s*\d+\s*$", "", agency).strip()
            fields["patent_agency"] = agency
        m_ag = re.search(r"专利代理师\s+(.+)", block)
        if m_ag:
            fields["patent_agent"] = m_ag.group(1).strip()

    # 权利要求 — 从 "1." 到 "技术领域" 或 "[0001]"
    m = re.search(r"(?:^|\n)\s*[1．\.]\s*(.+?)(?=技术领域|发明内容|\[0001\]|附图说明|\Z)", text, re.DOTALL)
    if m:
        fields["claims"] = _clean_text(m.group(1))

    # 说明书 — 从 "技术领域" 或 "[0001]" 到 "附图说明"
    m = re.search(r"(?:技术领域|\[0001\])\s*(.+?)(?=附图说明|\Z)", text, re.DOTALL)
    if m:
        desc = m.group(1)
        desc = re.sub(r"^[，,、。\s]+", "", desc)
        fields["description"] = _clean_text(desc)

    return fields


def _empty_fields() -> dict:
    return {
        "title": "",
        "patent_number": "",
        "filing_date": "",
        "publication_date": "",
        "publication_number": "",
        "ipc_codes": [],
        "applicants": [],
        "inventors": [],
        "abstract": "",
        "claims": "",
        "description": "",
        "patent_agency": "",
        "patent_agent": "",
        "_missing": [],
    }


def _clean_deepseek_text(text: str) -> str:
    """清理 DeepSeek-OCR 特有的格式"""
    if not text:
        return ""
    text = re.sub(r"---\s*第\s*\d+\s*页\s*---", "", text)
    text = re.sub(r"\f", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _split_inventors(raw: str) -> list[str]:
    """分割发明人列表（按空格/换行分割）"""
    if not raw:
        return []
    raw = re.sub(r"^\s*发明人[\s\u3000:：]*", "", raw)
    raw = re.sub(r"\d+$", "", raw).strip()
    # 按换行、空格、全角空格分割
    names = re.split(r"[\s\u3000]+", raw)
    return [n.strip().rstrip("\u3000") for n in names if n and len(n.strip()) > 1]


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
            user_prompt = f"""从以下专利文本中提取缺失字段: {fields["_missing"]}

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
