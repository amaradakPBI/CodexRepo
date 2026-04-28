from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Constant:
    key: str
    label: str
    category: str
    value: float
    unit: str


CONSTANTS = [
    Constant("pi", "pi", "Mathematical", 3.141592653589793, ""),
    Constant("e", "e", "Mathematical", 2.718281828459045, ""),
    Constant("tau", "tau", "Mathematical", 6.283185307179586, ""),
    Constant("phi", "phi", "Mathematical", 1.618033988749895, ""),
    Constant("c", "c", "Physical", 299792458.0, "m/s"),
    Constant("g", "g", "Physical", 9.80665, "m/s^2"),
    Constant("h", "Planck", "Physical", 6.62607015e-34, "J*s"),
    Constant("na", "Avogadro", "Chemical", 6.02214076e23, "1/mol"),
    Constant("r", "Gas constant", "Chemical", 8.314462618, "J/(mol*K)"),
    Constant("au", "Astronomical unit", "Astronomical", 149597870700.0, "m"),
]


def constant_search(term: str) -> list[Constant]:
    normalized = term.strip().lower()
    if not normalized:
        return CONSTANTS
    return [
        constant
        for constant in CONSTANTS
        if normalized in constant.key.lower()
        or normalized in constant.label.lower()
        or normalized in constant.category.lower()
    ]
