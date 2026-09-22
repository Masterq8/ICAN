"""Conservative semantic checks for commonly confused experiment-card fields."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict


class FieldSemanticDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["review"] = "review"
    message: str
    suggested_field: Literal["dataset", "metric", "result"]


METRIC = re.compile(
    r"\b(?:accuracy|acc\.?|f1(?:[- ]score)?|bleu|rouge|wer|word error rate|"
    r"map|mrr|mean (?:average precision|reciprocal rank)|auc|precision|recall|"
    r"perplexity|spearman(?:'s)?(?: rho)?|kendall|correlation|exact match)\b",
    re.IGNORECASE,
)
DATASET = re.compile(
    r"\b(?:dataset|corpus|benchmark|test set|training set|validation set|dev set)\b",
    re.IGNORECASE,
)
RESULT = re.compile(
    r"\b(?:achiev(?:e|es|ed)|outperform(?:s|ed)?|improv(?:e|es|ed|ement)|"
    r"surpass(?:es|ed)?|better than|worse than|state[- ]of[- ]the[- ]art|"
    r"increase(?:s|d)?|decrease(?:s|d)?)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?\s*(?:%|points?|x)?\b")
METRIC_ONLY = re.compile(
    r"^(?:the\s+)?(?:accuracy|f1(?:[- ]score)?|bleu(?:[- ]\d+)?|rouge(?:[- ][ln])?|"
    r"wer|word error rate|map|mrr|mean average precision|mean reciprocal rank|auc|"
    r"precision|recall|perplexity|spearman(?:'s)?(?: rho)?|kendall(?: tau)?|"
    r"correlation|exact match)(?:\s+(?:score|metric))?$",
    re.IGNORECASE,
)


def _diagnostic(code: str, source: str, target: str):
    return FieldSemanticDiagnostic(
        code=code,
        suggested_field=target,
        message=f"{source} value has strong lexical signals for {target}; verify field type",
    )


def diagnose_field_assignment(
    name: str, value: str, quote: str | None = None
) -> list[FieldSemanticDiagnostic]:
    """Flag only strong dataset/metric/result conflicts; never relabel content."""

    if name not in {"dataset", "metric", "result"}:
        return []
    text = " ".join(value.split())
    context = " ".join(part for part in (text, quote or "") if part)
    metric_only = bool(METRIC_ONLY.fullmatch(text.strip(" .:;")))
    dataset_cue = bool(DATASET.search(context))
    result_cue = bool(RESULT.search(text))
    scored_result = result_cue and bool(NUMBER.search(text))

    if name == "dataset":
        if metric_only:
            return [_diagnostic("dataset_is_metric", "dataset", "metric")]
        if scored_result:
            return [_diagnostic("dataset_is_result", "dataset", "result")]
    elif name == "metric":
        if result_cue and (NUMBER.search(text) or not METRIC.search(text)):
            return [_diagnostic("metric_is_result", "metric", "result")]
        if dataset_cue and not METRIC.search(context):
            return [_diagnostic("metric_is_dataset", "metric", "dataset")]
    elif name == "result":
        if metric_only:
            return [_diagnostic("result_is_metric", "result", "metric")]
        if dataset_cue and not result_cue and not METRIC.search(text):
            return [_diagnostic("result_is_dataset", "result", "dataset")]
    return []
