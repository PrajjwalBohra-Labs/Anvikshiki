"""Search abstraction for discovering candidate web sources.

Search rank is retained as discovery metadata only.  It is never used as an
evidence-quality or source-authority signal.
"""

from dataclasses import dataclass
from urllib.parse import (
    parse_qs,
    parse_qsl,
    quote_plus,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)

import httpx
from bs4 import BeautifulSoup

from backend.app.core.config import settings
from backend.app.core.errors import AnvikshikiDomainError

SEARCH_ENDPOINT = "https://lite.duckduckgo.com/lite/"


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    canonical_url: str
    snippet: str
    rank: int
    domain: str


def canonicalize_url(url: str) -> str:
    """Return a stable public URL form without changing its resource query."""
    if not isinstance(url, str) or not url.strip():
        raise AnvikshikiDomainError("A URL is required.", status_code=400)
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise AnvikshikiDomainError("Only public HTTP and HTTPS URLs are allowed.", status_code=400)
    if parsed.username or parsed.password:
        raise AnvikshikiDomainError("URLs containing credentials are not allowed.", status_code=400)
    try:
        port = parsed.port
    except ValueError as exc:
        raise AnvikshikiDomainError("The URL port is invalid.", status_code=400) from exc
    hostname = parsed.hostname.rstrip(".").lower().encode("idna").decode("ascii")
    netloc = hostname
    if ":" in hostname and not hostname.startswith("["):
        netloc = f"[{hostname}]"
    if port and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
        netloc = f"{netloc}:{port}"
    query = urlencode(parse_qsl(parsed.query, keep_blank_values=True), doseq=True)
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", query, ""))


class WebSearchService:
    """Small deterministic HTML search adapter with explicit failure handling."""

    async def search(self, query: str, max_results: int | None = None) -> list[WebSearchResult]:
        query = (query or "").strip()
        if not query or len(query) > 1000:
            raise AnvikshikiDomainError("Search query must contain 1-1000 characters.", status_code=400)
        limit = max_results or settings.WEB_RETRIEVAL_MAX_RESULTS
        if limit < 1 or limit > settings.WEB_RETRIEVAL_MAX_RESULTS:
            raise AnvikshikiDomainError("The requested result limit is invalid.", status_code=400)
        try:
            async with httpx.AsyncClient(timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{SEARCH_ENDPOINT}?q={quote_plus(query)}",
                    headers={"User-Agent": settings.WEB_SEARCH_USER_AGENT},
                )
                if len(response.content) > settings.WEB_MAX_RESPONSE_BYTES:
                    raise AnvikshikiDomainError("Search response exceeds the configured size limit.", status_code=413)
                response.raise_for_status()
        except AnvikshikiDomainError:
            raise
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise AnvikshikiDomainError("Web search is temporarily unavailable.", status_code=502) from exc

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[WebSearchResult] = []
        anchors = soup.select("a.result__a, a.result-link")
        if not anchors and "no results" not in soup.get_text(" ", strip=True).lower():
            raise AnvikshikiDomainError(
                "Web search response contained no parseable results.", status_code=502
            )
        for anchor in anchors:
            href = anchor.get("href")
            if not href:
                continue
            if href.startswith("//duckduckgo.com/l/"):
                href = parse_qs(urlsplit(urljoin("https://duckduckgo.com", href)).query).get("uddg", [""])[0]
            try:
                canonical = canonicalize_url(href)
            except AnvikshikiDomainError:
                continue
            parsed = urlsplit(canonical)
            result = anchor.find_parent(class_="result")
            snippet_node = result.select_one(".result__snippet") if result else None
            results.append(
                WebSearchResult(
                    title=anchor.get_text(" ", strip=True) or canonical,
                    url=href,
                    canonical_url=canonical,
                    snippet=snippet_node.get_text(" ", strip=True) if snippet_node else "",
                    rank=len(results) + 1,
                    domain=parsed.hostname or "",
                )
            )
            if len(results) == limit:
                break
        return results
