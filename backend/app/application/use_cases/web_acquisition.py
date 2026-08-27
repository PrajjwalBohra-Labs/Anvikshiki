import ipaddress
import socket
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import structlog

from backend.app.core.errors import AnvikshikiDomainError
from backend.app.core.config import settings
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import DocumentModel, PassageModel, SourceModel
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)

logger = structlog.get_logger(__name__)


class WebAcquisitionService:
    def __init__(self, session: AsyncSession, storage_service: LocalStorageService):
        self.session = session
        self.storage = storage_service

    @staticmethod
    def _validate_public_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AnvikshikiDomainError(
                "Only public HTTP and HTTPS URLs are allowed.", status_code=400
            )
        if parsed.username or parsed.password:
            raise AnvikshikiDomainError(
                "URLs containing credentials are not allowed.", status_code=400
            )

        hostname = parsed.hostname.rstrip(".").lower()
        if hostname in {"localhost", "localhost.localdomain", "ip6-localhost"}:
            raise AnvikshikiDomainError(
                "Private and loopback destinations are not allowed.", status_code=403
            )

        try:
            addresses = {
                sockaddr[4][0]
                for sockaddr in socket.getaddrinfo(
                    hostname, parsed.port, type=socket.SOCK_STREAM
                )
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

    async def acquire_url(
        self, url: str, source_title: Optional[str] = None
    ) -> Tuple[SourceModel, DocumentModel, List[PassageModel]]:
        """Fetch, clean, archive, and index a public web document."""
        original_url = url
        try:
            async with httpx.AsyncClient(
                timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as client:
                for _ in range(5):
                    self._validate_public_url(url)
                    response = await client.get(
                        url, headers={"User-Agent": "AnvikshikiResearchBot/1.0"}
                    )
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("location")
                        if not location:
                            raise AnvikshikiDomainError(
                                "Redirect response did not provide a destination.",
                                status_code=502,
                            )
                        url = urljoin(url, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                        raise AnvikshikiDomainError(
                            f"Unsupported web content type: {content_type or 'missing'}.",
                            status_code=415,
                        )
                    if len(response.content) > settings.WEB_MAX_RESPONSE_BYTES:
                        raise AnvikshikiDomainError(
                            "Web response exceeds the configured size limit.",
                            status_code=413,
                        )
                    html_content = response.text
                    break
                else:
                    raise AnvikshikiDomainError(
                        "Too many redirects while retrieving URL.", status_code=502
                    )
        except AnvikshikiDomainError:
            raise
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.error("Failed to fetch external URL", url=url, error=str(exc))
            raise AnvikshikiDomainError(
                f"Failed to retrieve URL {url}: {str(exc)}", status_code=502
            ) from exc

        soup = BeautifulSoup(html_content, "html.parser")
        for script_or_style in soup(["script", "style", "nav", "footer", "header"]):
            script_or_style.decompose()

        title = source_title or (
            soup.title.string.strip() if soup.title and soup.title.string else url
        )
        paragraphs = [p.get_text().strip() for p in soup.find_all("p")]
        cleaned_text = "\n\n".join(p for p in paragraphs if len(p) > 20)
        if not cleaned_text:
            cleaned_text = soup.get_text(separator="\n", strip=True)

        content_bytes = cleaned_text.encode("utf-8")
        filename = f"web_scrape_{abs(hash(original_url))}.txt"
        metadata = await self.storage.store_original(content_bytes, filename)

        doc_result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.checksum_sha256 == metadata.checksum_sha256)
        )
        if doc_result.scalars().first():
            raise AnvikshikiDomainError(
                "This exact web document has already been acquired.", status_code=409
            )

        new_source = SourceModel(
            title=title,
            source_type=SourceType.DISCOVERY_ONLY,
            reference_url=original_url,
        )
        self.session.add(new_source)
        await self.session.flush()

        new_doc = DocumentModel(
            source_id=new_source.id,
            checksum_sha256=metadata.checksum_sha256,
            mime_type="text/html",
            total_pages=1,
            original_filename=metadata.original_filename,
            storage_path=metadata.storage_path,
        )
        self.session.add(new_doc)
        await self.session.flush()

        passage_models = []
        chunks = [part.strip() for part in cleaned_text.split("\n\n") if part.strip()]
        embedder = LocalSentenceTransformerEmbeddingAdapter()
        vectors = await embedder.embed_texts(chunks)
        for chunk, vector in zip(chunks, vectors):
            if not chunk:
                continue
            passage = PassageModel(
                document_id=new_doc.id,
                content=chunk,
                page_number=1,
                ocr_confidence=1.0,
                extraction_uncertainty=False,
                language="en",
                embedding_model=embedder.model_version,
                embedding=vector,
            )
            passage_models.append(passage)
            self.session.add(passage)

        await self.session.commit()
        return new_source, new_doc, passage_models
