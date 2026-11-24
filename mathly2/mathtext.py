"""LaTeX that an AI writes, as the plain math symbols the app shows (△, ∠, ⊥, °, √, ≤ ...). The app draws math as text inside $...$ (math.js
fmt), so a "\\triangle ABC" or "30^\\circ" from the AI would show as code. Text that has no backslash, caret, underscore or empty "()" comes back as is."""
from __future__ import annotations

import re

SYMBOLS = {
    "triangle": "△", "angle": "∠", "measuredangle": "∢", "perp": "⊥", "parallel": "∥", "cdot": "·", "times": "×", "div": "÷",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠", "pm": "±", "mp": "∓", "approx": "≈", "cong": "≅", "sim": "∼",
    "equiv": "≡", "Rightarrow": "⇒", "rightarrow": "→", "to": "→", "Leftrightarrow": "⇔", "in": "∈", "notin": "∉", "infty": "∞",
    "pi": "π", "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "Delta": "Δ", "theta": "θ", "lambda": "λ", "mu": "μ", "sigma": "σ",
    "circ": "°", "degree": "°", "cup": "∪", "cap": "∩", "emptyset": "∅", "varnothing": "∅", "ldots": "…", "dots": "…", "cdots": "⋯",
    "square": "□", "parallelogram": "▱", "overline": "", "quad": " ", "qquad": " ", "left": "", "right": "",
}
SUB = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
SUP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")


def _part(text: str) -> str:
    """A numerator or denominator: in brackets unless it is one number or one letter (2, 0.5, x)."""
    text = text.strip()
    return text if re.fullmatch(r"[0-9.]+|[A-Za-z]", text) else f"({text})"


def tidy(text: str | None) -> str:
    if not text:
        return text or ""
    s = str(text)
    if "\\" not in s and "^" not in s and "_" not in s and not re.search(r"\(\s*\)", s):
        return s
    s = s.replace("\\(", "$").replace("\\)", "$").replace("\\[", "$").replace("\\]", "$")
    for _ in range(3):                                                   # nested \text{\frac{..}{..}} and the like
        s = re.sub(r"\\(?:text|mathrm|textrm|mathbf|textbf|operatorname|mbox)\s*\{([^{}]*)\}", r"\1", s)
        s = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", lambda m: f"{_part(m[1])}/{_part(m[2])}", s)
        s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", lambda m: f"√{m[1]}" if len(m[1]) <= 2 else f"√({m[1]})", s)
        s = re.sub(r"\\overline\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\^\s*\{\s*\\circ\s*\}|\^\s*\\circ|\\circ", "°", s)
    s = re.sub(r"\\sqrt\b", "√", s)
    s = re.sub(r"\\([A-Za-z]+)", lambda m: SYMBOLS.get(m[1], m[0]), s)
    s = re.sub(r"\\[,;:! ]", " ", s).replace("\\{", "{").replace("\\}", "}").replace("\\%", "%")
    s = re.sub(r"_\{([0-9+\-=()]+)\}|_([0-9])", lambda m: (m[1] or m[2]).translate(SUB), s)
    s = re.sub(r"\^\{([0-9+\-=()n]+)\}|\^([0-9n])", lambda m: (m[1] or m[2]).translate(SUP), s)
    s = re.sub(r"\s*\(\s*\)", "", s)                                        # an empty "()" left where something could not be read
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()
