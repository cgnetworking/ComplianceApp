from __future__ import annotations

import html
import re

import bleach

HTML_ALLOWED_TAGS = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "dd",
        "div",
        "dl",
        "dt",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "span",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    }
)
HTML_ALLOWED_ATTRIBUTES = {
    "*": ["class"],
    "a": ["href", "title", "target", "rel"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}
HTML_ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})
HTML_SANITIZER = bleach.sanitizer.Cleaner(
    tags=HTML_ALLOWED_TAGS,
    attributes=HTML_ALLOWED_ATTRIBUTES,
    protocols=HTML_ALLOWED_PROTOCOLS,
    strip=True,
    strip_comments=True,
)
PURPOSE_RE = re.compile(r"^## 1\. Purpose\s+([\s\S]*?)\s+## ", re.MULTILINE)


def extract_purpose_from_markdown(value: str) -> str:
    match = PURPOSE_RE.search(value)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def sanitize_uploaded_html(value: str) -> str:
    raw_html = str(value or "")
    sanitized = HTML_SANITIZER.clean(raw_html).strip()
    if sanitized:
        return sanitized
    if not raw_html.strip():
        return ""
    return f"<pre class=\"document-pre\">{html.escape(raw_html)}</pre>"


__all__ = [
    "extract_purpose_from_markdown",
    "sanitize_uploaded_html",
]
