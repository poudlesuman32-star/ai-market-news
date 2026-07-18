from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from .collector_common import CollectorError, require

_RELEASE_PATH_FRAGMENT = "/news-releases/news-release-details/"
_DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)
_GENERIC_HEADINGS = {"newsroom", "latest news", "press", "investor relations"}
_GENERIC_LINK_TEXT = {"read article", "read more", "view article"}


class _MicronNewsroomParser(HTMLParser):
    """Parse Micron's corporate newsroom cards without fetching article pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict[str, str]] = []
        self._heading_depth = 0
        self._heading_parts: list[str] = []
        self._pending_title = ""
        self._pending_date = ""
        self._release_href: str | None = None
        self._release_link_parts: list[str] = []

    @staticmethod
    def _clean(parts: list[str]) -> str:
        return " ".join(" ".join(parts).split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered in {"h2", "h3", "h4", "h5", "h6"}:
            if self._heading_depth == 0:
                self._heading_parts = []
            self._heading_depth += 1

        if lowered == "a":
            href = str(dict(attrs).get("href") or "").strip()
            if _RELEASE_PATH_FRAGMENT in href:
                self._release_href = href
                self._release_link_parts = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"h2", "h3", "h4", "h5", "h6"} and self._heading_depth:
            self._heading_depth -= 1
            if self._heading_depth == 0:
                title = self._clean(self._heading_parts)
                if title and title.casefold() not in _GENERIC_HEADINGS:
                    self._pending_title = title

        if lowered == "a" and self._release_href is not None:
            link_text = self._clean(self._release_link_parts)
            title = self._pending_title
            if not title and link_text.casefold() not in _GENERIC_LINK_TEXT:
                title = link_text
            if title and self._pending_date:
                self.entries.append(
                    {
                        "title": title,
                        "link": self._release_href,
                        "identifier": self._release_href,
                        "published": self._pending_date,
                        "summary": title,
                    }
                )
                self._pending_title = ""
                self._pending_date = ""
            self._release_href = None
            self._release_link_parts = []

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        if self._heading_depth:
            self._heading_parts.append(data)
        if self._release_href is not None:
            self._release_link_parts.append(data)
        match = _DATE_PATTERN.search(data)
        if match:
            self._pending_date = match.group(0)


def parse_micron_newsroom_index(body: bytes, *, index_url: str) -> list[dict[str, str]]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("utf-8", errors="replace")

    parser = _MicronNewsroomParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise CollectorError("Micron newsroom index contains invalid HTML") from exc

    require(bool(parser.entries), "Micron newsroom index contains no release entries")
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in parser.entries:
        link = urljoin(index_url, entry["link"])
        require(link not in seen, f"duplicate Micron newsroom release link: {link}")
        seen.add(link)
        entries.append({**entry, "link": link, "identifier": link})
    return entries
