"""
OP(AI)UM — Markdown to HTML Renderer

Converts markdown to HTML for QTextBrowser / Qt rich text.
Fenced code blocks are replaced with Unicode placeholders (never __ or **)
before markdown2 runs, then re-inserted as HTML. Inline `code` is left to
markdown2 so it is not HTML-escaped.
"""

from __future__ import annotations

import html
import re

from loguru import logger

_PLACEHOLDER_PREFIX = "\u2060CB"  # word joiner — invisible, breaks no markdown
_PLACEHOLDER_SUFFIX = "\u2060"


def _highlight_code(code: str, language: str) -> str:
    """Syntax-highlight a code block using Pygments."""
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
        from pygments.formatters import HtmlFormatter

        code = code.rstrip("\n")
        lexer = TextLexer()
        lang = (language or "").strip().lower()
        if lang:
            try:
                lexer = get_lexer_by_name(lang, stripall=True)
            except Exception:
                try:
                    lexer = guess_lexer(code)
                except Exception:
                    lexer = TextLexer()
        else:
            try:
                lexer = guess_lexer(code)
            except Exception:
                lexer = TextLexer()

        formatter = HtmlFormatter(
            nowrap=True,
            noclasses=True,
            style="monokai",
            prestyles="margin:0; white-space:pre-wrap;",
        )
        return highlight(code, lexer, formatter)
    except ImportError:
        return html.escape(code)


def _extract_fenced_code(md_text: str) -> tuple[str, dict[str, str]]:
    """Replace ```fenced``` blocks with placeholders; return markdown + HTML map."""
    placeholders: dict[str, str] = {}
    counter = 0
    result: list[str] = []
    pos = 0
    n = len(md_text)

    while pos < n:
        start = md_text.find("```", pos)
        if start < 0:
            result.append(md_text[pos:])
            break
        result.append(md_text[pos:start])
        line_end = md_text.find("\n", start + 3)
        if line_end < 0:
            # No newline after opening fence — treat rest as code or append literally
            result.append(md_text[start:])
            break
        lang_line = md_text[start + 3 : line_end].strip()
        close = md_text.find("```", line_end + 1)
        if close < 0:
            result.append(md_text[start:])
            break
        body = md_text[line_end + 1 : close]
        highlighted = _highlight_code(body, lang_line)
        key = f"{_PLACEHOLDER_PREFIX}{counter}{_PLACEHOLDER_SUFFIX}"
        counter += 1
        placeholders[key] = (
            '<table width="100%" cellspacing="0" cellpadding="0" style="margin:6px 0;">'
            '<tr><td style="background-color:#2d2d2d; border-radius:6px; padding:8px 10px;">'
            '<pre style="margin:0; font-family:Consolas,\'Cascadia Code\',monospace; '
            'font-size:9pt; white-space:pre-wrap; color:#f8f8f2;">'
            f"{highlighted}</pre></td></tr></table>"
        )
        result.append("\n\n")
        result.append(key)
        result.append("\n\n")
        pos = close + 3
        while pos < n and md_text[pos] in "\n\r":
            pos += 1

    processed = "".join(result)
    return processed, placeholders


def _style_inline_code(body_html: str) -> str:
    """Add Qt-friendly styles to <code> from markdown2 when not already styled."""
    style = (
        "background-color:rgba(128,128,128,0.22); border-radius:3px; "
        "padding:1px 5px; font-family:Consolas,'Cascadia Code',monospace; font-size:9pt;"
    )

    def repl(m: re.Match) -> str:
        attrs = (m.group(1) or "").strip()
        content = m.group(2)
        if "style=" in attrs:
            return m.group(0)
        if attrs:
            return f'<code {attrs} style="{style}">{content}</code>'
        return f'<code style="{style}">{content}</code>'

    return re.sub(r"<code([^>]*)>(.*?)</code>", repl, body_html, flags=re.DOTALL)


def markdown_to_html(text: str) -> str:
    """Convert markdown to a full HTML document for QTextBrowser."""
    if not text:
        return "<html><head></head><body></body></html>"

    try:
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        md_body, code_map = _extract_fenced_code(text)

        import markdown2

        body_html = markdown2.markdown(
            md_body,
            extras=[
                "tables",
                "strike",
                "task_list",
                "break-on-newline",
                "cuddled-lists",
            ],
        )

        for key, block_html in code_map.items():
            wrapped_p = "<p>" + key + "</p>"
            if wrapped_p in body_html:
                body_html = body_html.replace(wrapped_p, block_html)
            else:
                body_html = body_html.replace(key, block_html)

        body_html = _style_inline_code(body_html)
        body_html = body_html.replace("<br />", "<br/>")

        body_html = body_html.replace(
            "<table>",
            '<table border="1" cellspacing="0" cellpadding="4" width="100%" '
            'style="border-color:#888888; margin:6px 0;">',
        )
        body_html = body_html.replace("<th>", '<th align="left" bgcolor="#E8E8E8">')
        body_html = body_html.replace("<td>", "<td>")

        for level in range(1, 7):
            body_html = body_html.replace(
                f"<h{level}>",
                f'<h{level} style="margin:10px 0 4px 0;">',
            )

        body_html = body_html.replace(
            "<blockquote>",
            '<blockquote style="margin:6px 0; padding-left:8px;">',
        )
        body_html = body_html.replace(
            "<ul>",
            '<ul style="margin:4px 0; padding-left:22px;">',
        )
        body_html = body_html.replace(
            "<ol>",
            '<ol style="margin:4px 0; padding-left:22px;">',
        )
        body_html = body_html.replace("<li>", '<li style="margin:2px 0;">')
        body_html = body_html.replace(
            "<p>",
            '<p style="margin:4px 0; line-height:1.35;">',
        )

        return f"""<!DOCTYPE HTML>
<html>
<head>
<meta charset="utf-8"/>
<style type="text/css">
body {{
  font-size: 10pt;
  line-height: 1.35;
  margin: 0;
  padding: 0;
}}
p {{ margin: 4px 0; line-height: 1.35; }}
ul, ol {{ margin: 4px 0; padding-left: 22px; }}
li {{ margin: 2px 0; }}
strong {{ font-weight: bold; }}
em {{ font-style: italic; }}
a {{ color: #1976D2; }}
blockquote {{ margin: 6px 0; padding-left: 8px; border-left: 3px solid #90CAF9; }}
h1, h2, h3, h4, h5, h6 {{ font-weight: bold; }}
table {{ border-collapse: collapse; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

    except Exception as e:
        logger.error(f"Markdown rendering failed: {e}")
        esc = html.escape(text)
        return (
            "<html><body><p style=\"margin:4px 0;\">"
            + esc.replace("\n", "<br/>")
            + "</p></body></html>"
        )
