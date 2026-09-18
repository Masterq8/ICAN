# P4.3 Research Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic claim-verification layer and auditable research screening, extraction, and Markdown reporting flow on the existing scoped evidence corpus.

**Architecture:** New `ican.research` modules validate typed claims against `AgentCorpus`, safely evaluate source-local Python assertions, append immutable revisions, and render reports. The existing PaperQA2 environment and FastAPI app delegate to the same service, so direct API use and Agent tools cannot produce different evidence states.

**Tech Stack:** Python 3.12, Pydantic v2, AST, Decimal, filelock, FastAPI, fixed PaperQA2/Aviary, pytest.

---

### Task 1: Claim contracts and deterministic verifier

**Files:**
- Create: `ican/research/__init__.py`
- Create: `ican/research/schema.py`
- Create: `ican/research/claims.py`
- Create: `tests/test_research_claims.py`

- [ ] **Step 1: Write failing claim tests**

```python
def test_even_grid_assert_blocks_execution_claim(corpus):
    verdict = verify_claim(corpus, ClaimDraft(
        statement="the next merge runs", kind="code_execution",
        evidence_ids=["merge"],
        conditions=[CodeCondition(chunk_id="merge", bindings={"H": 7, "W": 7})],
    ))
    assert verdict.status == "blocked_by_precondition"
    assert "H % 2 == 0" in verdict.conditions[0].expression
```

Run: `D:/CondaEnv/ican/python.exe -m pytest -q tests/test_research_claims.py`

- [ ] **Step 2: Implement strict schema and safe AST evaluation**

```python
class ClaimDraft(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)
    kind: Literal["verbatim", "numeric", "code_execution", "inference"]
    evidence_ids: list[str] = Field(min_length=1, max_length=8)

def evaluate_assert(expression: ast.expr, bindings: dict[str, Decimal]) -> bool:
    # recurse only over numeric literals, names, arithmetic, comparisons and BoolOp
    # raise ConditionUnsupported for calls, attributes, subscripts and unknown names
```

- [ ] **Step 3: Add negative and provenance tests**

```python
assert verify_claim(corpus, missing_quote).status == "insufficient_evidence"
assert verify_claim(corpus, inference).status == "requires_review"
assert verify_claim(corpus, bad_binding).status == "insufficient_evidence"
assert verify_claim(corpus, numeric).calculation.result == "0.002"
```

- [ ] **Step 4: Run scoped tests and commit**

Run: `D:/CondaEnv/ican/python.exe -m pytest -q tests/test_research_claims.py`

```powershell
git add ican/research tests/test_research_claims.py
git commit -m "feat(research): verify typed evidence claims"
```

### Task 2: Revision records and report renderer

**Files:**
- Create: `ican/research/store.py`
- Create: `ican/research/service.py`
- Create: `tests/test_research_service.py`

- [ ] **Step 1: Write failing revision and report tests**

```python
first = await service.submit_screening(request, screening)
second = await service.submit_screening(request, screening.model_copy(update={"revision_of": first.record_id}))
assert service.store.load(first.record_id).revision_of is None
assert service.store.load(second.record_id).revision_of == first.record_id
assert "blocked_by_precondition" in service.build_report([second.record_id]).markdown
```

- [ ] **Step 2: Implement append-only UUID records under the ignored research directory**

```python
def append(self, record: ResearchRecord) -> ResearchRecord:
    target = self.directory / f"{record.record_id}.json"
    with self.lock:
        if target.exists():
            raise ValueError("Research record ID already exists")
        target.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return record
```

- [ ] **Step 3: Implement submissions and deterministic Markdown output**

```python
def render_report(records: list[ResearchRecord]) -> str:
    # list subject, revision, fields/decision, verdict status, diagnostics and source location
    # never omit non-supported fields or invent cross-paper rankings
```

- [ ] **Step 4: Run scoped tests and commit**

