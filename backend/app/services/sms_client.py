"""阿里云 DYPNS 客户端封装 — 直接使用 alibabacloud_dypnsapi20170525 SDK。

参考 zip 示例代码：
- backend/app/services/sms_send_sample/alibabacloud_sample/sample.py
- backend/app/services/sms_verify_sample/alibabacloud_sample/sample.py
"""
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class SmsClient:
    """短信验证码客户端。开发环境无凭证时降级为日志打印。"""

    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """使用凭据初始化阿里云 Client（与 zip 示例的 create_client() 一致）。"""
        try:
            from alibabacloud_dypnsapi20170525.client import Client as Dypnsapi20170525Client
            from alibabacloud_credentials.client import Client as CredentialClient
            from alibabacloud_tea_openapi import models as open_api_models

            credential = CredentialClient()
            config = open_api_models.Config(credential=credential)
            config.endpoint = "dypnsapi.aliyuncs.com"
            self._client = Dypnsapi20170525Client(config)
            logger.info("阿里云 DYPNS 客户端初始化成功")
        except Exception as e:
            logger.warning("阿里云客户端初始化失败（开发模式降级）: %s", e)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def send_code(self, phone: str, template_code: str) -> dict:
        """发送短信验证码（参考 sms_send_sample/sample.py）。

        Args:
            phone: 手机号
            template_code: 阿里云模板 CODE（100001 / 100003）

        Returns:
            {"success": bool, "biz_id": str | None, "message": str}
        """
        if not self._client:
            fake_code = f"{hash(phone) % 1_000_000:06d}"
            logger.info(
                "[DEV SMS] phone=%s template=%s code=%s valid=%ss",
                phone, template_code, fake_code, settings.SMS_CODE_VALID_TIME,
            )
            return {"success": True, "biz_id": "dev-mock", "message": "开发模式模拟发送"}

        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_util import models as util_models

        # ── 参数与 sms_send_sample/sample.py 完全一致 ──
        request = dypnsapi_models.SendSmsVerifyCodeRequest(
            scheme_name=settings.SMS_SCHEME_NAME,
            country_code="86",
            phone_number=phone,
            sign_name=settings.SMS_SIGN_NAME,
            template_code=template_code,
            template_param=json.dumps({
                "code": "##code##",
                "min": str(settings.SMS_CODE_VALID_TIME // 60),
            }),
            code_length=settings.SMS_CODE_LENGTH,
            valid_time=settings.SMS_CODE_VALID_TIME,
            duplicate_policy=1,
            interval=settings.SMS_RESEND_INTERVAL,
            code_type=1,
            return_verify_code=True,  # 与 sample.py 一致
            auto_retry=1,
        )
        runtime = util_models.RuntimeOptions()
        try:
            resp = self._client.send_sms_verify_code_with_options(request, runtime)
            body = resp.body
            if body.code == "OK":
                biz_id = body.model.biz_id if body.model else None
                logger.info("短信发送成功 phone=%s biz_id=%s", phone, biz_id)
                return {"success": True, "biz_id": biz_id, "message": "发送成功"}
            logger.error("短信发送失败 phone=%s code=%s message=%s", phone, body.code, body.message)
            return {"success": False, "biz_id": None, "message": body.message or "发送失败"}
        except Exception as error:
            # 与 sample.py 一致的错误处理模式：error.message + error.data.get("Recommend")
            error_msg = error.message if hasattr(error, "message") else str(error)
            logger.error("短信发送异常 phone=%s error=%s", phone, error_msg)
            if hasattr(error, "data") and error.data:
                logger.error("诊断地址: %s", error.data.get("Recommend"))
            return {"success": False, "biz_id": None, "message": error_msg}

    def verify_code(self, phone: str, code: str) -> bool:
        """核验短信验证码（参考 sms_verify_sample/sample.py）。

        Args:
            phone: 手机号
            code: 用户输入的验证码

        Returns:
            True 表示核验通过（PASS），False 表示核验失败
        """
        if not self._client:
            fake_code = f"{hash(phone) % 1_000_000:06d}"
            result = code == fake_code
            logger.info(
                "[DEV SMS VERIFY] phone=%s input=%s expected=%s result=%s",
                phone, code, fake_code, result,
            )
            return result

        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_util import models as util_models

        # ── 参数与 sms_verify_sample/sample.py 完全一致 ──
        request = dypnsapi_models.CheckSmsVerifyCodeRequest(
            scheme_name=settings.SMS_SCHEME_NAME,
            country_code="86",
            phone_number=phone,
            verify_code=code,
            case_auth_policy=1,
        )
        runtime = util_models.RuntimeOptions()
        try:
            resp = self._client.check_sms_verify_code_with_options(request, runtime)
            body = resp.body
            if body.code == "OK" and body.model:
                passed = body.model.verify_result == "PASS"
                logger.info("验证码核验 phone=%s result=%s", phone, "PASS" if passed else "FAIL")
                return passed
            logger.error("验证码核验异常 phone=%s code=%s", phone, body.code)
            return False
        except Exception as error:
            error_msg = error.message if hasattr(error, "message") else str(error)
            logger.error("验证码核验异常 phone=%s error=%s", phone, error_msg)
            if hasattr(error, "data") and error.data:
                logger.error("诊断地址: %s", error.data.get("Recommend"))
            return False


sms_client = SmsClient()
