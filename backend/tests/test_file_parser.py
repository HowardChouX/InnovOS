"""
测试 file_parser.py — 文件解析器

Mock 文件读取和第三方库，测试各格式解析逻辑、编码处理、异常分支。
"""

import os
import pytest
from unittest.mock import MagicMock, patch, mock_open


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_txt_file(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("Hello, 世界！", encoding="utf-8")
    return str(path)


@pytest.fixture
def temp_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    return str(path)


@pytest.fixture
def temp_csv_file(tmp_path):
    path = tmp_path / "test.csv"
    path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    return str(path)


# ═══════════════════════════════════════════════════════════════════
# parse_file - 入口
# ═══════════════════════════════════════════════════════════════════

class TestParseFile:
    def test_pdf_routes_to_pdf_parser(self, monkeypatch, tmp_path):
        path = tmp_path / "test.pdf"
        path.write_text("fake pdf")
        mock_parse = MagicMock(return_value={"content": "pdf text", "type": "pdf"})
        monkeypatch.setattr("app.algorithm.file_parser._parse_pdf", mock_parse)

        from app.algorithm.file_parser import parse_file

        result = parse_file(str(path))
        assert result["content"] == "pdf text"
        mock_parse.assert_called_once_with(str(path), "pdfminer")

    def test_docx_routes_to_docx_parser(self, monkeypatch, tmp_path):
        path = tmp_path / "test.docx"
        path.write_text("fake docx")
        mock_parse = MagicMock(return_value={"content": "docx text", "type": "docx"})
        monkeypatch.setattr("app.algorithm.file_parser._parse_docx", mock_parse)

        from app.algorithm.file_parser import parse_file

        result = parse_file(str(path))
        assert result["content"] == "docx text"

    def test_csv_routes_to_csv_parser(self, monkeypatch, tmp_path):
        path = tmp_path / "test.csv"
        path.write_text("a,b,c\n1,2,3\n")
        mock_parse = MagicMock(return_value={"content": "a,b,c\n1,2,3", "type": "csv"})
        monkeypatch.setattr("app.algorithm.file_parser._parse_csv", mock_parse)

        from app.algorithm.file_parser import parse_file

        result = parse_file(str(path))
        assert result["type"] == "csv"

    def test_unknown_ext_routes_to_text_parser(self, tmp_path):
        path = tmp_path / "test.unknown"
        path.write_text("plain text")

        from app.algorithm.file_parser import parse_file

        result = parse_file(str(path))
        assert result["type"] == "text"
        assert result["content"] == "plain text"

    def test_parse_exception_falls_back_to_text(self, monkeypatch, tmp_path):
        path = tmp_path / "test.pdf"
        path.write_text("not a pdf but will be read as text")
        mock_fail = MagicMock(side_effect=RuntimeError("parse failed"))
        monkeypatch.setattr("app.algorithm.file_parser._parse_pdf", mock_fail)

        from app.algorithm.file_parser import parse_file

        result = parse_file(str(path))
        assert result["type"] == "text"


# ═══════════════════════════════════════════════════════════════════
# _parse_text — 测试文本文件读取
# ═══════════════════════════════════════════════════════════════════

class TestParseText:
    def test_reads_utf8(self, temp_txt_file):
        from app.algorithm.file_parser import _parse_text
        result = _parse_text(temp_txt_file)
        assert result["content"] == "Hello, 世界！"
        assert result["title"] == "test.txt"
        assert result["type"] == "text"

    def test_empty_file(self, temp_empty_file):
        from app.algorithm.file_parser import _parse_text
        result = _parse_text(temp_empty_file)
        assert result["content"] == ""


# ═══════════════════════════════════════════════════════════════════
# _parse_pdf — 测试 PDF 解析入口
# ═══════════════════════════════════════════════════════════════════

class TestParsePdf:
    def test_pdfminer_success(self, monkeypatch):
        """pdfminer 成功返回内容，不触发降级"""
        mock_extract = MagicMock(return_value="PDF extracted text" * 20)  # > OCR_THRESHOLD
        monkeypatch.setattr("app.algorithm.file_parser._try_pdfminer", mock_extract)

        from app.algorithm.file_parser import _parse_pdf
        result = _parse_pdf("/fake/test.pdf")

        assert result["content"] == "PDF extracted text" * 20
        assert result["type"] == "pdf"

    def test_pdfminer_fails_falls_to_pypdf2(self, monkeypatch):
        """pdfminer 返回内容太少时，应尝试 PyPDF2"""
        monkeypatch.setattr("app.algorithm.file_parser._try_pdfminer", lambda p: "short")
        mock_pypdf2 = MagicMock(return_value="PyPDF2 content" * 20)
        monkeypatch.setattr("app.algorithm.file_parser._try_pypdf2", mock_pypdf2)

        from app.algorithm.file_parser import _parse_pdf
        result = _parse_pdf("/fake/test.pdf")

        assert result["content"] == "PyPDF2 content" * 20

    def test_both_fail_error_message(self, monkeypatch):
        """两者都失败时返回错误消息"""
        monkeypatch.setattr("app.algorithm.file_parser._try_pdfminer", lambda p: None)
        monkeypatch.setattr("app.algorithm.file_parser._try_pypdf2", lambda p: None)

        from app.algorithm.file_parser import _parse_pdf
        result = _parse_pdf("/fake/test.pdf")

        assert "文字层提取失败" in result["content"]


# ═══════════════════════════════════════════════════════════════════
# _try_pypdf2 / _try_pdfminer — 底层 PDF 库
# ═══════════════════════════════════════════════════════════════════

class TestTryPypdf2:
    @patch("PyPDF2.PdfReader")
    def test_success(self, mock_reader_cls, monkeypatch):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader

        # Mock open so we don't need a real file
        monkeypatch.setattr("builtins.open", mock_open(read_data=b"fake pdf data"))

        from app.algorithm.file_parser import _try_pypdf2
        result = _try_pypdf2("/fake/test.pdf")
        assert result == "Page 1 content"

    @patch("PyPDF2.PdfReader")
    def test_failure_returns_none(self, mock_reader_cls):
        mock_reader_cls.side_effect = RuntimeError("PDF error")

        from app.algorithm.file_parser import _try_pypdf2
        result = _try_pypdf2("/fake/test.pdf")
        assert result is None


class TestTryPdfminer:
    @patch("pdfminer.high_level.extract_text")
    def test_success(self, mock_extract):
        mock_extract.return_value = "pdfminer extracted text"

        from app.algorithm.file_parser import _try_pdfminer
        result = _try_pdfminer("/fake/test.pdf")
        assert result == "pdfminer extracted text"

    @patch("pdfminer.high_level.extract_text")
    def test_failure_returns_none(self, mock_extract):
        mock_extract.side_effect = RuntimeError("pdfminer failed")

        from app.algorithm.file_parser import _try_pdfminer
        result = _try_pdfminer("/fake/test.pdf")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# _parse_docx — 测试 DOCX 解析
# ═══════════════════════════════════════════════════════════════════

class TestParseDocx:
    @patch("docx.Document")
    def test_success(self, mock_document_cls):
        mock_doc = MagicMock()
        mock_p1 = MagicMock()
        mock_p1.text = "Paragraph 1"
        mock_p2 = MagicMock()
        mock_p2.text = "Paragraph 2"
        mock_doc.paragraphs = [mock_p1, mock_p2]
        mock_document_cls.return_value = mock_doc

        from app.algorithm.file_parser import _parse_docx
        result = _parse_docx("/fake/test.docx")

        assert result["content"] == "Paragraph 1\nParagraph 2"
        assert result["type"] == "docx"

    @patch("docx.Document")
    def test_import_error_falls_back_to_text(self, mock_docx, monkeypatch):
        """python-docx 抛出异常时回退到文本解析"""
        mock_docx.side_effect = ImportError("No module named 'docx'")
        monkeypatch.setattr(
            "app.algorithm.file_parser._parse_text",
            lambda p: {"content": "fallback text", "type": "text"},
        )

        from app.algorithm.file_parser import _parse_docx
        result = _parse_docx("/fake/test.docx")
        assert result["type"] == "text"
        assert result["content"] == "fallback text"


# ═══════════════════════════════════════════════════════════════════
# _parse_csv — 测试 CSV 解析
# ═══════════════════════════════════════════════════════════════════

class TestParseCsv:
    def test_parses_csv(self, tmp_path):
        path = tmp_path / "test.csv"
        path.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")

        from app.algorithm.file_parser import _parse_csv
        result = _parse_csv(str(path))

        assert "a,b,c" in result["content"]
        assert "1,2,3" in result["content"]
        assert result["type"] == "csv"
