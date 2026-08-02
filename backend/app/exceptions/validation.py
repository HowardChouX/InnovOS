"""全局 422 校验错误中文化处理器。

FastAPI 默认返回英文校验消息（如 "String should match pattern..."），
本处理器按字段名 + 错误类型翻译成中文，保留原有列表结构（兼容前端与测试）。
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# 字段名 → 中文消息（优先匹配）
FIELD_MESSAGES: dict[str, str] = {
    "phone": "手机号格式不正确（11 位数字，1 开头）",
    "password": "密码至少 8 个字符",
    "new_password": "新密码至少 8 个字符",
    "email": "邮箱格式不正确",
    "code": "验证码格式不正确（6 位数字）",
    "current_password": "请输入当前密码",
    "username": "用户名格式不正确",
}

# 错误类型 → 中文兜底（字段名未命中时使用）
TYPE_MESSAGES: dict[str, str] = {
    "missing": "缺少必填字段",
    "string_type": "请输入文本",
    "string_pattern_mismatch": "格式不正确",
    "too_short": "长度不足",
    "too_long": "长度超出限制",
    "int_parsing": "请输入数字",
    "bool_parsing": "请输入 true 或 false",
    "value_error": "值不合法",
    "email_parsing": "邮箱格式不正确",
}


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """把 FastAPI 422 校验错误的英文 msg 翻译成中文。"""
    translated = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = str(loc[-1]) if loc else ""
        err_type = err.get("type", "")

        # 优先按字段名，其次按错误类型，最后保留原文
        msg = FIELD_MESSAGES.get(field) or TYPE_MESSAGES.get(err_type) or err.get("msg", "参数校验失败")

        translated.append({
            "loc": list(loc),
            "msg": msg,
            "type": err_type,
        })

    return JSONResponse(status_code=422, content={"detail": translated})
