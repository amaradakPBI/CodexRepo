from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Any

from .constants import CONSTANTS
from .conversions import convert_value, parse_inline_conversion


@dataclass
class CalculationResult:
    expression: str
    rendered_expression: str
    result: Any
    display: str
    mode: str
    angle_unit: str
    display_format: str
    base: str
    assigned_variable: str | None = None
    formula: str | None = None


def display_in_bases(value: int, word_size: int) -> dict[str, str]:
    mask = (1 << word_size) - 1
    masked = value & mask
    width = max(1, word_size // 4)
    return {
        "BIN": format(masked, f"0{word_size}b"),
        "OCT": format(masked, "o"),
        "DEC": str(masked if masked <= mask else value),
        "HEX": format(masked, f"0{width}X"),
    }


class CalculatorEngine:
    def __init__(self) -> None:
        self._constants = {constant.key: constant.value for constant in CONSTANTS}

    def evaluate(
        self,
        expression: str,
        *,
        mode: str,
        angle_unit: str,
        precision: int,
        display_format: str,
        word_size: int,
        variables: dict[str, float],
        ans: float | int,
    ) -> CalculationResult:
        raw_expression = expression.strip()
        if not raw_expression:
            raise ValueError("Enter an expression")

        inline_conversion = parse_inline_conversion(raw_expression)
        if inline_conversion:
            value, from_unit, to_unit = inline_conversion
            converted, category, formula = convert_value(value, from_unit, to_unit)
            rendered = self._format_number(converted, precision, display_format)
            return CalculationResult(
                expression=raw_expression,
                rendered_expression=raw_expression,
                result=converted,
                display=rendered,
                mode=mode,
                angle_unit=angle_unit,
                display_format=display_format,
                base="DEC",
                formula=f"{category}: {formula}",
            )

        assigned_variable = None
        expr_body = raw_expression
        if "=" in raw_expression and "==" not in raw_expression:
            left, right = raw_expression.split("=", 1)
            candidate = left.strip()
            if candidate.isidentifier():
                assigned_variable = candidate
                expr_body = right.strip()

        prepared = self._prepare_expression(expr_body, mode)
        names = self._build_names(variables=variables, ans=ans, angle_unit=angle_unit)
        value = self._safe_eval(prepared, names)
        if mode == "Programmer":
            integer_value = int(value)
            display = self._format_programmer(integer_value, word_size)
            result_value = integer_value
        else:
            display = self._format_number(float(value), precision, display_format)
            result_value = float(value)

        return CalculationResult(
            expression=raw_expression,
            rendered_expression=expr_body,
            result=result_value,
            display=display,
            mode=mode,
            angle_unit=angle_unit,
            display_format=display_format,
            base="DEC",
            assigned_variable=assigned_variable,
        )

    def _prepare_expression(self, expression: str, mode: str) -> str:
        prepared = expression.replace("÷", "/").replace("×", "*").replace("−", "-")
        if mode != "Programmer":
            prepared = prepared.replace("^", "**")
        prepared = prepared.replace("%", "/100")
        return prepared

    def _build_names(
        self,
        *,
        variables: dict[str, float],
        ans: float | int,
        angle_unit: str,
    ) -> dict[str, Any]:
        def to_radians(value: float) -> float:
            if angle_unit == "Degree":
                return math.radians(value)
            if angle_unit == "Gradian":
                return value * math.pi / 200.0
            return value

        def from_radians(value: float) -> float:
            if angle_unit == "Degree":
                return math.degrees(value)
            if angle_unit == "Gradian":
                return value * 200.0 / math.pi
            return value

        names: dict[str, Any] = {
            **self._constants,
            **variables,
            "Ans": ans,
            "abs": abs,
            "sqrt": math.sqrt,
            "cbrt": lambda value: math.copysign(abs(value) ** (1.0 / 3.0), value),
            "root": lambda degree, value: value ** (1.0 / degree),
            "sin": lambda value: math.sin(to_radians(value)),
            "cos": lambda value: math.cos(to_radians(value)),
            "tan": lambda value: math.tan(to_radians(value)),
            "asin": lambda value: from_radians(math.asin(value)),
            "acos": lambda value: from_radians(math.acos(value)),
            "atan": lambda value: from_radians(math.atan(value)),
            "sinh": math.sinh,
            "cosh": math.cosh,
            "tanh": math.tanh,
            "asinh": math.asinh,
            "acosh": math.acosh,
            "atanh": math.atanh,
            "ln": math.log,
            "log": math.log10,
            "log2": math.log2,
            "logx": lambda value, base: math.log(value, base),
            "exp": math.exp,
            "pow": pow,
            "fact": lambda value: math.factorial(int(value)),
            "npr": lambda n, r: math.perm(int(n), int(r)),
            "ncr": lambda n, r: math.comb(int(n), int(r)),
            "mod": lambda a, b: a % b,
            "floor": math.floor,
            "ceil": math.ceil,
            "round": round,
        }
        return names

    def _safe_eval(self, expression: str, names: dict[str, Any]) -> Any:
        parsed = ast.parse(expression, mode="eval")
        return self._visit(parsed.body, names)

    def _visit(self, node: ast.AST, names: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Unsupported constant")
        if isinstance(node, ast.Name):
            if node.id not in names:
                raise ValueError(f"Unknown identifier: {node.id}")
            return names[node.id]
        if isinstance(node, ast.BinOp):
            left = self._visit(node.left, names)
            right = self._visit(node.right, names)
            operators = {
                ast.Add: lambda a, b: a + b,
                ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b,
                ast.Div: lambda a, b: a / b,
                ast.Pow: lambda a, b: a**b,
                ast.Mod: lambda a, b: a % b,
                ast.BitAnd: lambda a, b: int(a) & int(b),
                ast.BitOr: lambda a, b: int(a) | int(b),
                ast.BitXor: lambda a, b: int(a) ^ int(b),
                ast.LShift: lambda a, b: int(a) << int(b),
                ast.RShift: lambda a, b: int(a) >> int(b),
            }
            for op_type, handler in operators.items():
                if isinstance(node.op, op_type):
                    return handler(left, right)
            raise ValueError("Unsupported operator")
        if isinstance(node, ast.UnaryOp):
            operand = self._visit(node.operand, names)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.Invert):
                return ~int(operand)
            raise ValueError("Unsupported unary operator")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Unsupported function call")
            function_name = node.func.id
            function = names.get(function_name)
            if function is None or not callable(function):
                raise ValueError(f"Unknown function: {function_name}")
            args = [self._visit(argument, names) for argument in node.args]
            return function(*args)
        raise ValueError("Unsupported expression")

    def _format_programmer(self, value: int, word_size: int) -> str:
        bases = display_in_bases(value, word_size)
        return " | ".join(f"{base}: {rendered}" for base, rendered in bases.items())

    def _format_number(self, value: float, precision: int, display_format: str) -> str:
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if math.isnan(value):
            return "NaN"
        if display_format == "Scientific":
            return f"{value:.{precision}e}"
        if display_format == "Engineering":
            if value == 0:
                return "0"
            exponent = int(math.floor(math.log10(abs(value))))
            engineering_exponent = exponent - (exponent % 3)
            mantissa = value / (10 ** engineering_exponent)
            return f"{mantissa:.{precision}f}e{engineering_exponent}"
        if display_format == "Fraction":
            numerator, denominator = value.as_integer_ratio()
            return f"{numerator}/{denominator}"
        return f"{value:.{precision}f}".rstrip("0").rstrip(".")
