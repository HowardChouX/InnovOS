"""
URL 抓取测试脚本 — 使用 InnovOS + MarkDownload 融合管线抓取网页并保存为 Markdown。

用法:
  .venv/bin/python -m tests.test_url_scrape <url> [output.md]

示例:
  .venv/bin/python -m tests.test_url_scrape https://xinglugu.huijiwiki.com/wiki/%E5%A4%8F%E5%AD%A3 output.md
  .venv/bin/python -m tests.test_url_scrape https://example.com  # 打印到 stdout
"""
import asyncio
import sys
import os

# 确保能找到 backend 模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else ""
    output_file = sys.argv[2] if len(sys.argv) > 2 else ""

    if not url:
        print("用法: python -m tests.test_url_scrape <url> [output.md]", file=sys.stderr)
        sys.exit(1)

    from app.algorithm.knowledge.url_fetcher import fetch_url
    from app.algorithm.knowledge.html_to_markdown import url_to_markdown

    print(f"抓取: {url}", file=sys.stderr)

    # 抓取（自动降级：httpx → Python Playwright → Node.js MarkDownload）
    result = await fetch_url(url, timeout=60.0, use_browser_fallback=True)
    raw = result["html"]
    final_url = result["final_url"]
    fetcher = result.get("fetcher", "?")
    title = result.get("title", "")

    print(f"抓取器: {fetcher}", file=sys.stderr)
    print(f"最终URL: {final_url}", file=sys.stderr)

    # 转换
    if result.get("already_markdown"):
        content = raw
    else:
        print("转换 HTML → Markdown...", file=sys.stderr)
        content = url_to_markdown(raw, base_url=final_url)

    lines = content.count("\n")
    print(f"行数: {lines}, 字符: {len(content)}", file=sys.stderr)

    # 输出
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"已保存: {os.path.abspath(output_file)}", file=sys.stderr)
    else:
        print(content)


if __name__ == "__main__":
    asyncio.run(main())
