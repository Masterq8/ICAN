"""Scoped claim verification, research revisions, and deterministic reports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ican.agent.corpus import AgentCorpus
from ican.agent.schema import ToolInputError

from .claims import verify_claim
from .schema import (
    ClaimDraft,
    ClaimVerificationResponse,
    ExtractionDraft,
    ResearchRecord,
    ResearchReport,
    ResearchReportRequest,
    ScreeningDraft,
    VerifiedExtractionField,
)
from .store import ResearchStore


class ResearchService:
    def __init__(
        self,
        root: Path,
        index_config,
        evidence_service,
        *,
        corpus_factory=AgentCorpus,
        store: ResearchStore | None = None,
    ):
        self.root = Path(root)
        self.index_config = index_config
        self.evidence_service = evidence_service
        self.corpus_factory = corpus_factory
        self.store = store or ResearchStore(
            self.root / "data/processed/research/p4-v1/records"
        )

    def corpus(self, request):
        return self.corpus_factory(
            self.root, self.index_config, self.evidence_service, request
        )

    def verify_with_corpus(self, corpus, claims: list[ClaimDraft], *, allowed_ids=None):
        return ClaimVerificationResponse(
            verdicts=[
                verify_claim(corpus, claim, allowed_ids=allowed_ids) for claim in claims
            ]
        )

    def verify(self, request, claims: list[ClaimDraft]):
        return self.verify_with_corpus(self.corpus(request), claims)

    @staticmethod
    def _subject_is_cited(subject_source_id, verdicts):
        if subject_source_id not in {
            evidence.source.source_id
            for verdict in verdicts
            for evidence in verdict.evidence
        }:
            raise ToolInputError("Subject source ID must occur in submitted evidence")

    def _validate_revision(self, record_type, subject_source_id, revision_of):
        if revision_of is None:
            return None
        try:
            previous = self.store.load(revision_of)
        except ToolInputError as error:
            raise ToolInputError("Research revision is absent") from error
        if (
            previous.record_type != record_type
            or previous.subject_source_id != subject_source_id
        ):
            raise ToolInputError(
                "Research revision must retain record type and subject"
            )
        return previous

    def submit_screening(
        self,
        request,
        draft: ScreeningDraft,
        *,
        corpus=None,
        allowed_ids=None,
        card_id=None,
    ):
        corpus = corpus or self.corpus(request)
        verdicts = self.verify_with_corpus(
            corpus, draft.claims, allowed_ids=allowed_ids
        ).verdicts
        self._subject_is_cited(draft.subject_source_id, verdicts)
        previous = self._validate_revision(
            "screening", draft.subject_source_id, draft.revision_of
        )
        if previous is not None:
            if card_id is not None and previous.card_id != card_id:
                raise ToolInputError("Research revision must retain card identity")
            card_id = previous.card_id
        return self.store.append(
            ResearchRecord(
                record_id=uuid4(),
                card_id=card_id,
                created_at=datetime.now(timezone.utc),
                record_type="screening",
                subject_source_id=draft.subject_source_id,
                revision_of=draft.revision_of,
                decision=draft.decision,
                claims=verdicts,
            )
        )

    def submit_extraction(
        self,
        request,
        draft: ExtractionDraft,
        *,
        corpus=None,
        allowed_ids=None,
        card_id=None,
    ):
        corpus = corpus or self.corpus(request)
        fields = []
        all_verdicts = []
        for field in draft.fields:
            verdicts = self.verify_with_corpus(
                corpus, field.claims, allowed_ids=allowed_ids
            ).verdicts
            all_verdicts.extend(verdicts)
            fields.append(
                VerifiedExtractionField(
                    name=field.name, value=field.value, claims=verdicts
                )
            )
        self._subject_is_cited(draft.subject_source_id, all_verdicts)
        previous = self._validate_revision(
            "extraction", draft.subject_source_id, draft.revision_of
        )
        if previous is not None:
            if card_id is not None and previous.card_id != card_id:
                raise ToolInputError("Research revision must retain card identity")
            card_id = previous.card_id
        return self.store.append(
            ResearchRecord(
                record_id=uuid4(),
                card_id=card_id,
                created_at=datetime.now(timezone.utc),
                record_type="extraction",
                subject_source_id=draft.subject_source_id,
                revision_of=draft.revision_of,
                fields=fields,
            )
        )

    @staticmethod
    def _location(evidence):
        location = evidence.source.location
        if "line_start" in location:
            return f"{evidence.source.source_path}:{location['line_start']}"
        if "page" in location:
            return f"{evidence.source.source_path}:p.{location['page']}"
        if "section_index" in location:
            section = int(location["section_index"]) + 1
            paragraph = location.get("paragraph_index")
            suffix = f"§{section}"
            if paragraph is not None:
                suffix += f"¶{int(paragraph) + 1}"
            return f"{evidence.source.source_path}:{suffix}"
        return evidence.source.source_path

    @classmethod
    def _render_verdict(cls, verdict):
        lines = [f"- 状态：`{verdict.status}`；结论：{verdict.claim.statement}"]
        for evidence in verdict.evidence:
            lines.append(
                f"  - 证据：`{evidence.chunk_id}`（{cls._location(evidence)}）"
            )
        for condition in verdict.conditions:
            evidence = next(
                item for item in verdict.evidence if item.chunk_id == condition.chunk_id
            )
            location = (
                f"（{evidence.source.source_path}:{condition.line}）"
                if condition.line is not None
                else ""
            )
            lines.append(
                f"  - 条件：`{condition.expression}` → `{condition.status}`{location}"
            )
        if verdict.calculation:
            lines.append(
                f"  - 计算：`{verdict.calculation.expression}` = `{verdict.calculation.result}`"
            )
        lines.extend(f"  - 说明：{item}" for item in verdict.diagnostics)
        return lines

    def build_report(self, request: ResearchReportRequest) -> ResearchReport:
        records = [self.store.load(record_id) for record_id in request.record_ids]
        lines = ["# 研究核查报告", ""]
        for record in records:
            lines.extend(
                [
                    f"## {record.record_type}: {record.subject_source_id}",
                    f"- revision: `{record.record_id}`",
                    f"- created_at: `{record.created_at.isoformat()}`",
                ]
            )
            if record.revision_of:
                lines.append(f"- revision_of: `{record.revision_of}`")
            if record.record_type == "screening":
                lines.append(f"- decision: `{record.decision}`")
                for verdict in record.claims:
                    lines.extend(self._render_verdict(verdict))
            else:
                for field in record.fields:
                    lines.append(f"### {field.name}: {field.value}")
                    for verdict in field.claims:
                        lines.extend(self._render_verdict(verdict))
            lines.append("")
            if sum(len(line) + 1 for line in lines) > 200_000:
                raise ToolInputError("Research report exceeds the bounded output size")
        return ResearchReport(record_ids=request.record_ids, markdown="\n".join(lines))
