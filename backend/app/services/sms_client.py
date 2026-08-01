"""阿里云 DYPNS 短信验证码客户端。

基于官方 SDK 示例（alibabacloud_sample/sample.py）改写：
- create_client() 与示例一致：CredentialClient 凭据链 + endpoint
- 发送/核验均使用异步方法（示例 main_async 的调用方式）
- 开发环境无凭证时降级为日志打印
"""
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class SmsClient:
    """短信验证码客户端。"""

    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """与示例 create_client() 一致：凭据链 + 固定 endpoint。"""
        try:
            from alibabacloud_credentials.client import Client as CredentialClient
            from alibabacloud_dypnsapi20170525.client import Client as Dypnsapi20170525Client
            from alibabacloud_tea_openapi import models as open_api_models

            credential = CredentialClient()
            config = open_api_models.Config(credential=credential)
            config.endpoint = settings.SMS_ENDPOINT
            self._client = Dypnsapi20170525Client(config)
            logger.info("阿里云 DYPNS 客户端初始化成功")
        except Exception as e:
            logger.warning("阿里云客户端初始化失败（开发模式降级为日志模拟）: %s", e)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def _dev_code(self, phone: str) -> str:
        """开发模式伪验证码（确定性，便于调试）。"""
        return f"{abs(hash(phone)) % 1_000_000:06d}"

    async def send_code(self, phone: str, template_code: str) -> dict:
        """发送短信验证码（异步，与示例 main_async 调用方式一致）。

        Args:
            phone: 手机号
            template_code: 阿里云模板 CODE（100001 / 100003）

        Returns:
            {"success": bool, "biz_id": str | None, "message": str}
        """
        if not self._client:
            code = self._dev_code(phone)
            logger.info(
                "[DEV SMS] phone=%s template=%s code=%s valid=%ss",
                phone, template_code, code, settings.SMS_CODE_VALID_TIME,
            )
            return {"success": True, "biz_id": "dev-mock", "message": "开发模式模拟发送"}

        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_util import models as util_models

        # 参数与官方示例完全一致（template_param 的 min 为分钟）
        request = dypnsapi_models.SendSmsVerifyCodeRequest(
            scheme_name=settings.SMS_SCHEME_NAME,
            country_code=settings.SMS_COUNTRY_CODE,
            phone_number=phone,
            sign_name=settings.SMS_SIGN_NAME,
            template_code=template_code,
            template_param=json.dumps({
                "code": "##code##",
                "min": str(settings.SMS_CODE_VALID_MIN),
            }),
            code_length=settings.SMS_CODE_LENGTH,
            valid_time=settings.SMS_CODE_VALID_TIME,
            duplicate_policy=settings.SMS_DUPLICATE_POLICY,
            interval=settings.SMS_RESEND_INTERVAL,
            code_type=settings.SMS_CODE_TYPE,
            return_verify_code=True,
            auto_retry=settings.SMS_AUTO_RETRY,
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 与示例 main_async 相同的异步调用
            resp = await self._client.send_sms_verify_code_with_options_async(request, runtime)
            body = resp.body
            if body.code == "OK":
                biz_id = body.model.biz_id if body.model else None
                logger.info("短信发送成功 phone=%s biz_id=%s", phone, biz_id)
                return {"success": True, "biz_id": biz_id, "message": "发送成功"}
            logger.error("短信发送失败 phone=%s code=%s message=%s", phone, body.code, body.message)
            return {"success": False, "biz_id": None, "message": body.message or "发送失败"}
        except Exception as error:
            # 与示例相同的错误处理：error.message + error.data["Recommend"]
            error_msg = getattr(error, "message", None) or str(error)
            recommend = ""
            data = getattr(error, "data", None)
            if data:
                recommend = data.get("Recommend", "")
            logger.error("短信发送异常 phone=%s error=%s recommend=%s", phone, error_msg, recommend)
            return {"success": False, "biz_id": None, "message": error_msg}

    async def verify_code(self, phone: str, code: str) -> bool:
        """核验短信验证码（异步）。

        Args:
            phone: 手机号
            code: 用户输入的验证码

        Returns:
            True 表示核验通过（VerifyResult == "PASS"）
        """
        if not self._client:
            # 开发模式：对比伪验证码
            dev_code = self._dev_code(phone)
            result = code == dev_code
            logger.info(
                "[DEV SMS VERIFY] phone=%s input=%s expected=%s result=%s",
                phone, code, dev_code, result,
            )
            return result

        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_util import models as util_models

        # 参数与官方示例完全一致
        request = dypnsapi_models.CheckSmsVerifyCodeRequest(
            scheme_name=settings.SMS_SCHEME_NAME,
            country_code=settings.SMS_COUNTRY_CODE,
            phone_number=phone,
            verify_code=code,
            case_auth_policy=settings.SMS_CASE_AUTH_POLICY,
        )
        runtime = util_models.RuntimeOptions()
        try:
            resp = await self._client.check_sms_verify_code_with_options_async(request, runtime)
            body = resp.body
            if body.code == "OK" and body.model:
                passed = body.model.verify_result == "PASS"
                logger.info("验证码核验 phone=%s result=%s", phone, "PASS" if passed else "UNKNOWN")
                return passed
            logger.error("验证码核验接口异常 phone=%s code=%s", phone, body.code)
            return False
        except Exception as error:
            error_msg = getattr(error, "message", None) or str(error)
            logger.error("验证码核验异常 phone=%s error=%s", phone, error_msg)
            return False


sms_client = SmsClient()
