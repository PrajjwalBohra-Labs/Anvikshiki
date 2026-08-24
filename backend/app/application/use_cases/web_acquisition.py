from typing import List, Tuple, Optional
from bs4 import BeautifulSoup
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.domain.models.enums import SourceType
from backend.app.core.errors import AnvikshikiDomainError
import structlog

logger = structlog.get_logger(__name__)

class WebAcquisitionService:
    def __init__(self, session: AsyncSession, storage_service: LocalStorageService):
        self.session = session
        self.storage = storage_service

    async def acquire_url(self, url: str, source_title: Optional[str] = None) -> Tuple[SourceModel, DocumentModel, List[PassageModel]]:
        """
        Fetches an external URL, cleans HTML into plain text, archives it locally,
        and indexes it as a DISCOVERY_ONLY source with reference_url tracking.
        """
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "AnvikshikiResearchBot/1.0"})
                response.raise_for_status()
                html_content = response.text
        except httpx.RequestError as e:
            logger.error("Failed to fetch external URL", url=url, error=str(e))
            raise AnvikshikiDomainError(f"Failed to retrieve URL {url}: {str(e)}", status_code=502)

        soup = BeautifulSoup(html_content, "html.parser")
        
        for script_or_style in soup(["script", "style", "nav", "footer", "header"]):
            script_or_style.decompose()

        title = source_title or (soup.title.string.strip() if soup.title and soup.title.string else url)
        
        paragraphs = [p.get_text().strip() for p in soup.find_all("p")]
        cleaned_text = "\n\n".join([p for p in paragraphs if len(p) > 20])
        
        if not cleaned_text:
            cleaned_text = soup.get_text(separator="\n", strip=True)

        content_bytes = cleaned_text.encode("utf-8")
        filename = f"web_scrape_{abs(hash(url))}.txt"

        metadata = await self.storage.store_original(content_bytes, filename)

        doc_result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.checksum_sha256 == metadata.checksum_sha256)
        )
        if doc_result.scalars().first():
            raise AnvikshikiDomainError("This exact web document has already been acquired.", status_code=409)

        new_source = SourceModel(
            title=title,
            source_type=SourceType.DISCOVERY_ONLY,
            reference_url=url
        )
        self.session.add(new_source)
        await self.session.flush()

        new_doc = DocumentModel(
            source_id=new_source.id,
            checksum_sha256=metadata.checksum_sha256,
            mime_type="text/html",
            total_pages=1
        )
        self.session.add(new_doc)
        await self.session.flush()

        chunks = [c.strip() for c in cleaned_text.split("\n\n") if c.strip()]
        passage_models = []
        
        for chunk in chunks:
            passage = PassageModel(
                document_id=new_doc.id,
                content=chunk,
                page_number=1,
                ocr_confidence=1.0,
                extraction_uncertainty=False,
                language="en"
            )
            passage_models.append(passage)
            self.session.add(passage)

        await self.session.commit()
        return new_source, new_doc, passage_models