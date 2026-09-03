"""Durable, typed provenance graph assembly over existing research records."""

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.domain.models.enums import (
    ProvenanceNodeType,
    ProvenanceRelationType,
)
from backend.app.infrastructure.database.models import (
    ArgumentModel,
    ClaimModel,
    DocumentModel,
    DocumentVersionModel,
    EvidenceLinkModel,
    PageModel,
    PassageModel,
    PremiseModel,
    ProvenanceEdgeModel,
    ProvenanceNodeModel,
    ResearchRunModel,
    SourceModel,
    SourceRelationshipModel,
)


class ProvenanceService:
    """Materializes and queries provenance without replacing domain records."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._node_cache: dict[tuple[str, str], ProvenanceNodeModel] = {}
        self._edge_cache: dict[tuple[str, str, str], ProvenanceEdgeModel] = {}
        self._touched_nodes: dict[str, ProvenanceNodeModel] = {}
        self._touched_edges: dict[str, ProvenanceEdgeModel] = {}

    async def _node(
        self,
        node_type: ProvenanceNodeType,
        entity_id: str,
        label: str,
        metadata: dict | None = None,
    ) -> ProvenanceNodeModel:
        key = (node_type.value, str(entity_id))
        cached = self._node_cache.get(key)
        if cached is not None:
            self._touched_nodes[cached.id] = cached
            return cached

        result = await self.session.execute(
            select(ProvenanceNodeModel).where(
                ProvenanceNodeModel.node_type == node_type,
                ProvenanceNodeModel.entity_id == str(entity_id),
            )
        )
        node = result.scalar_one_or_none()
        if node is None:
            node = ProvenanceNodeModel(
                node_type=node_type,
                entity_id=str(entity_id),
                label=label,
                metadata_payload=metadata,
            )
            self.session.add(node)
            await self.session.flush()
        self._node_cache[key] = node
        self._touched_nodes[node.id] = node
        return node

    async def _edge(
        self,
        from_node: ProvenanceNodeModel,
        to_node: ProvenanceNodeModel,
        relationship_type: ProvenanceRelationType,
        metadata: dict | None = None,
    ) -> ProvenanceEdgeModel:
        key = (from_node.id, to_node.id, relationship_type.value)
        cached = self._edge_cache.get(key)
        if cached is not None:
            self._touched_edges[cached.id] = cached
            return cached

        result = await self.session.execute(
            select(ProvenanceEdgeModel).where(
                ProvenanceEdgeModel.from_node_id == from_node.id,
                ProvenanceEdgeModel.to_node_id == to_node.id,
                ProvenanceEdgeModel.relationship_type == relationship_type,
            )
        )
        edge = result.scalar_one_or_none()
        if edge is None:
            edge = ProvenanceEdgeModel(
                from_node_id=from_node.id,
                to_node_id=to_node.id,
                relationship_type=relationship_type,
                metadata_payload=metadata,
            )
            self.session.add(edge)
            await self.session.flush()
        self._edge_cache[key] = edge
        self._touched_edges[edge.id] = edge
        return edge

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _stable_datetime(value: datetime) -> datetime:
        """Return a consistently timezone-aware value across DB dialects.

        SQLite does not preserve the timezone flag of SQLAlchemy DateTime
        columns, so a just-created row and the same row read back could be
        serialized differently.  Provenance exports are deterministic API
        records; interpret legacy naive UTC values explicitly at this
        boundary without changing the stored value.
        """
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _node_payload(node: ProvenanceNodeModel) -> dict:
        return {
            "node_id": node.id,
            "node_type": ProvenanceService._enum_value(node.node_type),
            "entity_id": node.entity_id,
            "label": node.label,
            "metadata": node.metadata_payload or {},
            "created_at": ProvenanceService._stable_datetime(node.created_at),
        }

    @staticmethod
    def _edge_payload(edge: ProvenanceEdgeModel) -> dict:
        return {
            "edge_id": edge.id,
            "from_node_id": edge.from_node_id,
            "to_node_id": edge.to_node_id,
            "relationship_type": ProvenanceService._enum_value(edge.relationship_type),
            "metadata": edge.metadata_payload or {},
            "created_at": ProvenanceService._stable_datetime(edge.created_at),
        }

    async def link_sources(
        self, source_id: str, target_id: str, relationship_type: str
    ) -> SourceRelationshipModel:
        """Link a derivative source to its parent original source."""
        rel = SourceRelationshipModel(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
        )
        self.session.add(rel)
        await self.session.commit()
        return rel

    async def trace_lineage(self, source_id: str) -> list[dict]:
        """Trace source lineage while retaining the existing response shape."""
        lineage = []
        current_id = source_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            stmt = select(SourceModel).where(SourceModel.id == current_id).options(
                selectinload(SourceModel.targets).selectinload(SourceRelationshipModel.target)
            )
            result = await self.session.execute(stmt)
            source = result.scalars().first()
            if not source:
                break
            lineage.append({"source_id": source.id, "title": source.title, "type": source.source_type})
            if source.targets:
                primary_target = source.targets[0]
                lineage[-1]["derived_via"] = primary_target.relationship_type
                current_id = primary_target.target_id
            else:
                current_id = None
        return lineage

    async def record_document_ancestry(
        self,
        document: DocumentModel,
        version: DocumentVersionModel | None = None,
        pages: Iterable[PageModel] = (),
        passages: Iterable[PassageModel] = (),
    ) -> None:
        """Persist source-to-passage ancestry for an ingested document."""
        source = await self.session.get(SourceModel, document.source_id)
        if source is None:
            return
        source_node = await self._node(
            ProvenanceNodeType.SOURCE,
            source.id,
            source.title,
            {
                "source_type": self._enum_value(source.source_type),
                "author": source.author,
                "reference_url": source.reference_url,
            },
        )
        document_node = await self._node(
            ProvenanceNodeType.DOCUMENT,
            document.id,
            document.original_filename or document.id,
            {
                "source_id": document.source_id,
                "checksum_sha256": document.checksum_sha256,
                "mime_type": document.mime_type,
                "web_metadata": document.web_metadata,
            },
        )
        await self._edge(source_node, document_node, ProvenanceRelationType.CONTAINS)

        version_node = None
        if version is not None:
            version_node = await self._node(
                ProvenanceNodeType.DOCUMENT_VERSION,
                version.id,
                f"Version {version.version_number}",
                {
                    "document_id": version.document_id,
                    "version_number": version.version_number,
                    "checksum_sha256": version.checksum_sha256,
                    "extraction_method": version.extraction_method,
                    "extraction_status": version.extraction_status,
                },
            )
            await self._edge(document_node, version_node, ProvenanceRelationType.HAS_VERSION)

        page_nodes = {}
        for page in pages:
            if version_node is None:
                continue
            page_node = await self._node(
                ProvenanceNodeType.PAGE,
                page.id,
                f"Page {page.page_number}",
                {
                    "document_version_id": page.document_version_id,
                    "page_number": page.page_number,
                    "page_order": page.page_order,
                    "extraction_method": page.extraction_method,
                    "extraction_status": page.extraction_status,
                    "ocr_status": page.ocr_status,
                    "ocr_language": page.ocr_language,
                    "ocr_text_length": page.ocr_text_length,
                    "ocr_confidence": page.ocr_confidence,
                },
            )
            page_nodes[page.id] = page_node
            await self._edge(version_node, page_node, ProvenanceRelationType.CONTAINS)

        for passage in passages:
            passage_node = await self._node(
                ProvenanceNodeType.PASSAGE,
                passage.id,
                f"Passage {passage.passage_order if passage.passage_order is not None else passage.id}",
                {
                    "document_id": passage.document_id,
                    "document_version_id": passage.document_version_id,
                    "page_id": passage.page_id,
                    "page_number": passage.page_number,
                    "passage_order": passage.passage_order,
                    "extraction_method": passage.extraction_method,
                    "extraction_uncertainty": passage.extraction_uncertainty,
                    "ocr_confidence": passage.ocr_confidence,
                    "language": passage.language,
                    "section_heading": passage.section_heading,
                    "embedding_status": self._enum_value(passage.embedding_status),
                    "embedding_provider": passage.embedding_provider,
                    "embedding_model_version": passage.embedding_model_version,
                    "embedding_dimension": passage.embedding_dimension,
                    "embedding_config_fingerprint": passage.embedding_config_fingerprint,
                    "embedding_content_sha256": passage.embedding_content_sha256,
                },
            )
            parent = page_nodes.get(passage.page_id) or version_node
            if parent is not None:
                await self._edge(parent, passage_node, ProvenanceRelationType.CONTAINS)

    async def _record_passage_ancestry(self, passage: PassageModel) -> None:
        document = passage.document
        version = passage.document_version
        pages = version.pages if version is not None else []
        await self.record_document_ancestry(document, version, pages, [passage])

    async def _materialize_run(self, run_id: str) -> ResearchRunModel | None:
        run = await self.session.get(ResearchRunModel, run_id)
        if run is None:
            return None

        self._touched_nodes.clear()
        self._touched_edges.clear()
        run_node = await self._node(
            ProvenanceNodeType.RESEARCH_RUN,
            run.id,
            run.query,
            {"status": run.status, "user_id": run.user_id, "domain": run.domain},
        )
        claims_result = await self.session.execute(
            select(ClaimModel)
            .where(ClaimModel.research_run_id == run_id)
            .order_by(ClaimModel.created_at.asc())
        )
        claims = claims_result.scalars().all()
        claim_ids = [claim.id for claim in claims]
        evidence_result = await self.session.execute(
            select(EvidenceLinkModel)
            .where(EvidenceLinkModel.claim_id.in_(claim_ids))
            .order_by(EvidenceLinkModel.created_at.asc())
        ) if claim_ids else None
        evidence_links = evidence_result.scalars().all() if evidence_result else []
        passage_ids = {link.passage_id for link in evidence_links}
        passage_ids.update(
            claim.provenance_id for claim in claims if claim.provenance_id
        )
        passages_result = await self.session.execute(
            select(PassageModel)
            .where(PassageModel.id.in_(passage_ids))
            .options(
                selectinload(PassageModel.document).selectinload(DocumentModel.source),
                selectinload(PassageModel.document_version).selectinload(DocumentVersionModel.pages),
                selectinload(PassageModel.page),
            )
        ) if passage_ids else None
        passages = {passage.id: passage for passage in passages_result.scalars().all()} if passages_result else {}

        for passage in passages.values():
            await self._record_passage_ancestry(passage)
        claim_nodes = {}
        for claim in claims:
            claim_node = await self._node(
                ProvenanceNodeType.CLAIM,
                claim.id,
                claim.statement,
                {
                    "claim_type": self._enum_value(claim.claim_type),
                    "confidence": claim.confidence,
                    "lifecycle_status": claim.lifecycle_status,
                    "research_run_id": claim.research_run_id,
                },
            )
            claim_nodes[claim.id] = claim_node
            await self._edge(run_node, claim_node, ProvenanceRelationType.PRODUCES)
            if claim.provenance_id in passages:
                passage_node = await self._node(
                    ProvenanceNodeType.PASSAGE,
                    claim.provenance_id,
                    f"Passage {claim.provenance_id}",
                )
                await self._edge(claim_node, passage_node, ProvenanceRelationType.DERIVES_FROM)

        for link in evidence_links:
            evidence_node = await self._node(
                ProvenanceNodeType.EVIDENCE,
                link.id,
                f"Evidence {self._enum_value(link.relation_type)}",
                {
                    "claim_id": link.claim_id,
                    "premise_id": link.premise_id,
                    "passage_id": link.passage_id,
                    "relation_type": self._enum_value(link.relation_type),
                    "confidence_weight": link.confidence_weight,
                },
            )
            if link.claim_id in claim_nodes:
                claim_node = claim_nodes[link.claim_id]
                relation = ProvenanceRelationType(self._enum_value(link.relation_type))
                await self._edge(claim_node, evidence_node, ProvenanceRelationType.HAS_EVIDENCE)
                await self._edge(evidence_node, claim_node, relation)
                if link.passage_id in passages:
                    passage_node = await self._node(
                        ProvenanceNodeType.PASSAGE,
                        link.passage_id,
                        f"Passage {link.passage_id}",
                    )
                    await self._edge(passage_node, claim_node, relation)
            if link.passage_id in passages:
                passage_node = await self._node(
                    ProvenanceNodeType.PASSAGE,
                    link.passage_id,
                    f"Passage {link.passage_id}",
                )
                await self._edge(evidence_node, passage_node, ProvenanceRelationType.CITES)

        output = run.output_references or {}
        validation = output.get("validation") if isinstance(output, dict) else None
        validation_node = None
        if isinstance(validation, dict) and validation:
            validation_node = await self._node(
                ProvenanceNodeType.VALIDATION,
                f"{run.id}:validation",
                f"Validation for {run.query}",
                validation,
            )
            await self._edge(run_node, validation_node, ProvenanceRelationType.HAS_VALIDATION)
            validated_claims = validation.get("validated_claims", [])
            for item in validated_claims:
                claim_node = claim_nodes.get(item.get("claim_id"))
                if claim_node is not None:
                    await self._edge(claim_node, validation_node, ProvenanceRelationType.VALIDATED_BY)

        synthesis_node = None
        final_response = output.get("final_response") if isinstance(output, dict) else None
        if final_response:
            synthesis_node = await self._node(
                ProvenanceNodeType.SYNTHESIS,
                f"{run.id}:synthesis",
                f"Synthesis for {run.query}",
                {
                    "research_run_id": run.id,
                    "validation_status": output.get("validation_status"),
                    "validated_claims_count": output.get("validated_claims_count", 0),
                },
            )
            await self._edge(run_node, synthesis_node, ProvenanceRelationType.PRODUCES)
            if validation_node is not None:
                await self._edge(validation_node, synthesis_node, ProvenanceRelationType.VALIDATES)
            for item in (validation or {}).get("validated_claims", []):
                claim_node = claim_nodes.get(item.get("claim_id"))
                if claim_node is not None:
                    await self._edge(claim_node, synthesis_node, ProvenanceRelationType.CONTRIBUTES_TO)

        specialist_payload = output.get("specialist_analysis") if isinstance(output, dict) else {}
        if isinstance(specialist_payload, dict):
            for specialist_type, entries in specialist_payload.items():
                if isinstance(entries, dict):
                    entries = [entries]
                if not isinstance(entries, list):
                    continue
                for index, entry in enumerate(entries):
                    if not isinstance(entry, dict) or not entry:
                        continue
                    result_id = entry.get("argument_id") or entry.get("criticism_id")
                    entity_id = str(result_id or f"{run.id}:{specialist_type}:{index}")
                    analysis_node = await self._node(
                        ProvenanceNodeType.SPECIALIST_ANALYSIS,
                        entity_id,
                        f"{specialist_type} analysis",
                        {"specialist_type": specialist_type, "result": entry},
                    )
                    await self._edge(run_node, analysis_node, ProvenanceRelationType.HAS_ANALYSIS)
                    if entry.get("claim_id") in claim_nodes:
                        await self._edge(
                            analysis_node,
                            claim_nodes[entry["claim_id"]],
                            ProvenanceRelationType.CONTRIBUTES_TO,
                        )
                    if entry.get("passage_id") in passages:
                        passage_node = await self._node(
                            ProvenanceNodeType.PASSAGE,
                            entry["passage_id"],
                            f"Passage {entry['passage_id']}",
                        )
                        await self._edge(
                            analysis_node, passage_node, ProvenanceRelationType.DERIVES_FROM
                        )
                    if entry.get("argument_id"):
                        argument = await self.session.get(ArgumentModel, entry["argument_id"])
                        if argument:
                            premises_result = await self.session.execute(
                                select(EvidenceLinkModel)
                                .join(PremiseModel, PremiseModel.id == EvidenceLinkModel.premise_id)
                                .where(PremiseModel.argument_id == argument.id)
                            )
                            for premise_link in premises_result.scalars().all():
                                if premise_link.passage_id in passages:
                                    passage_node = await self._node(
                                        ProvenanceNodeType.PASSAGE,
                                        premise_link.passage_id,
                                        f"Passage {premise_link.passage_id}",
                                    )
                                    await self._edge(
                                        analysis_node,
                                        passage_node,
                                        ProvenanceRelationType.DERIVES_FROM,
                                    )
        await self.session.commit()
        return run

    async def _graph_response(self) -> dict:
        return {
            "nodes": [self._node_payload(node) for node in self._touched_nodes.values()],
            "edges": [self._edge_payload(edge) for edge in self._touched_edges.values()],
        }

    async def trace_passage(self, passage_id: str) -> dict | None:
        result = await self.session.execute(
            select(PassageModel)
            .where(PassageModel.id == passage_id)
            .options(
                selectinload(PassageModel.document).selectinload(DocumentModel.source),
                selectinload(PassageModel.document_version).selectinload(DocumentVersionModel.pages),
                selectinload(PassageModel.page),
            )
        )
        passage = result.scalar_one_or_none()
        if passage is None:
            return None
        self._touched_nodes.clear()
        self._touched_edges.clear()
        await self._record_passage_ancestry(passage)
        await self.session.commit()
        return await self._graph_response()

    async def trace_claim(self, claim_id: str) -> dict | None:
        claim = await self.session.get(ClaimModel, claim_id)
        if claim is None:
            return None
        self._touched_nodes.clear()
        self._touched_edges.clear()
        await self._materialize_claim_records([claim])
        await self.session.commit()
        return await self._graph_response()

    async def _materialize_claim_records(self, claims: Iterable[ClaimModel]) -> None:
        claims = list(claims)
        claim_ids = [claim.id for claim in claims]
        evidence_result = await self.session.execute(
            select(EvidenceLinkModel).where(EvidenceLinkModel.claim_id.in_(claim_ids))
        ) if claim_ids else None
        evidence_links = evidence_result.scalars().all() if evidence_result else []
        passage_ids = {link.passage_id for link in evidence_links}
        passage_ids.update(claim.provenance_id for claim in claims if claim.provenance_id)
        passages_result = await self.session.execute(
            select(PassageModel)
            .where(PassageModel.id.in_(passage_ids))
            .options(
                selectinload(PassageModel.document).selectinload(DocumentModel.source),
                selectinload(PassageModel.document_version).selectinload(DocumentVersionModel.pages),
                selectinload(PassageModel.page),
            )
        ) if passage_ids else None
        passages = {passage.id: passage for passage in passages_result.scalars().all()} if passages_result else {}
        for passage in passages.values():
            await self._record_passage_ancestry(passage)
        claim_nodes = {}
        for claim in claims:
            claim_nodes[claim.id] = await self._node(
                ProvenanceNodeType.CLAIM,
                claim.id,
                claim.statement,
                {"claim_type": self._enum_value(claim.claim_type), "confidence": claim.confidence},
            )
        for link in evidence_links:
            evidence_node = await self._node(
                ProvenanceNodeType.EVIDENCE,
                link.id,
                f"Evidence {self._enum_value(link.relation_type)}",
                {"relation_type": self._enum_value(link.relation_type), "passage_id": link.passage_id},
            )
            claim_node = claim_nodes.get(link.claim_id)
            if claim_node:
                relation = ProvenanceRelationType(self._enum_value(link.relation_type))
                await self._edge(claim_node, evidence_node, ProvenanceRelationType.HAS_EVIDENCE)
                await self._edge(evidence_node, claim_node, relation)
            passage_node = await self._node(
                ProvenanceNodeType.PASSAGE,
                link.passage_id,
                f"Passage {link.passage_id}",
            )
            await self._edge(evidence_node, passage_node, ProvenanceRelationType.CITES)

    async def trace_run(self, run_id: str) -> list[dict]:
        """Return the compatible trace list with an additive typed graph."""
        run = await self._materialize_run(run_id)
        if run is None:
            return []
        graph = await self._graph_response()
        stmt = (
            select(EvidenceLinkModel)
            .join(ClaimModel, ClaimModel.id == EvidenceLinkModel.claim_id)
            .where(ClaimModel.research_run_id == run_id)
            .options(
                selectinload(EvidenceLinkModel.claim),
                selectinload(EvidenceLinkModel.passage)
                .selectinload(PassageModel.document)
                .selectinload(DocumentModel.source),
                selectinload(EvidenceLinkModel.passage).selectinload(PassageModel.document_version),
                selectinload(EvidenceLinkModel.passage).selectinload(PassageModel.page),
            )
            .order_by(EvidenceLinkModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        traces = []
        for link in result.scalars().all():
            passage = link.passage
            if passage is None or passage.document is None or passage.document.source is None:
                continue
            document = passage.document
            source = document.source
            traces.append(
                {
                    "evidence_link_id": link.id,
                    "claim_id": link.claim_id,
                    "premise_id": link.premise_id,
                    "relation_type": self._enum_value(link.relation_type),
                    "confidence_weight": link.confidence_weight,
                    "passage": {
                        "passage_id": passage.id,
                        "document_id": passage.document_id,
                        "document_version_id": passage.document_version_id,
                        "page_id": passage.page_id,
                        "page_number": passage.page_number,
                        "passage_order": passage.passage_order,
                        "content": passage.content,
                        "extraction_method": passage.extraction_method,
                        "section_heading": passage.section_heading,
                        "ocr_confidence": passage.ocr_confidence,
                        "extraction_uncertainty": passage.extraction_uncertainty,
                        "language": passage.language,
                    },
                    "document": {
                        "document_id": document.id,
                        "source_id": document.source_id,
                        "checksum_sha256": document.checksum_sha256,
                        "mime_type": document.mime_type,
                        "original_filename": document.original_filename,
                        "total_pages": document.total_pages,
                    },
                    "source": {
                        "source_id": source.id,
                        "title": source.title,
                        "author": source.author,
                        "historical_era": source.historical_era,
                        "original_language": source.original_language,
                        "source_type": self._enum_value(source.source_type),
                        "reference_url": source.reference_url,
                    },
                    "source_lineage": await self.trace_lineage(source.id),
                    "graph_nodes": graph["nodes"],
                    "graph_edges": graph["edges"],
                }
            )
        return traces

    async def trace_run_graph(self, run_id: str) -> dict | None:
        """Return the complete graph, including runs without evidence rows."""
        run = await self._materialize_run(run_id)
        if run is None:
            return None
        return await self._graph_response()

    async def trace_source_impact(
        self,
        source_id: str | None = None,
        document_id: str | None = None,
        passage_id: str | None = None,
    ) -> dict | None:
        """Find existing claims and runs depending on a source resource."""
        if not any((source_id, document_id, passage_id)):
            return None
        stmt = select(PassageModel).join(DocumentModel)
        if passage_id:
            stmt = stmt.where(PassageModel.id == passage_id)
        elif document_id:
            stmt = stmt.where(DocumentModel.id == document_id)
        else:
            stmt = stmt.where(DocumentModel.source_id == source_id)
        passage_result = await self.session.execute(stmt)
        passage_ids = [passage.id for passage in passage_result.scalars().all()]
        if not passage_ids:
            return None
        links_result = await self.session.execute(
            select(EvidenceLinkModel, ClaimModel)
            .join(ClaimModel, ClaimModel.id == EvidenceLinkModel.claim_id)
            .where(EvidenceLinkModel.passage_id.in_(passage_ids))
        )
        rows = links_result.all()
        claim_ids = sorted({claim.id for _, claim in rows})
        run_ids = sorted({claim.research_run_id for _, claim in rows if claim.research_run_id})
        return {"passage_ids": passage_ids, "claim_ids": claim_ids, "research_run_ids": run_ids}
