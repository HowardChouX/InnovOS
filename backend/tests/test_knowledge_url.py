"""
测试 URL 抓取器 — url_fetcher.py

覆盖：
- fetch_url 主入口 httpx 成功返回内容
- SSRF 防护拒绝内网地址
- 无效 URL 格式/协议抛出 ValueError
- hostname 无法解析时抛出
- httpx 超时/异常降级到浏览器方案
- Cloudflare 检测
- 所有策略失败时抛出 RuntimeError
- HTML 内容提取返回文本
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

FETCHER_PATH = "app.algorithm.knowledge.url_fetcher"


# ─── Fixtures ─────────────────────────────────────────────────


def make_httpx_response(status_code=200, text="<html>ok</html>", headers=None, url_str="https://example.com"):
    """Create a mock httpx response."""
    resp = AsyncMock()
    resp.status_code = status_code
    resp.text = text
    resp.url = url_str
    resp.headers = headers or {"Content-Type": "text/html"}
    return resp


# ─── validate_url ──────────────────────────────────────────────


def test_validate_url_rejects_private_ip():
    """validate_url 拒绝内网地址。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    with patch(f"{FETCHER_PATH}._resolve_hostname", return_value=["127.0.0.1"]):
        with pytest.raises(ValueError, match="内网"):
            validate_url("http://localhost/test")


def test_validate_url_rejects_private_ip_10():
    """validate_url 拒绝 10.x.x.x 内网地址。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    with patch(f"{FETCHER_PATH}._resolve_hostname", return_value=["10.0.0.1"]):
        with pytest.raises(ValueError, match="内网"):
            validate_url("http://internal.example.com")


def test_validate_url_rejects_private_ip_192_168():
    """validate_url 拒绝 192.168.x.x 内网地址。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    with patch(f"{FETCHER_PATH}._resolve_hostname", return_value=["192.168.1.1"]):
        with pytest.raises(ValueError, match="内网"):
            validate_url("http://192.168.1.1/test")


def test_validate_url_rejects_private_ip_172_16():
    """validate_url 拒绝 172.16.x.x 内网地址。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    with patch(f"{FETCHER_PATH}._resolve_hostname", return_value=["172.16.0.5"]):
        with pytest.raises(ValueError, match="内网"):
            validate_url("http://172.16.0.5/test")


def test_validate_url_accepts_public_ip():
    """validate_url 接受公网地址。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    with patch(f"{FETCHER_PATH}._resolve_hostname", return_value=["8.8.8.8"]):
        # Should not raise
        validate_url("https://8.8.8.8/test")


def test_validate_url_invalid_format():
    """validate_url URL 格式无效时抛出。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    with pytest.raises(ValueError, match="URL 格式无效"):
        validate_url("not-a-url")


def test_validate_url_unsupported_protocol():
    """validate_url 拒绝非 http/https 协议。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    with pytest.raises(ValueError, match="不支持的 URL 协议"):
        validate_url("ftp://example.com/file")


