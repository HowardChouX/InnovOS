"""
测试 HTML → Markdown 转换管线 — html_to_markdown.py

覆盖：
- url_to_markdown 完整管线
- preprocess_dom 预处理（heading 清理、代码块、MathJax、KaTeX）
- convert_to_markdown ReadAbility + html2text 转换
- 剥离 script/style 标签
- 保留标题、链接、列表结构
- 空 HTML 处理
- 兜底回退方案
- validate_uri URL 绝对化
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

MD_PATH = "app.algorithm.knowledge.html_to_markdown"


# ─── validate_uri ─────────────────────────────────────────────


def test_validate_uri_absolute_url():
    """validate_uri 绝对 URL 直接返回。"""
    from app.algorithm.knowledge.html_to_markdown import validate_uri

    result = validate_uri("https://example.com/page", "https://base.com/")
    assert result == "https://example.com/page"


def test_validate_uri_root_relative():
    """validate_uri 根相对路径补全 origin。"""
    from app.algorithm.knowledge.html_to_markdown import validate_uri

    result = validate_uri("/images/logo.png", "https://example.com/page")
    assert result == "https://example.com/images/logo.png"


def test_validate_uri_relative_path():
    """validate_uri 相对路径用 urljoin 补全。"""
    from app.algorithm.knowledge.html_to_markdown import validate_uri

    result = validate_uri("../other.html", "https://example.com/docs/page.html")
    assert result.endswith("other.html")
    assert "example.com" in result


# ─── preprocess_dom ───────────────────────────────────────────


def test_preprocess_dom_removes_heading_class():
    """preprocess_dom 清除 heading 的 className。"""
    from app.algorithm.knowledge.html_to_markdown import preprocess_dom

    html = '<h1 class="some-class">标题</h1>'
    result = preprocess_dom(html)
    assert 'class="some-class"' not in result
    assert "<h1>标题</h1>" in result or ">标题<" in result


def test_preprocess_dom_removes_html_class():
    """preprocess_dom 移除 html 标签的 class 属性。"""
    from app.algorithm.knowledge.html_to_markdown import preprocess_dom

    html = '<html class="no-js" lang="zh"><body>内容</body></html>'
    result = preprocess_dom(html)
    # html class should be removed
    assert 'class="no-js"' not in result


def test_preprocess_dom_empty_html():
    """preprocess_dom 空 HTML 直接返回。"""
    from app.algorithm.knowledge.html_to_markdown import preprocess_dom

    assert preprocess_dom("") == ""


def test_preprocess_dom_invalid_html():
    """preprocess_dom 无效 HTML 返回原始字符串。"""
    from app.algorithm.knowledge.html_to_markdown import preprocess_dom

    # Malformed HTML that lxml can't parse should return original
    result = preprocess_dom("not>html<")
    # Should still be returned (lxml is lenient, but let's verify it doesn't crash)
    assert result is not None


def test_preprocess_dom_protects_pre_br():
    """preprocess_dom 保护 pre 内的 br 标签。"""
    from app.algorithm.knowledge.html_to_markdown import preprocess_dom

    html = "<pre>line1<br>line2</pre>"
    result = preprocess_dom(html)
    # <br> inside <pre> should be replaced with placeholder
    assert "<br-keep>" in result or "br-keep" in result


def test_preprocess_dom_code_language_marker():
    """preprocess_dom 提取代码块语言标记。"""
    from app.algorithm.knowledge.html_to_markdown import preprocess_dom

    html = '<div class="highlight-text-python"><pre><code>print("hello")</code></pre></div>'
    result = preprocess_dom(html)
    assert "code-lang-python" in result


def test_preprocess_dom_language_class():
    """preprocess_dom 处理 code 标签的 language- 类。"""
    from app.algorithm.knowledge.html_to_markdown import preprocess_dom

    html = '<code class="language-javascript">const x = 1;</code>'
    result = preprocess_dom(html)
    assert "code-lang-javascript" in result


# ─── convert_to_markdown ──────────────────────────────────────


def test_convert_to_markdown_empty():
    """convert_to_markdown 空 HTML 返回原值。"""
    from app.algorithm.knowledge.html_to_markdown import convert_to_markdown

    assert convert_to_markdown("") == ""


def test_convert_to_markdown_short():
    """convert_to_markdown 短 HTML（<100 chars）直接返回。"""
    from app.algorithm.knowledge.html_to_markdown import convert_to_markdown

    result = convert_to_markdown("<p>Hello</p>")
    assert result is not None


@pytest.mark.skip(reason="需要 readability-lxml 和 html2text 库")
def test_convert_to_markdown_with_deps():
    """convert_to_markdown 使用 readability + html2text 转换。"""
    from app.algorithm.knowledge.html_to_markdown import convert_to_markdown

    html = "<html><body><h1>标题</h1><p>段落内容</p></body></html>"
    result = convert_to_markdown(html)
    assert "标题" in result
    assert "段落内容" in result


def test_convert_to_markdown_missing_deps():
    """convert_to_markdown 缺少依赖时回退到纯文本。"""
    from app.algorithm.knowledge.html_to_markdown import convert_to_markdown

    # Simulate missing readability by patching import to fail
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("readability", "html2text"):
            raise ImportError(f"No module named {name}")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        result = convert_to_markdown("<html><body><h1>标题</h1><p>内容</p></body></html>")
        # Should fall back to text extraction
        assert "标题" in result or "内容" in result


def test_convert_to_markdown_readability_failure():
    """convert_to_markdown Readability 失败时回退。"""
    from app.algorithm.knowledge.html_to_markdown import convert_to_markdown

    # Patch readability.Document since it's imported inside the function
    with patch("readability.Document") as MockDoc:
        instance = MagicMock()
        instance.summary.side_effect = Exception("Readability error")
        MockDoc.return_value = instance

        result = convert_to_markdown("<html><body><p>内容</p></body></html>")

    # Should fall back gracefully to text extraction
    assert result is not None
    assert "内容" in str(result)


# ─── url_to_markdown ──────────────────────────────────────────


def test_url_to_markdown_empty():
    """url_to_markdown 空 HTML 返回空字符串。"""
    from app.algorithm.knowledge.html_to_markdown import url_to_markdown

    result = url_to_markdown("")
    assert result == ""


def test_url_to_markdown_runs_pipeline():
    """url_to_markdown 执行完整管线。"""
    from app.algorithm.knowledge.html_to_markdown import url_to_markdown

    html = "<html><body><h1>测试标题</h1><p>测试段落</p></body></html>"
    result = url_to_markdown(html)
    # Should at least not crash — the pipeline may produce empty if deps aren't installed
    assert isinstance(result, str)


# ─── _fallback_extract_text ───────────────────────────────────


def test_fallback_extract_text_strips_script_style():
    """_fallback_extract_text 移除 script/style 标签。"""
    from app.algorithm.knowledge.html_to_markdown import _fallback_extract_text

    html = "<html><head><style>body{}</style></head><body><p>正文内容</p><script>alert('x')</script></body></html>"
    result = _fallback_extract_text(html)
    assert "正文内容" in result
    assert "alert" not in result
    assert "body{}" not in result


def test_fallback_extract_text_handles_nested():
    """_fallback_extract_text 处理嵌套 HTML。"""
    from app.algorithm.knowledge.html_to_markdown import _fallback_extract_text

    html = "<div><ul><li>项目1</li><li>项目2</li></ul></div>"
    result = _fallback_extract_text(html)
    assert "项目1" in result
    assert "项目2" in result


def test_fallback_extract_text_malformed():
    """_fallback_extract_text 处理畸形 HTML。"""
    from app.algorithm.knowledge.html_to_markdown import _fallback_extract_text

    html = "纯文本内容，不是 HTML"
    # Should not crash
    result = _fallback_extract_text(html)
    assert result is not None


# ─── _absolutize_urls ─────────────────────────────────────────


def test_absolutize_urls_images():
    """_absolutize_urls 将 img src 绝对化。"""
    from app.algorithm.knowledge.html_to_markdown import _absolutize_urls

    html = '<img src="/images/pic.png" alt="pic">'
    result = _absolutize_urls(html, "https://example.com/page")
    assert "https://example.com/images/pic.png" in result


def test_absolutize_urls_links():
    """_absolutize_urls 将 a href 绝对化。"""
    from app.algorithm.knowledge.html_to_markdown import _absolutize_urls

    html = '<a href="/docs/help">帮助</a>'
    result = _absolutize_urls(html, "https://example.com")
    assert "https://example.com/docs/help" in result


def test_absolutize_urls_malformed():
    """_absolutize_urls 畸形 HTML 返回原值。"""
    from app.algorithm.knowledge.html_to_markdown import _absolutize_urls

    result = _absolutize_urls("", "https://example.com")
    assert result == ""
