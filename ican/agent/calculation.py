"""Small deterministic arithmetic interpreter; never executes Python code."""

import ast
from decimal import ROUND_FLOOR, Decimal, InvalidOperation, localcontext

from .schema import ToolInputError


def calculate(expression: str) -> str:
    if not isinstance(expression, str) or not 1 <= len(expression) <= 256:
        raise ToolInputError("Expression must contain 1–256 characters")
    try:
        tree = ast.parse(expression, mode="eval")
        if len(list(ast.walk(tree))) > 64:
            raise ToolInputError("Expression has too many operations")

        def visit(node):
            if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
                value = Decimal(ast.get_source_segment(expression, node))
            elif isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.UAdd, ast.USub)
            ):
                value = visit(node.operand)
                if isinstance(node.op, ast.USub):
                    value = -value
            elif isinstance(node, ast.BinOp):
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Add):
                    value = left + right
                elif isinstance(node.op, ast.Sub):
                    value = left - right
                elif isinstance(node.op, ast.Mult):
                    value = left * right
                elif isinstance(node.op, ast.Div):
                    value = left / right
                elif isinstance(node.op, (ast.FloorDiv, ast.Mod)):
                    if (
                        left != left.to_integral_value()
                        or right != right.to_integral_value()
                    ):
                        raise ToolInputError(
                            "Floor division and modulo require integer operands"
                        )
                    quotient = (left / right).to_integral_value(rounding=ROUND_FLOOR)
                    value = (
                        quotient
                        if isinstance(node.op, ast.FloorDiv)
                        else left - quotient * right
                    )
                elif (
                    isinstance(node.op, ast.Pow)
                    and right == right.to_integral_value()
                    and abs(right) <= 12
                ):
                    value = left ** int(right)
                else:
                    raise ToolInputError(
                        "Only +, -, *, /, integer // and %, and bounded integer powers are supported"
                    )
            else:
                raise ToolInputError("Only literal arithmetic is supported")
            if (
                not value.is_finite()
                or abs(value) > Decimal("1e18")
                or abs(value.as_tuple().exponent) > 100
            ):
                raise ToolInputError("Arithmetic result exceeds finite bounds")
            return value

        with localcontext() as context:
            context.prec = 40
            result = visit(tree.body)
        text = format(result, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    except (SyntaxError, InvalidOperation, ZeroDivisionError, OverflowError, TypeError):
        raise ToolInputError("Invalid or undefined arithmetic") from None
