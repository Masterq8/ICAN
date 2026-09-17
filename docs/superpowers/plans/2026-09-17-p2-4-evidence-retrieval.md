# P2.4 Evidence Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the verified BGE-M3/Qdrant index through a FastAPI endpoint that returns only source-locatable evidence, with collection, source-type, and safe source-path filters.

**Architecture:** Add a small `ican.retrieval` package. Its service owns one closed-after-use local Qdrant client operation and a fixed `DenseEncoder`; the API layer translates Pydantic request/response objects and controlled service exceptions to HTTP responses. The app factory accepts dependency overrides so most tests use fake encoder/Qdrant adapters; one opt-in integration command uses the published P2.3 index.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, Qdrant Client, Sentence Transformers BGE-M3, pytest, FastAPI TestClient.

---

### Task 1: Define retrieval contracts and pure filter validation

**Files:**
- Create: `ican/retrieval/__init__.py`
- Create: `ican/retrieval/schema.py`
- Create: `tests/test_retrieval_schema.py`

- [x] **Step 1: Write failing contract tests**

```python
def test_search_request_normalizes_and_accepts_safe_filters():
    request = SearchRequest(
        query="  Swin-T window size  ",
        collection="swin_v1",
        filters=SearchFilters(source_types=["config"], path_prefixes=["data/raw/repositories/Swin-Transformer/configs/swin/"]),
    )
    assert request.query == "Swin-T window size"


@pytest.mark.parametrize("prefix", ["../x", "C:/x", "\\\\server\\x", "configs\\swin", ""])
def test_search_filters_reject_unsafe_path_prefix(prefix):
    with pytest.raises(ValidationError):
        SearchFilters(path_prefixes=[prefix])
```

- [x] **Step 2: Run the failing test**

Run: `D:/CondaEnv/ican/python.exe -m pytest tests/test_retrieval_schema.py -q`

Expected: FAIL because `ican.retrieval.schema` does not exist.

- [x] **Step 3: Implement explicit Pydantic request and evidence response models**

```python
SourceType = Literal["paper", "code", "config", "documentation"]

class SearchFilters(BaseModel):
    source_types: list[SourceType] | None = None
    path_prefixes: list[str] | None = None

    @field_validator("path_prefixes")
    @classmethod
    def safe_prefixes(cls, prefixes):
        for prefix in prefixes or []:
            if not prefix or "\\" in prefix or prefix.startswith("/") or ":" in prefix or ".." in Path(prefix).parts:
                raise ValueError("path prefix must be a nonempty relative POSIX path")
        return prefixes
```

Define `SearchRequest` (`query` strips whitespace, 1–4096 chars; `limit` 1–20 default 5), `EvidenceSource`, `EvidenceResult`, and `SearchResponse`. Do not add fields for generated answer, rationale, prompt, chain of thought, or score transformations.

- [x] **Step 4: Run schema tests**

Run: `D:/CondaEnv/ican/python.exe -m pytest tests/test_retrieval_schema.py -q`

Expected: PASS.

- [x] **Step 5: Commit contract work**

```powershell
git add ican/retrieval/__init__.py ican/retrieval/schema.py tests/test_retrieval_schema.py
git commit -m "Add evidence retrieval API contracts"
```

### Task 2: Implement verified index discovery, Qdrant filtering, and evidence mapping

**Files:**
- Create: `ican/retrieval/service.py`
- Create: `tests/test_retrieval_service.py`
- Reuse: `ican/indexing/model.py`, `ican/indexing/pipeline.py`, `ican/indexing/verification.py`, `configs/indexing/v1.json`

- [x] **Step 1: Write failing service tests using fake encoder and Qdrant adapter**

```python
def test_service_maps_path_and_source_type_filters_to_qdrant(tmp_path):
    service = EvidenceSearchService(tmp_path, config(), encoder=FakeEncoder(), client_factory=FakeClient)
    response = service.search(SearchRequest(
        query="window size", collection="swin_v1",
        filters=SearchFilters(source_types=["config"], path_prefixes=["configs/swin/"]),
    ))
    assert response.results[0].source.source_path.startswith("configs/swin/")
    assert service.client.last_filter == expected_filter


def test_service_rejects_unknown_collection_before_encoding(tmp_path):
    with pytest.raises(CollectionNotFound):
        EvidenceSearchService(tmp_path, config(), encoder=FailIfCalledEncoder(), client_factory=FakeClient).search(
            SearchRequest(query="x", collection="not_real")
        )
```

