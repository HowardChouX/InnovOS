"""文件解析器 — 支持 PDF/DOCX/TXT/MD/CSV"""

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

# 触发 OCR 的文字量阈值（低于此值视为扫描件）
OCR_THRESHOLD = 80


def parse_file(file_path: str, mode: str = "pdfminer") -> dict:
    """解析文件并提取文本内容。

    Args:
        file_path: 文件路径
        mode: 'pdfminer'  — 纯 pdfminer 文字层提取
              'deepseek'  — DeepSeek-OCR API（需全局设置中配 OCR 模型）
    """
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            return _parse_pdf(file_path, mode)
        elif ext in (".docx", ".doc"):
            return _parse_docx(file_path)
        elif ext == ".csv":
            return _parse_csv(file_path)
        else:
            return _parse_text(file_path)
    except Exception as e:
        logger.warning(f"解析失败 {file_path}: {e}")
        return _parse_text(file_path)


def _parse_text(file_path: str) -> dict:
    with open(file_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {"title": os.path.basename(file_path), "content": content, "type": "text"}


def _parse_pdf(file_path: str, mode: str = "pdfminer") -> dict:
    if mode == "deepseek":
        logger.info(f"DeepSeek-OCR 模式: {file_path}")
        content = _ocr_deepseek(file_path)
        if not content:
            raise RuntimeError("DeepSeek-OCR 失败：请检查全局设置中 OCR 模型的 API Key 是否正确")
        return {"title": os.path.basename(file_path), "content": content, "type": "pdf_ocr"}

    # pdfminer 模式
    content = _try_pdfminer(file_path)
    if not content or len(content.strip()) < OCR_THRESHOLD:
        content = _try_pypdf2(file_path)
    if not content or len(content.strip()) < OCR_THRESHOLD:
        content = f"[PDF 文字层提取失败: {os.path.basename(file_path)}]"
    return {"title": os.path.basename(file_path), "content": content, "type": "pdf"}


def _try_pypdf2(file_path: str) -> str | None:
    try:
        import PyPDF2

        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            texts = []
            for page in reader.pages:
                texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception as e:
        logger.debug(f"PyPDF2 失败: {e}")
        return None


def _try_pdfminer(file_path: str) -> str | None:
    try:
        from pdfminer.high_level import extract_text

        return extract_text(file_path)
    except Exception as e:
        logger.debug(f"pdfminer 失败: {e}")
        return None


def _ocr_pdf(file_path: str) -> str:
    """OCR 扫描件 PDF — DeepSeek-OCR API"""
    return _ocr_deepseek(file_path) or "[OCR 失败: DeepSeek-OCR 不可用]"


def _ocr_deepseek(file_path: str) -> str | None:
    """使用 DeepSeek-OCR API（需配置供应商 API Key）

    从 model_providers 表中读取 DeepSeek 或配置了 OCR 能力的供应商配置。
    未配置时返回 None，自动降级到 Tesseract。
    """
    try:
        from app.database import get_db

        db = get_db()
        if not db:
            return None

        # 从 system_settings 读取配置的 OCR 模型
        row = db.execute("SELECT value FROM system_settings WHERE key='ocr_model'").fetchone()
        if not row or not row["value"]:
            logger.info("未配置 OCR 模型，降级到 Tesseract")
            db.close()
            return None

        ocr_model_id = row["value"]  # 格式: "providerId:modelId"
        provider_id, model_name = ocr_model_id.split(":", 1) if ":" in ocr_model_id else ("deepseek", ocr_model_id)

        # 从环境变量读取 API Key
        from app.algorithm.model_service import _get_provider_api_key

        api_key = _get_provider_api_key(provider_id)
        if not api_key:
            logger.info(f"供应商 {provider_id} 未配置 API Key，降级到 Tesseract")
            return None

        # 查找对应供应商的 host
        provider = db.execute(
            """SELECT api_host FROM model_providers
               WHERE provider_id = ? AND is_enabled = 1 LIMIT 1""",
            (provider_id,),
        ).fetchone()
        db.close()

        if not provider:
            logger.info(f"供应商 {provider_id} 未启用，降级到 Tesseract")
            return None

        api_host = provider["api_host"] or f"https://api.{provider_id}.com"
        from app.algorithm.model_runtime import ModelRuntime

        base_url = ModelRuntime.ensure_v1_url(api_host)

        # 调用 DeepSeek-OCR
        import base64

        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        from pdf2image import convert_from_path

        images = convert_from_path(file_path, dpi=200)
        texts = []

        for i, img in enumerate(images):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img.save(tmp.name, format="PNG")
                with open(tmp.name, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                os.unlink(tmp.name)

            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            {"type": "text", "text": "只输出图片中的文字，不要任何解释、不要任何格式说明。"},
                        ],
                    },
                ],
                max_tokens=4096,
                temperature=0.0,
            )
            page_text = resp.choices[0].message.content or ""
            # 过滤模型幻觉出的 HTML 标签
            import re as _re

            page_text = _re.sub(r"<[^>]+>", "", page_text)
            texts.append(f"--- 第 {i + 1} 页 ---\n{page_text.strip()}")

        result = "\n\n".join(texts)
        logger.info(f"DeepSeek-OCR 完成: {len(images)} 页, {len(result)} 字")
        return result

    except Exception as e:
        logger.warning(f"DeepSeek-OCR 调用失败，降级到 Tesseract: {e}")
        return None


def _parse_docx(file_path: str) -> dict:
    try:
        from docx import Document

        doc = Document(file_path)
        content = "\n".join(p.text for p in doc.paragraphs)
        return {"title": os.path.basename(file_path), "content": content, "type": "docx"}
    except ImportError:
        logger.warning("python-docx 未安装")
        return _parse_text(file_path)


def _parse_csv(file_path: str) -> dict:
    import csv

    rows = []
    with open(file_path, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(",".join(row))
    content = "\n".join(rows)
    return {"title": os.path.basename(file_path), "content": content, "type": "csv"}
