# Step 17: Web Research Acquisition

The authenticated endpoints are:

- `POST /api/v1/web/search` with `{ "query": "...", "max_results": 5 }`.
- `POST /api/v1/web/acquire` with `{ "url": "https://...", "source_title": "..." }`.

Search results are discovery candidates. Their search-engine rank is retained
for reproducibility but is not an evidence-quality or authority label. Acquired
responses are archived as raw bytes through the normal immutable,
SHA-256-addressed storage path, then passed to ordinary document ingestion and
provenance assembly.

The fetcher canonicalizes URLs, rejects credentials and private/reserved
destinations (including redirect destinations), observes `robots.txt` by
default, applies timeout and response-size limits, accepts only HTML/XHTML or
plain text, and records selected response headers and acquisition timestamps.
Successful fetches are cached under `CACHE_LOCAL_ROOT` using a SHA-256 key for
the canonical URL. Failed fetches are never cached. The original response is
never replaced by extracted text.

Run the focused suite from the repository root with:

```powershell
$env:RUNTIME_PROFILE='test'; $env:AUTH_MODE='test'; .\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_web_acquisition_phase17.py backend/tests/unit/test_web_security.py backend/tests/unit/test_web_acquisition_step17.py -q
```