def test_validate_url_resolution_failure():
    """validate_url 域名无法解析时抛出。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    with patch(f"{FETCHER_PATH}._resolve_hostname", return_value=[]):
        with pytest.raises(ValueError, match="无法解析域名"):
            validate_url("http://nonexistent.example.com")


def test_validate_url_rejects_localhost():
    """validate_url 拒绝 localhost。"""
    from app.algorithm.knowledge.url_fetcher import validate_url

    # Mock resolve to return private IP for localhost
    with patch(f"{FETCHER_PATH}._resolve_hostname", return_value=[]):
        with pytest.raises(ValueError, match="内网|无法解析"):
            validate_url("http://localhost")


# ─── _resolve_hostname ────────────────────────────────────────


def test_resolve_hostname_returns_ips():
    """_resolve_hostname 返回解析到的 IP 列表。"""
    from app.algorithm.knowledge.url_fetcher import _resolve_hostname

    result = _resolve_hostname("example.com")
    assert isinstance(result, list)


def test_resolve_hostname_unresolvable():
    """_resolve_hostname 无法解析时返回空列表。"""
    import socket
    from app.algorithm.knowledge.url_fetcher import _resolve_hostname

    # Mock socket to raise gaierror, simulating DNS failure
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
        result = _resolve_hostname("example.com")
        assert result == []


# ─── _is_blocked_ip ───────────────────────────────────────────


def test_is_blocked_ip_loopback():
    """_is_blocked_ip 检测 127.0.0.1 为拦截地址。"""
    from app.algorithm.knowledge.url_fetcher import _is_blocked_ip

    assert _is_blocked_ip("127.0.0.1") is True


def test_is_blocked_ip_private():
    """_is_blocked_ip 检测 10.x.x.x 为拦截地址。"""
    from app.algorithm.knowledge.url_fetcher import _is_blocked_ip

    assert _is_blocked_ip("10.0.0.1") is True


def test_is_blocked_ip_public():
    """_is_blocked_ip 接受公网地址。"""
    from app.algorithm.knowledge.url_fetcher import _is_blocked_ip

    assert _is_blocked_ip("8.8.8.8") is False


def test_is_blocked_ip_invalid():
    """_is_blocked_ip 对无效 IP 返回 True。"""
    from app.algorithm.knowledge.url_fetcher import _is_blocked_ip

    assert _is_blocked_ip("invalid") is True


# ─── Cloudflare 检测 ──────────────────────────────────────────


def test_cloudflare_detection_403():
    """_is_cloudflare_challenge 检测 403+Cloudflare 特征。"""
    from app.algorithm.knowledge.url_fetcher import _is_cloudflare_challenge

    html = "<html>Just a moment... checking your browser</html>"
    assert _is_cloudflare_challenge(html, 403) is True


def test_cloudflare_detection_no_match():
    """_is_cloudflare_challenge 无特征时返回 False。"""
    from app.algorithm.knowledge.url_fetcher import _is_cloudflare_challenge

    assert _is_cloudflare_challenge("<html>normal page</html>", 200) is False


def test_cloudflare_detection_headers():
    """_is_cloudflare_challenge_headers 检测 cf-mitigated header。"""
    from app.algorithm.knowledge.url_fetcher import _is_cloudflare_challenge_headers

    headers = {"cf-mitigated": "challenge"}
    assert _is_cloudflare_challenge_headers(headers) is True


def test_cloudflare_detection_headers_no_match():
    """_is_cloudflare_challenge_headers 无特征时返回 False。"""
    from app.algorithm.knowledge.url_fetcher import _is_cloudflare_challenge_headers

    assert _is_cloudflare_challenge_headers({"content-type": "text/html"}) is False


# ─── fetch_with_httpx ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_with_httpx_success():
    """fetch_with_httpx 成功返回包含 html 和元数据的字典。"""
    from app.algorithm.knowledge.url_fetcher import fetch_with_httpx

    mock_resp = make_httpx_response()

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        MockClient.return_value.__aenter__.return_value = mock_client

        result = await fetch_with_httpx("https://example.com")

    assert result["html"] == "<html>ok</html>"
    assert result["status_code"] == 200
    assert result["fetcher"] == "httpx"
    assert result["from_browser"] is False


@pytest.mark.asyncio
async def test_fetch_with_httpx_raises_on_connection_error():
    """fetch_with_httpx 连接异常时抛出。"""
    from app.algorithm.knowledge.url_fetcher import fetch_with_httpx

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        MockClient.return_value.__aenter__.return_value = mock_client

        with pytest.raises(Exception):
            await fetch_with_httpx("https://example.com")


# ─── fetch_url ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_url_httpx_success():
    """fetch_url 使用 httpx 成功返回内容。"""
    from app.algorithm.knowledge.url_fetcher import fetch_url

    with patch(f"{FETCHER_PATH}.validate_url") as mock_validate:
        with patch(f"{FETCHER_PATH}.fetch_with_httpx") as mock_httpx:
            mock_httpx.return_value = {
                "html": "<html>content</html>",
                "status_code": 200,
                "fetcher": "httpx",
                "from_browser": False,
                "cloudflare_detected": False,
            }

            result = await fetch_url("https://example.com", use_browser_fallback=False)

    assert result["html"] == "<html>content</html>"
    assert result["fetcher"] == "httpx"
    mock_validate.assert_called_once_with("https://example.com")


@pytest.mark.asyncio
async def test_fetch_url_httpx_failure_raises_without_fallback():
    """fetch_url 不使用浏览器降级时，httpx 失败抛出 RuntimeError。"""
    from app.algorithm.knowledge.url_fetcher import fetch_url

    with patch(f"{FETCHER_PATH}.validate_url"):
        with patch(f"{FETCHER_PATH}.fetch_with_httpx", side_effect=Exception("Connection error")):
            with pytest.raises(RuntimeError, match="无法访问"):
                await fetch_url("https://example.com", use_browser_fallback=False)


@pytest.mark.asyncio
async def test_fetch_url_fallback_to_pw_python():
    """fetch_url httpx Cloudflare 时降级到 Python Playwright。"""
    from app.algorithm.knowledge.url_fetcher import fetch_url

    with patch(f"{FETCHER_PATH}.validate_url"):
        with patch(f"{FETCHER_PATH}.fetch_with_httpx") as mock_httpx:
            mock_httpx.return_value = {
                "html": "challenge page",
                "status_code": 403,
                "fetcher": "httpx",
                "from_browser": False,
                "cloudflare_detected": True,
            }
            with patch(f"{FETCHER_PATH}.fetch_with_pw_python") as mock_pw:
                mock_pw.return_value = {
                    "html": "<html>browser content</html>",
                    "status_code": 200,
                    "fetcher": "playwright-python",
                    "from_browser": True,
                    "cloudflare_detected": False,
                }

                result = await fetch_url("https://example.com", use_browser_fallback=True)

    assert result["fetcher"] == "playwright-python"
    assert result["from_browser"] is True


@pytest.mark.asyncio
async def test_fetch_url_fallback_to_node():
    """fetch_url httpx+Playwright 失败时降级到 Node.js。"""
    from app.algorithm.knowledge.url_fetcher import fetch_url

    with patch(f"{FETCHER_PATH}.validate_url"):
        with patch(f"{FETCHER_PATH}.fetch_with_httpx") as mock_httpx:
            mock_httpx.return_value = {
                "html": "challenge",
                "status_code": 403,
                "cloudflare_detected": True,
                "fetcher": "httpx",
                "from_browser": False,
            }
            with patch(f"{FETCHER_PATH}.fetch_with_pw_python", return_value=None):
                with patch(f"{FETCHER_PATH}.fetch_with_node") as mock_node:
                    mock_node.return_value = {
                        "html": "# markdown content",
                        "status_code": 200,
                        "fetcher": "node-scraper",
                        "from_browser": True,
                        "cloudflare_detected": False,
                        "already_markdown": True,
                    }

                    result = await fetch_url("https://example.com", use_browser_fallback=True)

    assert result["fetcher"] == "node-scraper"


@pytest.mark.asyncio
async def test_fetch_url_all_fail_raise():
    """所有抓取策略失败时抛出 RuntimeError。"""
    from app.algorithm.knowledge.url_fetcher import fetch_url

    with patch(f"{FETCHER_PATH}.validate_url"):
        with patch(f"{FETCHER_PATH}.fetch_with_httpx") as mock_httpx:
            mock_httpx.side_effect = Exception("Connection error")
            with patch(f"{FETCHER_PATH}.fetch_with_pw_python", return_value=None):
                with patch(f"{FETCHER_PATH}.fetch_with_node", return_value=None):
                    with pytest.raises(RuntimeError, match="无法访问"):
                        await fetch_url("https://example.com", use_browser_fallback=True)


@pytest.mark.asyncio
async def test_fetch_url_ssrf_blocked_before_http():
    """SSRF 验证在 HTTP 请求之前执行。"""
    from app.algorithm.knowledge.url_fetcher import fetch_url

    with patch(f"{FETCHER_PATH}.validate_url", side_effect=ValueError("内网")):
        with patch(f"{FETCHER_PATH}.fetch_with_httpx") as mock_httpx:
            with pytest.raises(ValueError, match="内网"):
                await fetch_url("http://localhost/test")
            mock_httpx.assert_not_called()


# ─── fetch_with_node ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_with_node_no_script():
    """fetch_with_node 无可用脚本时返回 None。"""
    from app.algorithm.knowledge.url_fetcher import fetch_with_node

    with patch("os.path.isfile", return_value=False):
        result = await fetch_with_node("https://example.com")

    assert result is None
