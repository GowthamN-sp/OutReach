"""Allowlist renderer shared by tracked and untracked campaign emails."""

import html
import ipaddress
import re
from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
TAGS = {
    "p",
    "div",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
}


def safe_url(value: str) -> str | None:
    """Accept absolute HTTP(S) URLs without credentials or ambiguous syntax."""
    if not value or len(value) > 4096:
        return None
    decoded = unquote(value)
    if (
        any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)
        or any(c in decoded for c in ("\r", "\n", "\x00", "\\"))
        or any(c in value for c in ("<", ">", '"', "\\"))
    ):
        return None
    if re.search(r"%(?![0-9a-fA-F]{2})", value):
        return None
    try:
        parts = urlsplit(value)
        host = parts.hostname
        if (
            parts.scheme.lower() not in {"http", "https"}
            or not host
            or parts.username is not None
            or parts.password is not None
        ):
            return None
        if parts.port is not None and not 1 <= parts.port <= 65535:
            return None
        try:
            ipaddress.ip_address(host)
        except ValueError:
            host = host.encode("idna").decode("ascii")
            if len(host) > 253 or not all(
                re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                for label in host.rstrip(".").split(".")
            ):
                return None
    except (ValueError, UnicodeError):
        return None
    return value


def public_origin(value: str) -> bool:
    if not safe_url(value):
        return False
    parts = urlsplit(value)
    host = parts.hostname.lower().rstrip(".")
    if (
        parts.scheme != "https"
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return (
            "." in host
            and not host.endswith(
                (".localhost", ".local", ".internal", ".test", ".invalid")
            )
            and host != "localhost"
        )


def must_remain_direct(target: str, attrs: dict[str, str | None]) -> bool:
    parts = urlsplit(target)
    return (
        parts.scheme not in {"http", "https"}
        or "data-no-track" in attrs
        or "unsubscribe" in (attrs.get("rel") or "").lower().split()
        or any(
            word in unquote(parts.path + "?" + parts.query).lower()
            for word in ("unsubscribe", "opt-out", "optout")
        )
        or parts.path.startswith(("/api/track/", "/api/t/", "/api/o/"))
    )


def safe_direct_anchor(value: str) -> str | None:
    """Keep ordinary email and telephone anchors direct, never track them."""
    if any(ord(c) < 32 or c in '<>"\\' for c in unquote(value)):
        return None
    if re.fullmatch(r"mailto:[^\s@?]+@[^\s@?]+(?:\?[^\s]*)?", value, re.IGNORECASE):
        return value
    if re.fullmatch(r"tel:\+?[0-9(). -]{1,40}", value, re.IGNORECASE):
        return value
    return None


class Renderer(HTMLParser):
    def __init__(self, rewrite: Callable[[str], str] | None):
        super().__init__(convert_charrefs=True)
        self.rewrite = rewrite
        self.markup: list[str] = []
        self.plain: list[str] = []
        self.anchor: str | None = None
        self.stack: list[str] = []

    def destination(self, target: str, attrs: dict[str, str | None]) -> str:
        return (
            self.rewrite(target)
            if self.rewrite and not must_remain_direct(target, attrs)
            else target
        )

    def close_anchor(self) -> None:
        if self.anchor:
            self.markup.append("</a>")
            self.plain.append(f" ({self.anchor})")
            self.anchor = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a":
            self.close_anchor()
            href = attributes.get("href") or ""
            target = safe_url(href) or safe_direct_anchor(href)
            if target:
                self.anchor = target
                direct = (
                    ' data-no-track="true"'
                    if must_remain_direct(target, attributes)
                    else ""
                )
                self.markup.append(
                    f'<a href="{html.escape(self.destination(target, attributes), quote=True)}"{direct}>'
                )
            return
        if tag in TAGS:
            self.markup.append(f"<{tag}>")
            if tag != "br":
                self.stack.append(tag)
            if tag in {"p", "div", "br", "li", "pre"}:
                self.plain.append("\n")
        else:
            raw = self.get_starttag_text()
            self.markup.append(html.escape(raw))
            self.plain.append(raw)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag in TAGS and tag != "br":
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.close_anchor()
        elif tag in self.stack:
            while self.stack:
                closed = self.stack.pop()
                self.markup.append(f"</{closed}>")
                if closed == tag:
                    break
            if tag in {"p", "div", "li", "pre"}:
                self.plain.append("\n")
        elif tag not in TAGS:
            self.markup.append(html.escape(f"</{tag}>"))
            self.plain.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.plain.append(data)
        if self.anchor:
            self.markup.append(html.escape(data))
            return
        cursor = 0
        for match in URL.finditer(data):
            target = match[0].rstrip(".,;:!?")
            while target and target[-1] in ")]}":
                closing = target[-1]
                opening = {")": "(", "]": "[", "}": "{"}[closing]
                if target.count(closing) <= target.count(opening):
                    break
                target = target[:-1]
            self.markup.append(html.escape(data[cursor : match.start()]))
            if safe_url(target):
                self.markup.append(
                    f'<a href="{html.escape(self.destination(target, {}), quote=True)}">{html.escape(target)}</a>'
                )
                self.markup.append(html.escape(match[0][len(target) :]))
            else:
                self.markup.append(html.escape(match[0]))
            cursor = match.end()
        self.markup.append(html.escape(data[cursor:]))


def render(body: str, rewrite: Callable[[str], str] | None = None) -> tuple[str, str]:
    renderer = Renderer(rewrite)
    # HTMLParser otherwise expands legacy entities without a semicolon, so a
    # plain URL parameter such as &copy=2 or &not=3 would be silently corrupted.
    body = re.sub(
        r"&(?!#[0-9]+;|#[xX][0-9a-fA-F]+;|[a-zA-Z][a-zA-Z0-9]+;)", "&amp;", body
    )
    renderer.feed(body)
    renderer.close()
    renderer.close_anchor()
    while renderer.stack:
        renderer.markup.append(f"</{renderer.stack.pop()}>")
    return "".join(renderer.plain).strip(), "".join(renderer.markup).replace(
        "\n", "<br>"
    )
