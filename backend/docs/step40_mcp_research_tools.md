# Step 40: MCP Research Tools

Step 40 registers the two research tools already present in the repository's
MCP history:

- `search_local_sources`: searches the indexed local corpus through the
  existing lexical, semantic, hybrid, and reranking services. Its optional
  `retrieval` value is `hybrid`, `lexical`, or `semantic`; `top_k` is limited
  to 1-20. Results retain passage, page, document, source, citation, and
  retrieval-score metadata.
- `trace_citation`: resolves a passage identifier through the existing
  `CitationService` and `ProvenanceService`. It returns the source-document-
  passage metadata, source lineage, and the existing typed provenance graph.

Both tools use closed JSON Schemas and return structured JSON. Empty citation
lookups return `traceable: false` and do not fabricate evidence. Retrieval and
provenance failures are handled by the Step 39 sanitized MCP error boundary.

The tools do not access arbitrary files, URLs, commands, credentials, or
user-owned research runs. The indexed source corpus is the same globally
readable corpus used by the existing search endpoint; no database migration is
required. The stdio entrypoint creates a fresh database session for each tool
invocation.

Focused verification from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_mcp_research_tools_step40_contracts.py backend/tests/integration/test_mcp_research_tools_step40.py backend/tests/integration/test_mcp_phase25.py -q
```
