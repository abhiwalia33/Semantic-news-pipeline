"""HTML-safety helpers for streamlit_app.py (kept separate so they can be unit tested).

Every value that comes from the API/database must go through one of these before
being placed into markup rendered with unsafe_allow_html=True.
"""
import html
from urllib.parse import urlparse


def esc(value) -> str:
    """Escape text for use in HTML element content or a quoted attribute."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def snippet(text, max_chars: int = 400) -> str:
    """Truncate first, then escape, so an entity like &amp; is never cut in half."""
    return esc((text or "")[:max_chars].strip())


def safe_url(url) -> str:
    """Escaped URL for an href; anything that isn't http(s) becomes '#'."""
    if not url or urlparse(str(url)).scheme.lower() not in ("http", "https"):
        return "#"
    return esc(url)
