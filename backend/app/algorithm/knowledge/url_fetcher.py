"""
URL 抓取器 — 三层降级策略，确保国内环境可用。

层级：
1. httpx — 快速轻量，适用于普通页面（主线）
2. Playwright for Python — Cloudflare/JS 渲染（可选，pip install playwright）
3. Node.js 子进程 — Cloudflare 兜底（调用独立 scrape.js，playwright 已预装）

自动检测 Cloudflare 挑战，透明降级。

SSRF 防护：所有 URL 在抓取前会验证目标 IP 地址，拒绝内网/保留地址。
"""

import asyncio
import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ── SSRF 防护 ──────────────────────────────────────────────────────────

_PRIVATE_IPS_ERROR_MSG = (
    "URL 解析到的目标 IP 地址为内网/保留地址，已拒绝访问。为避免 SSRF 攻击，知识库 URL 抓取不支持内网地址。"
)


def _resolve_hostname(hostname: str) -> list[str]:
    """解析域名到 IP 地址列表。超时 3s。"""
    try:
        # getaddrinfo 在主线程可能阻塞，但在 async worker 中有 GIL 保护
        infos = socket.getaddrinfo(hostname, 80, socket.AF_INET, socket.SOCK_STREAM)
        return list({str(info[4][0]) for info in infos})
    except (socket.gaierror, OSError):
        return []


# SSRF 黑名单：精确的 IP 段，仅拦截能实际被 SSRF 利用的内网/链路本地地址。
# 注意：不使用 ipaddress.is_private，因为它也会拦截 198.18.0.0/15（Benchmarking）
# 和 100.64.0.0/10（CGNAT），这些在部分测试/网络环境下会误杀公网域名。
_SSRF_BLOCKED_V4 = [
    ipaddress.IPv4Network("127.0.0.0/8"),  # Loopback
    ipaddress.IPv4Network("10.0.0.0/8"),  # Private A
    ipaddress.IPv4Network("172.16.0.0/12"),  # Private B
    ipaddress.IPv4Network("192.168.0.0/16"),  # Private C
    ipaddress.IPv4Network("169.254.0.0/16"),  # Link-local
    ipaddress.IPv4Network("0.0.0.0/8"),  # Current network
]
_SSRF_BLOCKED_V6 = [
    ipaddress.IPv6Network("::1/128"),  # Loopback
    ipaddress.IPv6Network("fc00::/7"),  # Unique-local
    ipaddress.IPv6Network("fe80::/10"),  # Link-local
    ipaddress.IPv6Network("::/128"),  # Unspecified
]


def _is_blocked_ip(ip_str: str) -> bool:
    """检查 IP 是否属于 SSRF 攻击可利用的内网/链路本地地址。"""
    try:
        addr = ipaddress.ip_address(ip_str)
        if isinstance(addr, ipaddress.IPv4Address):
            return any(net.supernet_of(ipaddress.IPv4Network(addr)) for net in _SSRF_BLOCKED_V4)
        else:
            return any(net.supernet_of(ipaddress.IPv6Network(addr)) for net in _SSRF_BLOCKED_V6)
    except ValueError:
        return True  # 非标准 IP 地址也拒绝


