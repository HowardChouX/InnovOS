"""定制 JWTStrategy - 织入 token_version 撤销校验。"""
from fastapi_users.authentication.strategy.jwt import JWTStrategy
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.manager import BaseUserManager


class InnovOSJWTStrategy(JWTStrategy):
    """JWT + token_version 撤销校验。

    在标准 JWTStrategy 基础上：
    - write_token: payload 注入 token_version
    - read_token: 校验 token_version 与 DB 值，不匹配则视为已撤销
    """

    async def read_token(self, token, user_manager: BaseUserManager):
        if token is None:
            return None
        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience,
                algorithms=[self.algorithm],
            )
            user_id = data.get("sub")
            token_version = data.get("token_version", 0)
            if user_id is None:
                return None
        except Exception:
            return None
        try:
            parsed_id = user_manager.parse_id(user_id)
            user = await user_manager.get(parsed_id)
        except Exception:
            return None
        # token_version 校验：不匹配则视为已撤销
        if user and getattr(user, "token_version", 0) != token_version:
            return None
        return user

    async def write_token(self, user) -> str:
        data = {
            "sub": str(user.id),
            "aud": self.token_audience,
            "token_version": getattr(user, "token_version", 0),
        }
        return generate_jwt(
            data, self.encode_key, self.lifetime_seconds,
            algorithm=self.algorithm,
        )