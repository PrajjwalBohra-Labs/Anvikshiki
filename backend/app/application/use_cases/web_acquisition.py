"""Safe acquisition of web representations into the normal ingestion path."""

import asyncio
import base64
import hashlib
import ipaddress
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import structlog
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.application.use_cases.provenance import ProvenanceService
from backend.app.application.use_cases.web_search import canonicalize_url
from backend.app.core.config import settings
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
    DocumentModel,
    DocumentVersionModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.storage.local_storage import LocalStorageService

logger = structlog.get_logger(__name__)


class WebAcquisitionService:
    MAX_REDIRECTS = 5

    def __init__(self, session: AsyncSession, storage_service: LocalStorageService):
        self.session = session
        self.storage = storage_service

    @staticmethod
    def _validate_public_url(url: str) -> None:
        canonical = canonicalize_url(url)
        parsed = urlsplit(canonical)
        hostname = parsed.hostname or ""
        if hostname in {"localhost", "localhost.localdomain", "ip6-localhost"}:
            raise AnvikshikiDomainError(
                "Private and loopback destinations are not allowed.", status_code=403
            )
        try:
            addresses = {
                sockaddr[4][0]
                for sockaddr in socket.getaddrinfo(hostname, parsed.port, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError) as exc:
            raise AnvikshikiDomainError(
                f"Unable to resolve URL host '{hostname}'.", status_code=400
            ) from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                raise AnvikshikiDomainError(
                    "Private and loopback destinations are not allowed.", status_code=403
                )

    @staticmethod
    def _cache_path(storage: LocalStorageService, canonical_url: str) -> Path:
        key = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        return storage.cached_web_dir / f"{key}.json"

    async def _read_cache(self, canonical_url: str) -> dict[str, Any] | None:
        if self.storage is None:
            return None
        path = self._cache_path(self.storage, canonical_url)
        if not path.is_file():
            return None
        try:
            payload = await asyncio.to_thread(path.read_text, encoding="utf-8")
            cached = json.loads(payload)
            if cached.get("canonical_url") != canonical_url:
                return None
            content = base64.b64decode(cached["content_base64"], validate=True)
            if len(content) > settings.WEB_MAX_RESPONSE_BYTES:
                return None
            cached["content"] = content
            cached["cache_hit"] = True
            return cached
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            logger.warning("Ignoring invalid web cache entry", url=canonical_url)
            return None

    async def _write_cache(self, canonical_url: str, record: dict[str, Any], content: bytes) -> None:
        if self.storage is None:
            return
        path = self._cache_path(self.storage, canonical_url)
        payload = {
            **record,
            "canonical_url": canonical_url,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        temporary = path.with_suffix(".tmp")
        try:
            await asyncio.to_thread(temporary.write_text, json.dumps(payload, sort_keys=True), encoding="utf-8")
            await asyncio.to_thread(temporary.replace, path)
        except OSError:
            try:
                await asyncio.to_thread(temporary.unlink, missing_ok=True)
            except OSError:
                pass
            logger.warning("Unable to persist web cache entry", url=canonical_url)

    async def _robots_allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        if not settings.WEB_RESPECT_ROBOTS:
            return True
        parsed = urlsplit(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            response = await client.get(robots_url, headers={"User-Agent": settings.WEB_USER_AGENT})
            if response.status_code == 404:
                return True
            if response.status_code >= 400:
                raise AnvikshikiDomainError(
                    "The site's robots policy could not be retrieved.", status_code=502
                )
            if len(response.content) > 256_000:
                raise AnvikshikiDomainError("The site's robots policy is too large.", status_code=413)
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(response.text.splitlines())
            if not parser.can_fetch(settings.WEB_USER_AGENT, url):
                raise AnvikshikiDomainError("The site's robots policy disallows this URL.", status_code=403)
            return True
        except AnvikshikiDomainError:
            raise
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise AnvikshikiDomainError("Unable to determine the site's robots policy.", status_code=502) from exc

    @staticmethod
    def _metadata_from_content(content: bytes, content_type: str, final_url: str) -> dict[str, Any]:
        if content_type not in {"text/html", "application/xhtml+xml"}:
            return {"title": final_url, "language": None, "author": None, "description": None}
        soup = BeautifulSoup(content, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""

        def meta(name: str) -> str | None:
            node = soup.find("meta", attrs={"name": name})
            return node.get("content", "").strip() or None if node else None

        canonical_link = soup.find("link", rel=lambda value: value and "canonical" in value)
        return {
            "title": title or final_url,
            "language": soup.html.get("lang") if soup.html else None,
            "author": meta("author"),
            "description": meta("description"),
            "canonical_document_url": urljoin(final_url, canonical_link.get("href")) if canonical_link else None,
        }

    async def _fetch(self, original_url: str, canonical_url: str) -> dict[str, Any]:
        cached = await self._read_cache(canonical_url)
        if cached:
            return cached
        url = canonical_url
        try:
            async with httpx.AsyncClient(
                timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS,
                follow_redirects=False,
                headers={"User-Agent": settings.WEB_USER_AGENT},
            ) as client:
                for _ in range(self.MAX_REDIRECTS + 1):
                    self._validate_public_url(url)
                    await self._robots_allowed(client, url)
                    response = await client.get(url)
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("location")
                        if not location:
                            raise AnvikshikiDomainError(
                                "Redirect response did not provide a destination.", status_code=502
                            )
                        url = canonicalize_url(urljoin(url, location))
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                        raise AnvikshikiDomainError(
                            f"Unsupported web content type: {content_type or 'missing'}.", status_code=415
                        )
                    declared_size = response.headers.get("content-length")
                    if declared_size and int(declared_size) > settings.WEB_MAX_RESPONSE_BYTES:
                        raise AnvikshikiDomainError("Web response exceeds the configured size limit.", status_code=413)
                    content = response.content
                    if len(content) > settings.WEB_MAX_RESPONSE_BYTES:
                        raise AnvikshikiDomainError("Web response exceeds the configured size limit.", status_code=413)
                    response_url = response.url if isinstance(response.url, str) else url
                    final_url = canonicalize_url(response_url)
                    record = {
                        "original_url": original_url,
                        "final_url": final_url,
                        "status_code": response.status_code,
                        "content_type": content_type,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "response_headers": {
                            key: response.headers[key]
                            for key in ("content-type", "content-language", "etag", "last-modified", "date")
                            if key in response.headers
                        },
                        "cache_hit": False,
                    }
                    await self._write_cache(canonical_url, record, content)
                    return {**record, "content": content}
                raise AnvikshikiDomainError("Too many redirects while retrieving URL.", status_code=502)
        except AnvikshikiDomainError:
            raise
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            logger.error("Failed to fetch external URL", url=url, error=str(exc))
            raise AnvikshikiDomainError(f"Failed to retrieve URL {url}: {exc}", status_code=502) from exc

    async def acquire_url(
        self, url: str, source_title: str | None = None
    ) -> tuple[SourceModel, DocumentModel, list[PassageModel]]:
        """Acquire raw bytes, cache them, then use ordinary ingestion/provenance."""
        canonical_url = canonicalize_url(url)
        self._validate_public_url(canonical_url)
        fetched = await self._fetch(url, canonical_url)
        content = fetched["content"]
        checksum = hashlib.sha256(content).hexdigest()
        existing = await self.session.scalar(select(DocumentModel).where(DocumentModel.checksum_sha256 == checksum))
        if existing:
            raise AnvikshikiDomainError("This exact web document has already been acquired.", status_code=409)

        content_type = fetched["content_type"]
        extracted = self._metadata_from_content(content, content_type, fetched["final_url"])
        source = SourceModel(
            title=(source_title or extracted["title"])[:512],
            author=extracted.get("author"),
            original_language=extracted.get("language"),
            source_type=SourceType.DISCOVERY_ONLY,
            reference_url=canonical_url,
        )
        self.session.add(source)
        await self.session.flush()
        try:
            document, passages = await DocumentIngestionService(self.session, self.storage).ingest_file(
                source_id=source.id,
                filename=f"web_{checksum}.{'txt' if content_type == 'text/plain' else 'html'}",
                content=content,
                mime_type=content_type,
            )
            document.web_metadata = {
                "original_url": url,
                "canonical_url": canonical_url,
                "final_url": fetched["final_url"],
                "status_code": fetched["status_code"],
                "content_type": content_type,
                "fetched_at": fetched["fetched_at"],
                "cache_hit": fetched["cache_hit"],
                "response_headers": fetched["response_headers"],
                "extracted_title": extracted["title"],
                "description": extracted.get("description"),
                "canonical_document_url": extracted.get("canonical_document_url"),
                "source_classification": SourceType.DISCOVERY_ONLY.value,
            }
            version_result = await self.session.execute(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.document_id == document.id)
                .options(selectinload(DocumentVersionModel.pages))
            )
            version = version_result.scalars().first()
            await ProvenanceService(self.session).record_document_ancestry(
                document, version, version.pages if version else (), passages
            )
            await self.session.commit()
            return source, document, passages
        except Exception:
            await self.session.rollback()
            raise