- [x] **Step 2: Run the failing service tests**

Run: `D:/CondaEnv/ican/python.exe -m pytest tests/test_retrieval_service.py -q`

Expected: FAIL because the service is absent.

- [x] **Step 3: Implement the bounded service**

`EvidenceSearchService` must:

1. Parse `configs/indexing/v1.json` with `IndexConfig`, verify the model ledger with `verified_model`, derive the immutable index directory through `index_identity` and `index_directory`, and check `index_manifest.json` status before serving.
2. Obtain known collection names from the manifest and reject unknown names before query encoding.
3. Load `DenseEncoder` only after structural checks; encode the raw request query once.
4. Build `models.Filter` with a `chunk.source_type` `MatchAny` condition and one `MatchText`/prefix-compatible condition per approved Qdrant local API. If Qdrant does not support safe prefix matching, fetch a bounded `limit * 20` candidate set with source-type filter, filter `chunk.source_path.startswith(prefix)` in Python, then return at most `limit`; record this deliberate local-filter fallback in the service docstring and response log.
5. Use `query_points` with `with_payload=True`, `with_vectors=False`; map only `chunk_id`, `text`, `review_required`, `source_id`, `source_type`, `source_path`, `source_version`, `location`, and score into response objects.
6. Close local Qdrant clients with `contextlib.closing`; do not retain a database handle across requests.
7. Raise `IndexUnavailable` for missing/corrupt index or model identity failure, and `CollectionNotFound` for invalid collection.

Use `time.perf_counter()` and `uuid.uuid4()` to produce a request log record with request ID, index fingerprint, collection, filters, result count and elapsed milliseconds. Log no query text, evidence text, vector, filesystem absolute path, credentials, model prompt, or generated content.

- [x] **Step 4: Run service tests**

Run: `D:/CondaEnv/ican/python.exe -m pytest tests/test_retrieval_service.py -q`

Expected: PASS.

- [x] **Step 5: Commit service work**

```powershell
git add ican/retrieval/service.py tests/test_retrieval_service.py
git commit -m "Add filtered Qdrant evidence retrieval service"
```

### Task 3: Add FastAPI application factory and HTTP behavior tests

**Files:**
- Create: `ican/api/__init__.py`
- Create: `ican/api/app.py`
- Create: `tests/test_retrieval_api.py`
- Create: `scripts/serve_api.py`

- [x] **Step 1: Write failing API tests with a fake dependency**

```python
def test_search_route_returns_evidence_only():
    app = create_app(service=FakeEvidenceService())
    response = TestClient(app).post("/v1/evidence/search", json={"query": "window", "collection": "swin_v1"})
    assert response.status_code == 200
    assert set(response.json()["results"][0]) == {"rank", "score", "chunk_id", "text", "review_required", "source"}


def test_search_route_maps_unavailable_index_to_503():
    app = create_app(service=UnavailableEvidenceService())
    assert TestClient(app).post("/v1/evidence/search", json={"query": "x", "collection": "swin_v1"}).status_code == 503
```

- [x] **Step 2: Run the failing API tests**

Run: `D:/CondaEnv/ican/python.exe -m pytest tests/test_retrieval_api.py -q`

Expected: FAIL because the application factory is absent.

- [x] **Step 3: Implement app factory and CLI server entrypoint**

```python
def create_app(root: Path | None = None, service: EvidenceSearchService | None = None) -> FastAPI:
    app = FastAPI(title="复现有据 Evidence API", version="0.1")
    evidence = service or EvidenceSearchService(root or ROOT, load_config(root or ROOT))

    @app.post("/v1/evidence/search", response_model=SearchResponse)
    def search(request: SearchRequest) -> SearchResponse:
        try:
            return evidence.search(request)
        except CollectionNotFound as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except IndexUnavailable:
            raise HTTPException(status_code=503, detail="Evidence index is unavailable")
```

