"""Verify typed claims without executing repository code."""

from __future__ import annotations

import ast
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from ican.agent.calculation import calculate
from ican.agent.schema import ToolInputError

from .schema import (
    CalculationResult,
    ClaimDraft,
    ClaimVerdict,
    CodeCondition,
    ConditionVerdict,
)


class ConditionUnsupported(ValueError):
    """An assert contains syntax outside the intentionally small evaluator."""


def _decimal(value):
    if type(value) not in {int, float}:
        raise ConditionUnsupported("Only numeric bindings are supported")
    try:
        converted = Decimal(str(value))
    except InvalidOperation as error:
        raise ConditionUnsupported("Binding is not a finite number") from error
    if not converted.is_finite() or abs(converted) > Decimal("1e18"):
        raise ConditionUnsupported("Binding exceeds finite bounds")
    return converted


def _bounded(value):
    if isinstance(value, Decimal) and (
        not value.is_finite()
        or abs(value) > Decimal("1e18")
        or abs(value.as_tuple().exponent) > 100
    ):
        raise ConditionUnsupported("Condition arithmetic exceeds finite bounds")
    return value


def _evaluate(node, bindings):
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        return _decimal(node.value)
    if isinstance(node, ast.Name):
        if node.id not in bindings:
            raise ConditionUnsupported(f"Missing binding: {node.id}")
        return bindings[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _evaluate(node.operand, bindings)
        return _bounded(-operand if isinstance(node.op, ast.USub) else operand)
    if isinstance(node, ast.BinOp):
        left, right = _evaluate(node.left, bindings), _evaluate(node.right, bindings)
        if isinstance(node.op, ast.Add):
            return _bounded(left + right)
        if isinstance(node.op, ast.Sub):
            return _bounded(left - right)
        if isinstance(node.op, ast.Mult):
            return _bounded(left * right)
        if isinstance(node.op, ast.Div):
            return _bounded(left / right)
        if isinstance(node.op, (ast.FloorDiv, ast.Mod)):
            if left != left.to_integral_value() or right != right.to_integral_value():
                raise ConditionUnsupported("Floor operations require integer operands")
            quotient = (left / right).to_integral_value(rounding=ROUND_FLOOR)
            return (
                quotient
                if isinstance(node.op, ast.FloorDiv)
                else left - quotient * right
            )
        if (
            isinstance(node.op, ast.Pow)
            and right == right.to_integral_value()
            and abs(right) <= 12
        ):
            return _bounded(left ** int(right))
        raise ConditionUnsupported("Unsupported arithmetic in assert")
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, bindings)
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            right = _evaluate(comparator, bindings)
            passed = {
                ast.Eq: left == right,
                ast.NotEq: left != right,
                ast.Lt: left < right,
                ast.LtE: left <= right,
                ast.Gt: left > right,
                ast.GtE: left >= right,
            }.get(type(operator))
            if passed is None:
                raise ConditionUnsupported("Unsupported comparison in assert")
            if not passed:
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        values = [_evaluate(value, bindings) for value in node.values]
        if not all(isinstance(value, bool) for value in values):
            raise ConditionUnsupported("Boolean assert requires boolean operands")
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        operand = _evaluate(node.operand, bindings)
        if not isinstance(operand, bool):
            raise ConditionUnsupported("not requires a boolean operand")
        return not operand
    raise ConditionUnsupported("Unsupported syntax in assert")


def _asserts_for_condition(corpus, condition: CodeCondition, evidence):
    if condition.chunk_id not in {item.chunk_id for item in evidence}:
        raise ToolInputError("Condition chunk must also be cited by the claim")
    item = next(item for item in evidence if item.chunk_id == condition.chunk_id)
    if item.source.source_type != "code":
        raise ToolInputError("Code execution conditions require a code evidence chunk")
    try:
        source = corpus.source_text(item.source.source_path)
        tree = ast.parse(source)
    except (SyntaxError, ToolInputError) as error:
        raise ConditionUnsupported("Original source cannot be safely parsed") from error
    location = item.source.location
    start, end = location.get("line_start"), location.get("line_end")
    if type(start) is not int or type(end) is not int:
        raise ConditionUnsupported("Code evidence has no line range")
    assertions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert) and start <= node.lineno <= end
    ]
    if not assertions:
        raise ConditionUnsupported("No static assert exists in the cited code range")
    return source, assertions


def _verify_conditions(corpus, claim, evidence):
    verdicts = []
    for condition in claim.conditions:
        try:
            source, assertions = _asserts_for_condition(corpus, condition, evidence)
            bindings = {
                key: _decimal(value) for key, value in condition.bindings.items()
            }
            for assertion in assertions:
                expression = (
                    ast.get_source_segment(source, assertion.test) or "<unavailable>"
                )
                try:
                    passed = _evaluate(assertion.test, bindings)
                    verdicts.append(
                        ConditionVerdict(
                            chunk_id=condition.chunk_id,
                            line=assertion.lineno,
                            expression=expression,
                            status="passed" if passed else "failed",
                        )
                    )
                except (
                    ConditionUnsupported,
                    InvalidOperation,
                    ZeroDivisionError,
                ) as error:
                    verdicts.append(
                        ConditionVerdict(
                            chunk_id=condition.chunk_id,
                            line=assertion.lineno,
                            expression=expression,
                            status="unsupported",
                            diagnostic=str(error),
                        )
                    )
        except ConditionUnsupported as error:
            verdicts.append(
                ConditionVerdict(
                    chunk_id=condition.chunk_id,
                    expression="<unavailable>",
                    status="unsupported",
                    diagnostic=str(error),
                )
            )
    return verdicts


def verify_claim(corpus, claim: ClaimDraft, *, allowed_ids: set[str] | None = None):
    if allowed_ids is not None and not set(claim.evidence_ids) <= allowed_ids:
        raise ToolInputError(
            "Claim evidence must already be in the current evidence pool"
        )
    evidence = [corpus.evidence(chunk_id) for chunk_id in claim.evidence_ids]
    diagnostics, calculation, conditions = [], None, []
    if claim.kind == "verbatim":
        if not all(claim.quote in item.text for item in evidence):
            diagnostics.append(
                "The supplied quote is absent from at least one cited chunk"
            )
            status = "insufficient_evidence"
        else:
            status = "supported"
    elif claim.kind == "numeric":
        try:
            calculation = CalculationResult(
                expression=claim.calculation.expression,
                result=calculate(claim.calculation.expression),
            )
            status = "supported"
        except ToolInputError as error:
            diagnostics.append(str(error))
            status = "insufficient_evidence"
    elif claim.kind == "code_execution":
        conditions = _verify_conditions(corpus, claim, evidence)
        if any(item.status == "failed" for item in conditions):
            status = "blocked_by_precondition"
        elif not conditions or any(item.status == "unsupported" for item in conditions):
            status = "insufficient_evidence"
        else:
            status = "supported"
    else:
        diagnostics.append("Inference claims require human semantic review")
        status = "requires_review"
    if status == "supported" and any(item.review_required for item in evidence):
        diagnostics.append("At least one cited chunk is marked review_required")
        status = "requires_review"
    return ClaimVerdict(
        claim=claim,
        status=status,
        evidence=evidence,
        conditions=conditions,
        calculation=calculation,
        diagnostics=diagnostics,
    )
