"""
OP(AI)UM — File Content Readers/Writers

Read and write content from various file formats:
PDF, DOCX, TXT, MD, PPTX, XLSX, CSV, .py, .tex
"""

from __future__ import annotations

from pathlib import Path

# Extensions that are plain text (no special handling)
PLAIN_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".tex",
    ".csv",
    ".json",
    ".xml",
    ".html",
    ".css",
    ".js",
    ".ts",
}


def read_file_content(path: Path, encoding: str = "utf-8", max_chars: int = 500_000) -> str | None:
    """
    Read file content, handling PDF, DOCX, PPTX, XLSX, CSV, and plain text.
    Returns None if format is not supported or read fails.
    """
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None

    suffix = path.suffix.lower()

    # Plain text
    if suffix in PLAIN_TEXT_EXTENSIONS or suffix in {".log", ".ini", ".cfg", ".yaml", ".yml"}:
        try:
            with open(path, encoding=encoding, errors="replace") as f:
                return f.read(max_chars)
        except Exception:
            return None

    # PDF
    if suffix == ".pdf":
        return _read_pdf(path, max_chars)

    # DOCX
    if suffix == ".docx":
        return _read_docx(path, max_chars)

    # PPTX
    if suffix == ".pptx":
        return _read_pptx(path, max_chars)

    # XLSX
    if suffix == ".xlsx":
        return _read_xlsx(path, max_chars)

    # Fallback: try as text
    try:
        with open(path, encoding=encoding, errors="replace") as f:
            return f.read(max_chars)
    except Exception:
        return None


def _read_pdf(path: Path, max_chars: int) -> str | None:
    """Read PDF text content."""
    try:
        import pdfplumber

        parts = []
        total = 0
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                if total >= max_chars:
                    break
                text = page.extract_text()
                if text:
                    parts.append(text)
                    total += len(text)
        return "\n\n".join(parts)[:max_chars] if parts else None
    except ImportError:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(path)
            parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
            return "\n\n".join(parts)[:max_chars] if parts else None
        except ImportError:
            return None
    except Exception:
        return None


def _read_docx(path: Path, max_chars: int) -> str | None:
    """Read DOCX text content."""
    try:
        from docx import Document

        doc = Document(path)
        parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text for c in row.cells]
                parts.append(" | ".join(cells))
        text = "\n".join(parts)
        return text[:max_chars] if text else None
    except ImportError:
        return None
    except Exception:
        return None


def _read_pptx(path: Path, max_chars: int) -> str | None:
    """Read PPTX text content."""
    try:
        from pptx import Presentation

        prs = Presentation(path)
        parts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    parts.append(shape.text)
        text = "\n\n".join(parts)
        return text[:max_chars] if text else None
    except ImportError:
        return None
    except Exception:
        return None


def _read_xlsx(path: Path, max_chars: int) -> str | None:
    """Read XLSX as tab-separated text."""
    try:
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts = []
        for sheet in wb.worksheets:
            parts.append(f"=== Sheet: {sheet.title} ===")
            for row in sheet.iter_rows(values_only=True):
                row_str = "\t".join(str(c) if c is not None else "" for c in row)
                if row_str.strip():
                    parts.append(row_str)
        wb.close()
        text = "\n".join(parts)
        return text[:max_chars] if text else None
    except ImportError:
        return None
    except Exception:
        return None


def write_file_content(path: Path, content: str, encoding: str = "utf-8") -> bool:
    """
    Write content to file. Handles DOCX, XLSX, and plain text.
    Returns True on success.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    # Plain text
    if suffix in PLAIN_TEXT_EXTENSIONS or suffix in {".log", ".ini", ".cfg", ".yaml", ".yml", ""}:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
            return True
        except Exception:
            return False

    # DOCX
    if suffix == ".docx":
        return _write_docx(path, content)

    # XLSX - write as simple CSV-like format (one sheet)
    if suffix == ".xlsx":
        return _write_xlsx(path, content)

    # Fallback: plain text
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return True
    except Exception:
        return False


def _write_docx(path: Path, content: str) -> bool:
    """Write content to DOCX."""
    try:
        from docx import Document
        from docx.shared import Pt

        doc = Document()
        for line in content.split("\n"):
            para = doc.add_paragraph(line)
            para.paragraph_format.space_after = Pt(6)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(path)
        return True
    except ImportError:
        return False
    except Exception:
        return False


def _write_xlsx(path: Path, content: str) -> bool:
    """Write content to XLSX (each line becomes a row, tab-separated values become cells)."""
    try:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        for row_idx, line in enumerate(content.split("\n"), start=1):
            cells = line.split("\t")
            for col_idx, cell_val in enumerate(cells, start=1):
                ws.cell(row=row_idx, column=col_idx, value=cell_val.strip() if cell_val else "")
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
        return True
    except ImportError:
        return False
    except Exception:
        return False


def can_read_format(suffix: str) -> bool:
    """Check if we can read this file format."""
    suffix = suffix.lower()
    if suffix in PLAIN_TEXT_EXTENSIONS:
        return True
    return suffix in {".pdf", ".docx", ".pptx", ".xlsx", ".csv"}


def can_write_format(suffix: str) -> bool:
    """Check if we can write this file format."""
    suffix = suffix.lower()
    if suffix in PLAIN_TEXT_EXTENSIONS or suffix in {".csv", ""}:
        return True
    return suffix in {".docx", ".xlsx"}
