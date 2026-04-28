from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LinearUnit:
    name: str
    category: str
    factor: float


LINEAR_UNITS = {
    "m": LinearUnit("meter", "Length", 1.0),
    "cm": LinearUnit("centimeter", "Length", 0.01),
    "mm": LinearUnit("millimeter", "Length", 0.001),
    "km": LinearUnit("kilometer", "Length", 1000.0),
    "in": LinearUnit("inch", "Length", 0.0254),
    "ft": LinearUnit("foot", "Length", 0.3048),
    "yd": LinearUnit("yard", "Length", 0.9144),
    "mi": LinearUnit("mile", "Length", 1609.344),
    "kg": LinearUnit("kilogram", "Mass", 1.0),
    "g": LinearUnit("gram", "Mass", 0.001),
    "lb": LinearUnit("pound", "Mass", 0.45359237),
    "oz": LinearUnit("ounce", "Mass", 0.028349523125),
    "s": LinearUnit("second", "Time", 1.0),
    "min": LinearUnit("minute", "Time", 60.0),
    "h": LinearUnit("hour", "Time", 3600.0),
    "day": LinearUnit("day", "Time", 86400.0),
    "mps": LinearUnit("meter/second", "Speed", 1.0),
    "kmph": LinearUnit("kilometer/hour", "Speed", 0.2777777777777778),
    "mph": LinearUnit("mile/hour", "Speed", 0.44704),
    "j": LinearUnit("joule", "Energy", 1.0),
    "kj": LinearUnit("kilojoule", "Energy", 1000.0),
    "wh": LinearUnit("watt-hour", "Energy", 3600.0),
    "pa": LinearUnit("pascal", "Pressure", 1.0),
    "kpa": LinearUnit("kilopascal", "Pressure", 1000.0),
    "bar": LinearUnit("bar", "Pressure", 100000.0),
    "b": LinearUnit("byte", "Data Storage", 1.0),
    "kb": LinearUnit("kilobyte", "Data Storage", 1024.0),
    "mb": LinearUnit("megabyte", "Data Storage", 1024.0 * 1024.0),
    "gb": LinearUnit("gigabyte", "Data Storage", 1024.0 * 1024.0 * 1024.0),
    "deg": LinearUnit("degree", "Angle", 1.0),
    "rad": LinearUnit("radian", "Angle", 57.29577951308232),
    "grad": LinearUnit("gradian", "Angle", 0.9),
}


UNIT_CATEGORIES = sorted({unit.category for unit in LINEAR_UNITS.values()} | {"Temperature"})
INLINE_PATTERN = re.compile(
    r"^\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s+(?P<from>[a-zA-Z]+)\s+to\s+(?P<to>[a-zA-Z]+)\s*$",
    re.IGNORECASE,
)


def _temperature_convert(value: float, from_unit: str, to_unit: str) -> tuple[float, str]:
    source = from_unit.lower()
    target = to_unit.lower()
    to_celsius = {
        "c": lambda v: v,
        "f": lambda v: (v - 32.0) * 5.0 / 9.0,
        "k": lambda v: v - 273.15,
    }
    from_celsius = {
        "c": lambda v: v,
        "f": lambda v: v * 9.0 / 5.0 + 32.0,
        "k": lambda v: v + 273.15,
    }
    if source not in to_celsius or target not in from_celsius:
        raise ValueError("Unsupported temperature conversion")
    celsius = to_celsius[source](value)
    converted = from_celsius[target](celsius)
    formula = {
        ("c", "f"): "F = C x 9/5 + 32",
        ("f", "c"): "C = (F - 32) x 5/9",
        ("c", "k"): "K = C + 273.15",
        ("k", "c"): "C = K - 273.15",
    }.get((source, target), "Converted via Celsius")
    return converted, formula


def convert_value(value: float, from_unit: str, to_unit: str) -> tuple[float, str, str]:
    source = from_unit.lower()
    target = to_unit.lower()
    if source in {"c", "f", "k"} or target in {"c", "f", "k"}:
        converted, formula = _temperature_convert(value, source, target)
        return converted, "Temperature", formula

    if source not in LINEAR_UNITS or target not in LINEAR_UNITS:
        raise ValueError("Unsupported unit")
    from_meta = LINEAR_UNITS[source]
    to_meta = LINEAR_UNITS[target]
    if from_meta.category != to_meta.category:
        raise ValueError("Unit categories do not match")
    base_value = value * from_meta.factor
    converted = base_value / to_meta.factor
    formula = f"{value} {source} x {from_meta.factor} / {to_meta.factor}"
    return converted, from_meta.category, formula


def parse_inline_conversion(expression: str) -> tuple[float, str, str] | None:
    match = INLINE_PATTERN.match(expression)
    if not match:
        return None
    return (
        float(match.group("value")),
        match.group("from"),
        match.group("to"),
    )
