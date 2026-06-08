"""工具函数"""


def utc_iso(dt_str: str | None) -> str | None:
    """将 SQLite datetime 字符串转换为带 UTC 时区的 ISO 格式。

    SQLite datetime('now') 返回 '2026-06-07 12:31:36'（无时区），
    前端 new Date() 会将其误解为本地时间。
    追加 '+00:00' 后，前端正确解析为 UTC。
    """
    if not dt_str:
        return None
    if "+" in dt_str or "Z" in dt_str:
        return dt_str
    return dt_str + "+00:00"
