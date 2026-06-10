"""
表初始化入口 — 委托给 pg_schema 模块。

保留此文件作为兼容层，所有表定义移入 pg_schema.py。
"""
from .pg_schema import init_all_tables

__all__ = ["init_all_tables"]
