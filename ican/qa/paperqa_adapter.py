from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from importlib.metadata import version

# Avoid LiteLLM fetching its cost map on import. No provider pricing is inferred.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

from paperqa import Context, Doc, Docs, PQASession, Settings, Text

from ican.qa.prompts import QA, SYSTEM
from ican.qa.schema import QAConfig
from ican.retrieval.schema import EvidenceResult


def context_id(chunk_id: str) -> str:
    return "pqac-" + hashlib.sha256(chunk_id.encode()).hexdigest()[:8]


class DisabledModel:
    async def call_single(self, **kwargs):
        raise RuntimeError("Summary calls are disabled")

    async def embed_documents(self, *args, **kwargs):
        raise RuntimeError("Implicit embeddings are disabled")


@dataclass
class PreparedEvidence:
    docs: Docs
    session: PQASession
    settings: Settings
    registry: dict[str, EvidenceResult]
    dropped_chunk_ids: list[str]


async def prepare_evidence(
    question: str, evidence: list[EvidenceResult], config: QAConfig
) -> PreparedEvidence:
    if version("paper-qa") != config.paperqa_version:
        raise RuntimeError("Unexpected PaperQA2 version")
    docs = Docs()
    registry: dict[str, EvidenceResult] = {}
    contexts = []
    dropped = []
    characters = 0
    budget_exhausted = False
    settings = Settings(
        parsing={"defer_embedding": True},
        answer={
            "get_evidence_if_no_contexts": False,
            "answer_max_sources": config.max_evidence,
        },
        prompts={
            "system": SYSTEM,
            "qa": QA,
            "pre": None,
            "post": None,
            "answer_iteration_prompt": None,
        },
    )
    for item in evidence:
        if (
            budget_exhausted
            or len(contexts) >= config.max_evidence
            or characters + len(item.text) > config.max_context_chars
        ):
            budget_exhausted = True
            dropped.append(item.chunk_id)
            continue
        cid = context_id(item.chunk_id)
        if cid in registry:
            raise ValueError("Context ID collision or duplicate chunk")
        registry[cid] = item
        doc = Doc(
            docname="chunk-" + item.chunk_id,
            dockey=item.chunk_id,
            citation=f"{item.source.source_path} @ {item.source.source_version}",
        )
        text = Text(
            text=item.text,
            name=cid,
            doc=doc,
            chunk_id=item.chunk_id,
            review_required=item.review_required,
        )
        await docs.aadd_texts([text], doc, settings=settings)
        contexts.append(
            Context(id=cid, context=item.text, text=text, question=question, score=1)
        )
        characters += len(item.text)

    async def serializer(settings, contexts, question, pre_str=None):
        # Registry metadata is kept outside hashable upstream Text objects.
        blocks = []
        for context in contexts:
            item = registry[context.id]
            metadata = {
                "source": item.source.model_dump(),
                "rank": item.rank,
                "retrieval_score": item.score,
                "review_required": item.review_required,
            }
            blocks.append(
                f"[{context.id}]\n{json.dumps(metadata, ensure_ascii=False)}\n"
                f"<evidence>\n{item.text}\n</evidence>"
            )
        return "\n\n".join(blocks)

    settings.custom_context_serializer = serializer
    return PreparedEvidence(
        docs,
        PQASession(question=question, contexts=contexts),
        settings,
        registry,
        dropped,
    )