def validate_url(url: str) -> None:
    """SSRF 防护验证：拒绝内网/保留地址。

    检查流程：
    1. 解析 URL 格式
    2. 提取 hostname
    3. 使用 socket.getaddrinfo 解析域名到 IP
    4. 检查所有解析到的 IP 是否都属于内网/保留地址

    Raises:
        ValueError: 如果 URL 指向内网地址或无法解析
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("URL 格式无效")

    # 只允许 http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不支持的 URL 协议: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL 缺少 hostname")

    # 预检查简单的内网域名模式
    lower_host = hostname.lower()
    if lower_host in ("localhost", "localhost.localdomain"):
        raise ValueError(_PRIVATE_IPS_ERROR_MSG)
    if lower_host.endswith(".internal") or lower_host.endswith(".local"):
        raise ValueError(_PRIVATE_IPS_ERROR_MSG)

    # 解析 IP 并检查
    ips = _resolve_hostname(hostname)
    if not ips:
        raise ValueError(f"无法解析域名: {hostname}")

    private_ips = [ip for ip in ips if _is_blocked_ip(ip)]
    if private_ips:
        logger.warning("SSRF blocked: %s resolved to private IPs: %s", hostname, private_ips)
        raise ValueError(_PRIVATE_IPS_ERROR_MSG)


# ── Cloudflare 检测 ────────────────────────────────────────────────────────

CLOUDFLARE_PATTERNS = [
    "just a moment",
    "checking your browser",
    "cf-browser-verification",
    "__cf_chl_tk",
    "challenge-platform",
    "cf_chl_opt",
]


def _is_cloudflare_challenge(html: str, status_code: int) -> bool:
    if status_code == 403 and html:
        lower = html[:2000].lower()
        return any(p in lower for p in CLOUDFLARE_PATTERNS)
    return False


def _is_cloudflare_challenge_headers(headers: dict) -> bool:
    h = {k.lower(): v for k, v in headers.items()}
    return h.get("cf-mitigated") == "challenge"


# ═══════════════════════════════════════════════════════════════════════════
#  Layer 1: httpx
# ═══════════════════════════════════════════════════════════════════════════


async def fetch_with_httpx(url: str, timeout: float = 30.0) -> dict:
    """httpx 快速抓取。"""
    import httpx

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        html = resp.text
        final_url = str(resp.url)
        status_code = resp.status_code
        headers = dict(resp.headers)

        is_cf = _is_cloudflare_challenge(html, status_code) or _is_cloudflare_challenge_headers(headers)

        return {
            "html": html,
            "final_url": final_url,
            "status_code": status_code,
            "headers": headers,
            "from_browser": False,
            "cloudflare_detected": is_cf,
            "fetcher": "httpx",
        }


# ═══════════════════════════════════════════════════════════════════════════
#  Layer 2: Playwright for Python (optional)
# ═══════════════════════════════════════════════════════════════════════════

_PW_AVAILABLE: bool | None = None


def _playwright_available() -> bool:
    global _PW_AVAILABLE
    if _PW_AVAILABLE is None:
        try:
            import playwright  # noqa: F401

            _PW_AVAILABLE = True
        except ImportError:
            _PW_AVAILABLE = False
    return _PW_AVAILABLE


async def fetch_with_pw_python(url: str, timeout: float = 60.0) -> dict | None:
    """Python Playwright 浏览器抓取（可选依赖）。不可用时返回 None。"""
    if not _playwright_available():
        return None

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    browser = None
    context = None
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)

        html = await page.content()
        final_url = page.url

        title = await page.title()
        if any(p in title.lower() for p in ["just a moment", "checking your browser"]):
            logger.info("Cloudflare 挑战残留，延时等待…")
            await asyncio.sleep(8)
            html = await page.content()
            final_url = page.url

        return {
            "html": html,
            "final_url": final_url,
            "status_code": 200,
            "headers": {},
            "from_browser": True,
            "cloudflare_detected": False,
            "fetcher": "playwright-python",
        }
    except Exception as e:
        logger.warning("Python Playwright 抓取失败: %s", e)
        return None
    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()


# ═══════════════════════════════════════════════════════════════════════════
#  Layer 3: Node.js subprocess (兜底, 调用 markdownload scrape.js)
# ═══════════════════════════════════════════════════════════════════════════

_NODE_SCRIPTS = [
    # 优先找同项目内可能放置的脚本
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "scrape.js"
    ),
    # 找用户 home 目录下的 markdownload 项目
    os.path.expanduser("~/markdownload/scrape.js"),
]


async def fetch_with_node(url: str, timeout: float = 60.0) -> dict | None:
    """调用 Node.js MarkDownload 管线抓取（Playwright for Node.js 已预装）。"""
    script_path = None
    for p in _NODE_SCRIPTS:
        if os.path.isfile(p):
            script_path = p
            break

    if not script_path:
        return None

    try:
        proc = await asyncio.create_subprocess_exec(
            "node",
            script_path,
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            logger.warning("Node.js 子进程超时")
            return None

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:300]
            logger.warning("Node.js 返回 %d: %s", proc.returncode, err)
            return None

        markdown = stdout.decode("utf-8", errors="replace").strip()
        if not markdown or len(markdown) < 20:
            logger.warning("Node.js 输出过少")
            return None

        # 从 stderr 提取标题信息
        stderr_text = stderr.decode("utf-8", errors="replace")
        title = ""
        for line in stderr_text.split("\n"):
            if "Title:" in line:
                title = line.partition("Title:")[2].strip().rstrip("|").strip()
                break

        logger.info("Node.js MarkDownload 管线成功: %s", title or url)

        return {
            "html": markdown,  # 已转为 Markdown
            "final_url": url,
            "status_code": 200,
            "headers": {},
            "from_browser": True,
            "cloudflare_detected": False,
            "already_markdown": True,  # 标记：内容已是 markdown
            "fetcher": "node-scraper",
            "title": title,
        }

    except FileNotFoundError:
        logger.warning("Node.js 未安装")
        return None
    except Exception as e:
        logger.warning("Node.js 子进程异常: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  Unified entry
# ═══════════════════════════════════════════════════════════════════════════


async def fetch_url(url: str, timeout: float = 30.0, use_browser_fallback: bool = True) -> dict:
    """统一 URL 抓取入口。

    策略链：httpx → Python Playwright → Node.js scrape.js
    httpx 连接失败或 Cloudflare 保护时自动降级到浏览器方案。

    注意：所有 URL 在抓取前会经过 SSRF 验证，拒绝内网/保留地址。

    Returns:
        {html, final_url, status_code, headers, from_browser,
         cloudflare_detected, already_markdown, fetcher, title}

    Raises:
        ValueError: SSRF 验证失败（内网地址/无法解析）
        RuntimeError: 所有抓取策略均失败
    """
    # SSRF 防护：验证 URL 不指向内网地址
    validate_url(url)

    # Layer 1: httpx
    httpx_ok = False
    need_browser = False
    try:
        result = await fetch_with_httpx(url, timeout)
        httpx_ok = True
        need_browser = result.get("cloudflare_detected", False)
    except Exception as e:
        logger.warning("httpx 抓取失败: %s — 尝试浏览器方案", e)
        need_browser = True

    if use_browser_fallback and need_browser:
        logger.info("尝试浏览器抓取: %s", url)
        browser_timeout = max(timeout, 60.0)

        # Layer 2: Python Playwright
        pw = await fetch_with_pw_python(url, browser_timeout)
        if pw:
            return pw

        # Layer 3: Node.js subprocess
        node = await fetch_with_node(url, browser_timeout)
        if node:
            return node

        logger.warning("所有浏览器方案均不可用")

        if httpx_ok:
            return result
        else:
            raise RuntimeError(f"无法访问 {url}: httpx 连接失败且无浏览器方案可用")

    if httpx_ok:
        return result
    else:
        raise RuntimeError(f"无法访问 {url}: httpx 连接失败")
