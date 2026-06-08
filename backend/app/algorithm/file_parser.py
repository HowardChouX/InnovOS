"""文件解析器 — 支持 PDF/DOCX/TXT/MD/CSV"""
import logging
import os

logger = logging.getLogger(__name__)


def parse_file(file_path: str) -> dict:
    """解析文件并提取文本内容。"""
    ext = os.path.splitext(file_path)[1].lower()
    name = os.path.basename(file_path)

    try:
        if ext == ".pdf":
            return _parse_pdf(file_path)
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
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {"title": os.path.basename(file_path), "content": content, "type": "text"}


def _parse_pdf(file_path: str) -> dict:
    try:
        import PyPDF2
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            texts = []
            for page in reader.pages:
                texts.append(page.extract_text() or "")
        content = "\n".join(texts)
        return {"title": os.path.basename(file_path), "content": content, "type": "pdf"}
    except ImportError:
        logger.warning("PyPDF2 未安装，尝试 pdfminer")
        return _parse_pdf_miner(file_path)


def _parse_pdf_miner(file_path: str) -> dict:
    try:
        from pdfminer.high_level import extract_text
        content = extract_text(file_path)
        return {"title": os.path.basename(file_path), "content": content, "type": "pdf"}
    except ImportError:
        logger.warning("pdfminer 也未安装，回退到文本解析")
        return {"title": os.path.basename(file_path), "content": f"[PDF file: {os.path.basename(file_path)}]", "type": "pdf"}


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
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(",".join(row))
    content = "\n".join(rows)
    return {"title": os.path.basename(file_path), "content": content, "type": "csv"}
