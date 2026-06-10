"""
HTML → Markdown 转换管线 — 移植自 MarkDownload 项目的 Readability.js → Turndown 流程。

完整复现 MarkDownload 的核心管线：
1. DOM 预处理（heading 清理、代码块检测、语言类提取）
2. Readability 提取正文
3. URL 绝对路径解析（validateUri）
4. html2text 转 Markdown + 后处理

对比原始 html2text，本模块增加了：
- MarkDownload 风格的 DOM 预处理
- Cloudflare 保护页面支持（通过 url_fetcher）
- 更好的相对 URL 解析
- 表格和代码块保留优化
- 中文内容优化（无自动换行、保留全角字符）
"""
import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from lxml import etree, html as lxml_html

logger = logging.getLogger(__name__)


# ── URL 验证（移植自 MarkDownload background.js validateUri）───────────────

def validate_uri(href: str, base_uri: str) -> str:
    """验证并绝对化 URL 引用。

    移植自 MarkDownload 的 validateUri().
    - 若已经是绝对 URL，直接返回
    - 若以 '/' 开头，补全 origin
    - 否则相对于当前页面路径补全
    """
    parsed = urlparse(href)
    if parsed.scheme and parsed.netloc:
        return href  # 已经是绝对 URL

    base_parsed = urlparse(base_uri)
    if href.startswith("/"):
        return f"{base_parsed.scheme}://{base_parsed.netloc}{href}"
    else:
        # 相对于当前路径
        return urljoin(base_uri, href)


# ── DOM 预处理（移植自 MarkDownload getArticleFromDom）─────────────────────

def preprocess_dom(html: str, base_url: str = "") -> str:
    """对原始 HTML 执行 MarkDownload 风格的 DOM 预处理。

    处理项目（按顺序）：
    1. 清理 heading 的 className（防止 Readability 误删）
    2. 移除 <html> 的 class 属性
    3. 提取代码块语言标记
    4. 保护 <pre> 内的 <br> 标签
    5. 处理 MathJax / KaTeX（若存在）

    Args:
        html: 原始 HTML 字符串
        base_url: 基准 URL（用于解析相对路径）

    Returns:
        预处理后的 HTML
    """
    if not html:
        return html

    try:
        root = lxml_html.fromstring(html)
    except Exception as e:
        logger.warning("lxml 解析 HTML 失败: %s — 返回原始 HTML", e)
        return html

    # 1. 清理 heading className → 防止 Readability 因 class 中包含特定关键词而删除 heading
    for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        for el in root.cssselect(tag):
            el.attrib.pop("class", None)
            # 重新序列化以触发 DOM 更新（对标 outerHTML = outerHTML）
    # 实际上 lxml 不需要 outerHTML 技巧，直接清理 class 即可

    # 2. 移除 <html> 的 class 属性
    html_el = root.tag if hasattr(root, "tag") else None
    if root.tag == "html" and "class" in root.attrib:
        root.attrib.pop("class", None)

    # 3. 代码块语言标记提取
    # 3a. highlight-text / highlight-source 模式
    for el in root.cssselect("[class*=highlight-text], [class*=highlight-source]"):
        class_name = el.get("class", "")
        m = re.search(r"highlight-(?:text|source)-([a-z0-9]+)", class_name)
        if m and el.find("pre") is not None:
            pre = el.find("pre")
            if pre is not None:
                pre.set("id", f"code-lang-{m.group(1)}")

    # 3b. language- 模式（如 <code class="language-python">）
    for el in root.cssselect("[class*=language-]"):
        class_name = el.get("class", "")
        m = re.search(r"language-([a-z0-9]+)", class_name)
        if m:
            el.set("id", f"code-lang-{m.group(1)}")

    # 3c. codehilite 模式
    for el in root.cssselect(".codehilite > pre"):
        code_child = el.find("code")
        class_name = el.get("class", "")
        if code_child is None and "language" not in class_name:
            el.set("id", "code-lang-text")

    # 4. 保护 <pre> 内的 <br> → Readability 会删掉 <br>，用占位符保护
    for br in root.cssselect("pre br"):
        br_placeholder = etree.Comment("br-keep")
        br.addprevious(br_placeholder)
        br.getparent().remove(br)

    # 5. MathJax 3 — 通过属性标记的公式
    for el in root.cssselect("[markdownload-latex]"):
        tex = el.get("markdownload-latex", "")
        display = el.get("display", "")
        inline = display != "true"
        new_tag = "i" if inline else "p"
        new_el = etree.SubElement(el.getparent(), new_tag)
        new_el.text = tex
        # 生成随机 id 存储公式信息
        import uuid
        math_id = f"math-{uuid.uuid4().hex[:12]}"
        new_el.set("id", math_id)
        # 移除原节点
        el.getparent().remove(el)

    # 6. KaTeX — 提取 annotation 内容
    for el in root.cssselect(".katex-mathml"):
        annotation = el.find(".//annotation")
        if annotation is not None and annotation.text:
            import uuid
            math_id = f"math-{uuid.uuid4().hex[:12]}"
            el.set("id", math_id)

    # 序列化回字符串
    result = etree.tostring(root, encoding="unicode", method="html")

    # 恢复 br 占位符 → 用自定义标签替代
    result = result.replace("<!--br-keep-->", "<br-keep></br-keep>")

    return result


