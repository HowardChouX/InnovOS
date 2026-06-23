"""工具函数"""


def utc_iso(dt_str: str | None) -> str | None:
    """将无时区的 datetime 字符串转换为带 UTC 时区的 ISO 格式。

    追加 '+00:00' 后，前端 new Date() 正确解析为 UTC 时间。
    """
    if not dt_str:
        return None
    if "+" in dt_str or "Z" in dt_str:
        return dt_str
    return dt_str + "+00:00"