Run: `D:/CondaEnv/ican/python.exe -m pytest -q tests/test_research_service.py`

```powershell
git add ican/research tests/test_research_service.py .gitignore
git commit -m "feat(research): store auditable screening and extraction revisions"
```

### Task 3: Agent business tools and FastAPI contracts

**Files:**
- Modify: `ican/agent/environment.py`
- Modify: `ican/agent/service.py`
- Modify: `ican/agent/prompts.py`
- Modify: `ican/api/app.py`
- Modify: `tests/test_agent_service.py`
- Modify: `tests/test_agent_api.py`
- Create: `tests/test_research_api.py`

- [ ] **Step 1: Write failing environment/API tests**

```python
result = await env.verify_claims([claim.model_dump()], state)
assert json.loads(result)["verdicts"][0]["status"] == "blocked_by_precondition"
assert TestClient(app).post("/v1/research/report", json={"record_ids": [record_id]}).status_code == 200
assert TestClient(app).post("/v1/research/report", json={"record_ids": ["../x"]}).status_code == 422
```

- [ ] **Step 2: Register four scoped tools and delegate through one service**

```python
for fn in [self.verify_claims, self.record_screening, self.record_extraction, self.build_research_report]:
    tools.append(Tool.from_function(fn, concurrency_safe=False))
```

Each tool accepts only evidence IDs already in `evidence_pool`; report creation only accepts IDs created by the service. Add planner instructions that non-supported verdicts cannot be stated as confirmed results.

- [ ] **Step 3: Add lazy research endpoints**

```python
@app.post("/v1/research/verify-claims", response_model=ClaimVerificationResponse)
def verify_claims(request: ClaimVerificationRequest):
    return get_research_service().verify(request)
```

Add equivalent screening, extraction and report endpoints. Preserve `/health` lazy behavior and map validation failures to 422.

- [ ] **Step 4: Run Agent/API tests and commit**

Run: `D:/CondaEnv/ican/python.exe -m pytest -q tests/test_agent_service.py tests/test_agent_api.py tests/test_research_api.py`

```powershell
git add ican/agent ican/api tests/test_agent_service.py tests/test_agent_api.py tests/test_research_api.py
git commit -m "feat(agent): add audited research workflow tools"
```

### Task 4: Delivery verification and documentation

**Files:**
- Modify: `docs/p4-agent-guide.md`
- Create: `docs/p4-research-guide.md`
- Modify: `docs/p4-agent-report.md`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `findings.md`
- Modify: `docs/requirements-spec.md`

- [ ] **Step 1: Document API requests and claim-status limits**

```json
{
  "scope": {"query": "Swin merge", "collection": "swin_v1"},
  "claims": [{"statement": "7x7 may merge", "kind": "code_execution", "evidence_ids": ["..."], "conditions": [{"chunk_id": "...", "bindings": {"H": 7, "W": 7}}]}]
}
```

State that no status proves unconstrained execution or free-form semantic entailment.

- [ ] **Step 2: Run final local verification**

Run: `D:/CondaEnv/ican/python.exe -m pytest -q`

Run: `D:/CondaEnv/ican/python.exe -m ruff check ican/research ican/agent ican/api tests/test_research_claims.py tests/test_research_service.py tests/test_research_api.py`

Run: `D:/CondaEnv/ican/python.exe -m ruff format --check ican/research ican/agent ican/api tests/test_research_claims.py tests/test_research_service.py tests/test_research_api.py`

- [ ] **Step 3: Verify immutable inputs and credentials before final commit**

```powershell
git -c core.whitespace=cr-at-eol diff --check
git status --short
```

Verify the existing protected ledger and frozen Swin test SHA with a local hash script. Scan staged files for credential-like patterns without printing contents.

- [ ] **Step 4: Commit final documentation**

```powershell
git add docs task_plan.md progress.md findings.md
git commit -m "docs(research): record P4.3 verification delivery"
```
