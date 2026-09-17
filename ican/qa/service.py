from __future__ import annotations

import asyncio
import re
from pathlib import Path

from ican.qa.paperqa_adapter import DisabledModel, prepare_evidence
from ican.qa.prompts import INSUFFICIENT
from ican.qa.runtime import ModelTimeout, OpenAICompatibleModel
from ican.qa.schema import Citation, QAConfig, QARequest, QAResponse, Usage
from ican.retrieval.schema import SearchRequest

CITATION_PATTERN = re.compile(r"\bpqac-[A-Za-z0-9_-]+\b")


class CapturedAnswerModel:
    """Keep original text before PaperQA2 removes its example citation ID."""

    def __init__(self, delegate):
        self.delegate = delegate
        self.raw_answer = ""
        self.calls = 0

    async def call_single(self, **kwargs):
        if self.calls or kwargs.get("name") != "answer":
            raise RuntimeError("Only one answer call is allowed")
        self.calls += 1
        result = await self.delegate.call_single(**kwargs)
        self.raw_answer = result.text or ""
        return result


class QAService:
    def __init__(
        self,
        root: Path,
        evidence_service,
        config: QAConfig | None = None,
        model_factory=None,
    ):
        self.root = root
        self.evidence_service = evidence_service
        self.config = config or QAConfig.model_validate_json(
            (root / "configs/qa/v1.json").read_text(encoding="utf-8")
        )
        self.model_factory = model_factory or (
            lambda: OpenAICompatibleModel(root, self.config)
        )

    async def answer(self, request: QARequest) -> QAResponse:
        search_request = SearchRequest.model_validate(request.model_dump())
        search_request.limit = min(search_request.limit, self.config.max_evidence)
        search = await asyncio.to_thread(self.evidence_service.search, search_request)
        prepared = await prepare_evidence(request.query, search.results, self.config)
        response = QAResponse(
            status="insufficient_evidence",
            answer="检索到的证据不足以回答，请补充材料或调整来源范围。",
            index_fingerprint=search.index_fingerprint,
            collection=search.collection,
            paperqa_version=self.config.paperqa_version,
            prompt_version=self.config.prompt_version,
            included_chunk_ids=[e.chunk_id for e in prepared.registry.values()],
            dropped_chunk_ids=prepared.dropped_chunk_ids,
        )
        if not prepared.registry:
            return response  # Missing model configuration cannot trigger a call here.
        model = self.model_factory()
        response.model = model.name
        captured = CapturedAnswerModel(model)
        try:
            session = await asyncio.wait_for(
                prepared.docs.aquery(
                    prepared.session,
                    settings=prepared.settings,
                    llm_model=captured,
                    summary_llm_model=DisabledModel(),
                    embedding_model=DisabledModel(),
                ),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError:
            raise ModelTimeout("Generation timed out") from None
        raw = captured.raw_answer
        counts = list(session.token_counts.values())
        response.usage = Usage(
            generation_calls=captured.calls,
            prompt_tokens=sum(x[0] for x in counts),
            completion_tokens=sum(x[1] for x in counts),
        )
        ids = list(dict.fromkeys(CITATION_PATTERN.findall(raw)))
        response.invalid_citation_ids = [
            cid for cid in ids if cid not in prepared.registry
        ]
        valid = [cid for cid in ids if cid in prepared.registry]
        response.citations = [
            Citation(number=i, context_id=cid, evidence=prepared.registry[cid])
            for i, cid in enumerate(valid, 1)
        ]
        numbers = {
            citation.context_id: citation.number for citation in response.citations
        }
        response.answer = CITATION_PATTERN.sub(
            lambda match: f"[{numbers[match[0]]}]" if match[0] in numbers else match[0],
            raw,
        )
        if response.invalid_citation_ids:
            response.status = "citation_invalid"
        elif INSUFFICIENT in raw:
            response.status = "insufficient_evidence"
            response.answer = response.answer.replace(
                INSUFFICIENT, "证据不足："
            ).strip()
        elif not valid:
            response.status = "citation_invalid"
        elif any(c.evidence.review_required for c in response.citations):
            response.status = "review_required"
        else:
            response.status = "answered"
        return response