Keep FastAPI validation failures at 422. Add `GET /health` that reports `{"status": "ok"}` without opening Qdrant or loading BGE-M3. `scripts/serve_api.py` must invoke uvicorn for one worker only and document that local Qdrant cannot serve multiple workers.

- [x] **Step 4: Run API tests**

Run: `D:/CondaEnv/ican/python.exe -m pytest tests/test_retrieval_api.py -q`

Expected: PASS.

- [x] **Step 5: Commit API work**

```powershell
git add ican/api/__init__.py ican/api/app.py scripts/serve_api.py tests/test_retrieval_api.py
git commit -m "Expose evidence retrieval through FastAPI"
```

### Task 4: Execute published-index integration check and document P2.4

**Files:**
- Create: `scripts/verify_retrieval_api.py`
- Create: `docs/p2-retrieval-guide.md`
- Modify: `README.md`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `findings.md`
- Modify: `docs/problem-solution-log.md`

- [x] **Step 1: Add a real-index verification command**

The script must call the service against `configs/indexing/v1.json`, then assert:

```python
unrestricted = search("Swin-T 的窗口大小配置是多少？", "swin_v1", ["config"], None)
restricted = search("Swin-T 的窗口大小配置是多少？", "swin_v1", ["config"], ["data/raw/repositories/Swin-Transformer/configs/swin/"])
assert unrestricted.results
assert restricted.results
assert all(item.source.source_path.startswith("configs/swin/") for item in restricted.results)
```

Save only count, filter values, returned relative paths, rank, score, chunk ID, source version and location to a versioned `retrieval_smoke.json`; do not save the frozen answer or label results as correct.

- [x] **Step 2: Run targeted, full, and integration verification**

Run:

```powershell
D:/CondaEnv/ican/python.exe -m pytest tests/test_retrieval_schema.py tests/test_retrieval_service.py tests/test_retrieval_api.py -q
D:/CondaEnv/ican/python.exe scripts/verify_retrieval_api.py
D:/CondaEnv/ican/python.exe -m pytest tests -q
D:/CondaEnv/ican/python.exe -m ruff check ican/retrieval ican/api scripts/serve_api.py scripts/verify_retrieval_api.py tests/test_retrieval_schema.py tests/test_retrieval_service.py tests/test_retrieval_api.py
D:/CondaEnv/ican/python.exe -m ruff format --check ican/retrieval ican/api scripts/serve_api.py scripts/verify_retrieval_api.py tests/test_retrieval_schema.py tests/test_retrieval_service.py tests/test_retrieval_api.py
```

Expected: all retrieval tests pass; integration reports paths restricted to `data/raw/repositories/Swin-Transformer/configs/swin/`; existing test count does not regress; generated data stays within the ignored immutable index directory.

- [x] **Step 3: Write the operational guide and update project records**

Document endpoint examples, single-worker local-Qdrant limit, fields returned, filters, error responses, version selection, smoke result limitation, and boundary before P2.5. Mark P2.4 complete only if integration and full tests pass; record any variant-retrieval failure in the problem log instead of hiding it.

- [x] **Step 4: Commit documentation and verification**

```powershell
git add scripts/verify_retrieval_api.py docs/p2-retrieval-guide.md README.md task_plan.md progress.md findings.md docs/problem-solution-log.md
git commit -m "Document and verify P2.4 evidence retrieval"
```

## Plan self-review

- Spec coverage: Tasks 1–3 implement contract, safe filters, FastAPI errors, locatable payloads and logging; Task 4 validates the real immutable index and updates user documentation.
- Scope: no Agent planning, answer generation, PaperQA2, reranking, BM25, UI or multi-worker deployment is included.
- Type consistency: every route uses `SearchRequest` and `SearchResponse`; all service errors are defined in Task 2 and mapped in Task 3.
- Placeholder scan: no deferred implementation steps or undefined files remain.

## Execution result (2026-09-17)

All four tasks completed. Real FastAPI validation used the immutable 3,959-point index and proved the Swin configuration path constraint. Targeted retrieval tests: 22 passed. Full suite: 101 passed, 1 skipped (Windows symbolic-link permission), with one third-party TestClient deprecation warning. P2.4 contains no Agent planning or generated answers.