# ── Readability + html2text 管线 ──────────────────────────────────────────

def convert_to_markdown(html: str, base_url: str = "") -> str:
    """Readability 提取正文 → html2text 转 Markdown。

    参考 MarkDownload 的 pipeline:
    getArticleFromDom() → Readability.parse() → turndown()

    本函数使用 Python 对应库:
    - readability-lxml (Document) ↔ Mozilla Readability.js
    - html2text              ↔ Turndown.js

    Args:
        html: 已预处理的 HTML
        base_url: 用于解析相对 URL

    Returns:
        Markdown 文本
    """
    if not html or len(html) < 100:
        return html or ""

    try:
        from readability import Document
        import html2text
    except ImportError as e:
        logger.warning("缺少依赖: %s — 请安装 readability-lxml 和 html2text", e)
        return _fallback_extract_text(html)

    # ── Step 1: Readability 提取正文 ──
    try:
        doc = Document(html)
        summary_html = doc.summary()
    except Exception as e:
        logger.warning("Readability 解析失败: %s — 回退到纯文本", e)
        return _fallback_extract_text(html)

    if not summary_html or len(summary_html) < 100:
        logger.warning("Readability 提取内容过少（%d chars）— 回退到纯文本", len(summary_html or ""))
        return _fallback_extract_text(html)

    # ── Step 2: 绝对化 URL（移植 MarkDownload 的 validateUri）──
    if base_url:
        summary_html = _absolutize_urls(summary_html, base_url)

    # ── Step 3: html2text 转 Markdown ──
    try:
        h = html2text.HTML2Text()
        h.body_width = 0               # 不自动换行（对中文友好）
        h.ignore_links = False         # 保留链接
        h.ignore_images = False        # 保留图片
        h.protect_links = True         # 保护链接中的 Markdown 语法
        h.bypass_tables = False        # 保留表格
        h.mark_code = True             # 代码块围栏
        h.ignore_emphasis = False      # 保留斜体/粗体
        h.ignore_anchors = False       # 保留锚点

        # MarkDownload 风格配置
        h.wrap_links = False           # 不要打断链接
        h.skip_internal_links = False  # 保留内部锚点
        h.reference_links = False      # 使用内联链接而非引用
        h.use_automatic_links = False  # 不要自动检测 URL
        h.google_doc = False

        md = h.handle(summary_html)

        # 清理多余的空白行（但保留段落分隔）
        md = re.sub(r"\n{4,}", "\n\n\n", md)
        return md.strip()

    except Exception as e:
        logger.warning("html2text 转换失败: %s — 回退到纯文本", e)
        return _fallback_extract_text(summary_html)


def _absolutize_urls(html: str, base_url: str) -> str:
    """将 HTML 中的相对 URL 绝对化（图片 src、链接 href）。"""
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return html

    for img in root.cssselect("img[src]"):
        src = img.get("src", "")
        img.set("src", validate_uri(src, base_url))

    for a in root.cssselect("a[href]"):
        href = a.get("href", "")
        a.set("href", validate_uri(href, base_url))

    return etree.tostring(root, encoding="unicode", method="html")


def _fallback_extract_text(html: str) -> str:
    """兜底方案：用 lxml 提取纯文本（保留段落结构）。"""
    try:
        root = lxml_html.fromstring(html)
        # 移除 script/style
        for el in root.cssselect("script, style, noscript"):
            el.getparent().remove(el)
        text = root.text_content()
        # 合并空白
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        # 最终兜底：正则去除标签
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text or html


# ── 完整管线（预处理 + 转换）────────────────────────────────────────────────

def url_to_markdown(html: str, base_url: str = "") -> str:
    """完整的 HTML → Markdown 转换管线。

    对应 MarkDownload 的完整流程:
    contentScript.getHTMLOfDocument()
    → background.getArticleFromDom()   [我们的 preprocess_dom]
    → Readability(dom).parse()          [readability-lxml]
    → turndown()                        [html2text + 后处理]

    Args:
        html: 原始网页 HTML
        base_url: 网页 URL（用于解析相对路径）

    Returns:
        转换后的 Markdown 文本
    """
    logger.info("HTML→Markdown 转换: 输入 %d bytes", len(html))

    # Step 1: DOM 预处理（MarkDownload 风格）
    processed_html = preprocess_dom(html, base_url)

    # Step 2: Readability + html2text
    markdown = convert_to_markdown(processed_html, base_url)

    logger.info("HTML→Markdown 转换完成: 输出 %d chars", len(markdown))
    return markdown
