"""工具函数"""
from datetime import datetime


def utc_iso(dt_str: str | datetime | None) -> str | None:
    """将无时区的 datetime 字符串转换为带 UTC 时区的 ISO 格式。

    追加 '+00:00' 后，前端 new Date() 正确解析为 UTC 时间。
    TIMESTAMPTZ 列经 psycopg2 返回 datetime 对象，直接 isoformat()
    （已带时区偏移）。
    """
    if not dt_str:
        return None
    if isinstance(dt_str, datetime):
        return dt_str.isoformat()
    if "+" in dt_str or "Z" in dt_str:
        return dt_str
    return dt_str + "+00:00"
