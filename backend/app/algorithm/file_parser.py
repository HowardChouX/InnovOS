"""文件解析器 — 支持 PDF/DOCX/TXT/MD/CSV"""

import logging
import os

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
    # 优先 Docling（更好的布局保留和中文支持），失败自动降级
    if mode in ("docling", "auto"):
        logger.info(f"Docling 模式: {file_path}")
        content = _try_docling(file_path)
        if content:
            return {"title": os.path.basename(file_path), "content": content, "type": "pdf_docling"}
        if mode == "docling":
            raise RuntimeError("Docling 解析失败，PDF 可能为扫描件或格式不支持")
        logger.warning(f"Docling 失败，降级到 pdfminer: {file_path}")

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


def _try_docling(file_path: str) -> str | None:
    """使用 Docling 提取 PDF 文本（Markdown 输出，保留布局和阅读顺序）"""
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(file_path)
        return result.document.export_to_markdown()
    except ImportError:
        logger.info("Docling 未安装，使用 pdfminer 降级")
        return None
    except Exception as e:
        logger.warning(f"Docling 失败: {e}")
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
