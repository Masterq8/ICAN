from __future__ import annotations

import asyncio
import json
import re

from aviary.core import Tool
from paperqa import Docs, Settings
from paperqa.agents.env import PaperQAEnvironment
from paperqa.agents.tools import Complete, EnvironmentState

from ican.qa.paperqa_adapter import DisabledModel, context_id, prepare_evidence
from ican.qa.prompts import INSUFFICIENT
from ican.qa.runtime import ModelTimeout, ModelUnavailable
from ican.qa.schema import Citation, QAConfig, QAResponse, Usage
from ican.qa.service import CITATION_PATTERN, CapturedAnswerModel

from .calculation import calculate as arithmetic
from .configuration import trace_config as configuration_trace
from .prompts import ANSWER_EXTENSION
from .runtime import AgentAnswerModel
from .schema import ToolInputError


class DomainEnvironment(PaperQAEnvironment):
    def __init__(self, corpus, request, runtime, config):
        super().__init__(
            query=request.query,
            settings=Settings(parsing={"defer_embedding": True}),
            docs=Docs(),
            llm_model=DisabledModel(),
            summary_llm_model=DisabledModel(),
            embedding_model=DisabledModel(),
        )
        self.corpus, self.request, self.runtime, self.config = (
            corpus,
            request,
            runtime,
            config,
        )
        self.evidence_pool = {}
        self.artifacts = []
        self.answer_response = None
        self.raw_answer = None
        self.answer_attempted = False
        self.fatal_error = None
        self.answer_error = None

    def make_tools(self):
        tools = [
            Tool.from_function(fn, concurrency_safe=False)
            for fn in [
                self.search_evidence,
                self.read_evidence,
                self.trace_config,
                self.calculate,
                self.gen_answer,
                self.complete,
            ]
        ]
        return tools

    def retain(self, items):
        for item in items:
            original = self.corpus.evidence(item.chunk_id)
            if (
                original.text != item.text
                or original.source != item.source
                or original.review_required != item.review_required
            ):
                self.fatal_error = "evidence_identity_changed"
                raise ToolInputError(
                    "Retrieved evidence differs from the verified corpus"
                )
            if (
                item.chunk_id not in self.evidence_pool
                and len(self.evidence_pool) >= self.config.max_evidence_pool
            ):
                break
            self.evidence_pool[item.chunk_id] = item

    def preview(self, items):
        return [
            {
                "chunk_id": e.chunk_id,
                "context_id": context_id(e.chunk_id),
                "source": e.source.model_dump(),
                "text": e.text[:1800],
                "preview_truncated": len(e.text) > 1800,
                "review_required": e.review_required,
            }
            for e in items
            if e.chunk_id in self.evidence_pool
        ]

    async def search_evidence(
        self,
        query: str,
        source_types: list[str],
        strategy: str,
        state: EnvironmentState,
    ) -> str:
        """Search verified evidence within the user's fixed scope.

        Args:
            query: Specific question or code symbols to search.
            source_types: Narrow to paper, code, config or documentation; empty retains the user scope.
            strategy: dense, dense_scoped, bm25, hybrid or hybrid_rerank.
            state: PaperQA2 task state.
        """
        request = self.corpus.search_request(query, source_types, strategy)
        if request is None:
            return json.dumps(
                {"evidence": [], "reason": "Source type intersection is empty"}
            )
        response = await asyncio.to_thread(self.corpus.service.search, request)
        if response.index_fingerprint != self.corpus.fingerprint:
            self.fatal_error = "index_fingerprint_changed"
            raise ToolInputError("Index fingerprint changed during this task")
        items = [
            e
            for e in response.results
            if self.corpus.allowed(self.corpus.registry[e.chunk_id])
        ]
        self.retain(items)
        return json.dumps(
            {
                "evidence": self.preview(items),
                "strategy": strategy,
                "family": self.corpus.family,
            },
            ensure_ascii=False,
        )

    async def read_evidence(
        self, chunk_id: str, structure: str, source_path: str, state: EnvironmentState
    ) -> str:
        """Read original fragments by ID or exact class/function structure.

        Args:
            chunk_id: Known original chunk ID, or empty to use structure.
            structure: Exact structure such as PatchMerging.forward; ignored when an ID is supplied.
            source_path: Exact source path to narrow structure lookup, or empty.
            state: PaperQA2 task state.
        """
        items = self.corpus.read(chunk_id, structure, source_path)
        self.retain(items)
        return json.dumps({"evidence": self.preview(items)}, ensure_ascii=False)

    async def trace_config(
        self,
        config_path: str,
        field: str,
        opts: list[str],
        cli: dict,
        state: EnvironmentState,
    ) -> str:
        """Statically trace an exact Swin configuration field, including BASE and overrides.

        Args:
            config_path: Exact eligible YAML path or filename; empty reads only defaults.
            field: Exact dotted field such as MODEL.DROP_PATH_RATE or MODEL.SWIN.PATCH_NORM.
            opts: User-provided alternating field/value strings; empty if none supplied.
            cli: User-provided CLI values such as accumulation_steps; empty if none supplied.
            state: PaperQA2 task state.
        """
        supplied = self.request.user_overrides
        if opts != supplied.opts or json.dumps(cli, sort_keys=True) != json.dumps(
            supplied.cli, sort_keys=True
        ):
            raise ToolInputError(
                "Overrides must match the structured user_overrides request; planner guesses are not user arguments"
            )
        artifact, items = await asyncio.to_thread(
            configuration_trace,
            self.corpus,
            config_path,
            field,
            opts,
            cli,
            user_arguments_verified=True,
        )
        self.retain(items)
        self.artifacts.append(artifact)
        return json.dumps(
            {"artifact": artifact, "evidence": self.preview(items)}, ensure_ascii=False
        )

    async def calculate(
        self, expression: str, evidence_ids: list[str], state: EnvironmentState
    ) -> str:
        """Compute bounded literal arithmetic from user values or original evidence.

        Supports +, -, *, /, bounded integer powers, integer-only // and %.
        The expression must produce one scalar number, never a tuple or list.

        Args:
            expression: Literal arithmetic using +, -, *, / or small integer powers.
            evidence_ids: IDs supporting parameters; empty means parameters were supplied by the user.
            state: PaperQA2 task state.
        """
        if len(evidence_ids) > 8 or any(
            cid not in self.evidence_pool for cid in evidence_ids
        ):
            raise ToolInputError(
                "Calculation references must already be in the evidence pool"
            )
        artifact = {
            "kind": "calculation",
            "expression": expression,
            "result": arithmetic(expression),
            "chunk_ids": evidence_ids,
            "parameter_origin": "evidence_and_user"
            if evidence_ids
            else "user_provided_claim_requires_review",
        }
        self.artifacts.append(artifact)
        return json.dumps(artifact, ensure_ascii=False)

    async def gen_answer(self, evidence_ids: list[str], state: EnvironmentState) -> str:
        """Generate the final cited answer once from chosen original evidence and tool results.

        Args:
            evidence_ids: At most eight unique IDs from the current pool, ordered by necessity.
            state: PaperQA2 task state.
        """
        if self.answer_attempted:
            raise ToolInputError(
                "An answer has already been attempted; no automatic retry"
            )
        if (
            len(evidence_ids) > 8
            or len(set(evidence_ids)) != len(evidence_ids)
            or any(cid not in self.evidence_pool for cid in evidence_ids)
        ):
            raise ToolInputError(
                "Choose at most eight unique IDs from the evidence pool"
            )
        self.answer_attempted = True
        selected = [
            self.evidence_pool[cid].model_copy(update={"rank": i})
            for i, cid in enumerate(evidence_ids, 1)
        ]
        prepared = await prepare_evidence(self.request.query, selected, QAConfig())
        prepared.session.tool_history = [
            list(turn) for turn in state.session.tool_history
        ]
        prepared.settings.prompts.system += ANSWER_EXTENSION
        original_serializer = prepared.settings.custom_context_serializer
        allowed = {e.chunk_id for e in prepared.registry.values()}
        artifacts = []
        for artifact in self.artifacts:
            references = artifact.get("chunk_ids", []) + [
                cid
                for step in artifact.get("chain", [])
                for cid in step.get("chunk_ids", [])
            ]
            if all(cid in allowed for cid in references):
                artifacts.append(artifact)

        async def serializer(settings, contexts, question, pre_str=None):
            text = await original_serializer(
                settings=settings, contexts=contexts, question=question, pre_str=pre_str
            )
            return (
                text
                + "\n<tool_results>\n"
                + json.dumps(artifacts, ensure_ascii=False)
                + "\n</tool_results>"
            )

        prepared.settings.custom_context_serializer = serializer
        response = QAResponse(
            status="insufficient_evidence",
            answer="证据不足，无法完成本次核查。",
            index_fingerprint=self.corpus.fingerprint,
            collection=self.request.collection,
            paperqa_version="2026.8.12",
            prompt_version="p4-tools-evidence-v1",
            model=self.runtime.config.answer_model,
            included_chunk_ids=[e.chunk_id for e in prepared.registry.values()],
            dropped_chunk_ids=prepared.dropped_chunk_ids,
        )
        if prepared.registry:
            captured = CapturedAnswerModel(AgentAnswerModel(self.runtime))
            try:
                session = await prepared.docs.aquery(
                    prepared.session,
                    settings=prepared.settings,
                    llm_model=captured,
                    summary_llm_model=DisabledModel(),
                    embedding_model=DisabledModel(),
                )
            except (ModelTimeout, ModelUnavailable) as error:
                self.answer_error = error
                raise
            raw = captured.raw_answer
            self.raw_answer = raw
            ids = list(dict.fromkeys(CITATION_PATTERN.findall(raw)))
            response.invalid_citation_ids = [
                cid for cid in ids if cid not in prepared.registry
            ]
            response.citations = [
                Citation(number=i, context_id=cid, evidence=prepared.registry[cid])
                for i, cid in enumerate(
                    [cid for cid in ids if cid in prepared.registry], 1
                )
            ]
            numbers = {c.context_id: c.number for c in response.citations}
            response.answer = CITATION_PATTERN.sub(
                lambda match: (
                    f"[{numbers[match[0]]}]" if match[0] in numbers else match[0]
                ),
                raw,
            )
            counts = list(session.token_counts.values())
            response.usage = Usage(
                generation_calls=captured.calls,
                prompt_tokens=sum(c[0] for c in counts),
                completion_tokens=sum(c[1] for c in counts),
            )
            if response.invalid_citation_ids:
                response.status = "citation_invalid"
            elif INSUFFICIENT in raw or re.match(
                r"\s*(?:I cannot answer|I can't answer|无法回答|证据不足)",
                raw,
                re.IGNORECASE,
            ):
                response.status = "insufficient_evidence"
            elif not response.citations:
                response.status = "citation_invalid"
            elif any(c.evidence.review_required for c in response.citations):
                response.status = "review_required"
            else:
                response.status = "answered"
            state.docs, state.session = prepared.docs, session
        self.answer_response = response
        return json.dumps(
            {
                "status": response.status,
                "answer": response.answer,
                "used_chunk_ids": response.included_chunk_ids,
            },
            ensure_ascii=False,
        )

    async def complete(
        self, has_successful_answer: bool, state: EnvironmentState
    ) -> str:
        """Complete only after a real cited answer has been generated.

        Args:
            has_successful_answer: Planner's assessment, checked against the actual answer status.
            state: PaperQA2 task state.
        """
        if self.answer_response is None:
            raise ToolInputError("No actual answer exists to complete")
        actual = self.answer_response.status == "answered"
        await Complete().complete(
            has_successful_answer=has_successful_answer and actual, state=state
        )
        return json.dumps(
            {"completed": True, "answer_status": self.answer_response.status}
        )
