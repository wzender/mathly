"""mathtext.tidy: LaTeX the AI writes, shown as the plain symbols the app draws."""
from mathly2.mathtext import tidy


def test_the_photographed_question_from_the_field():
    raw = r'נתון: \triangle ABC הוא משולש שווה-שוקיים (). PF \perp AB, PA \perp AC, \angle A_1 = 30^\circ, PC = 18\text{ ס"מ}. מצאו את גודלה של \angle B.'
    got = tidy(raw)
    assert "\\" not in got and "()" not in got
    assert "△ ABC" in got and "שוקיים. PF" in got and "PF ⊥ AB" in got and "∠ A₁ = 30°" in got and 'PC = 18 ס"מ' in got and got.endswith("∠ B.")


def test_formulas_and_plain_text():
    assert tidy(r"$x^2 + 3x = \frac{1}{2}$") == "$x² + 3x = 1/2$"
    assert tidy(r"$\frac{x+10}{2y}$") == "$(x+10)/(2y)$"
    assert tidy(r"$\sqrt{16} = 4$") == "$√16 = 4$"
    assert tidy(r"$a_{12} \leq b^{10}$") == "$a₁₂ ≤ b¹⁰$"
    assert tidy(r"\(2x\) ו־\(3\)") == "$2x$ ו־$3$"
    assert tidy(r"$90^{\circ}$") == "$90°$"
    assert tidy("פתרו: $2x + 3 = 11$ (שימו לב)") == "פתרו: $2x + 3 = 11$ (שימו לב)"     # nothing to do: unchanged
    assert tidy("") == "" and tidy(None) == ""
    assert tidy("משולש שווה־שוקיים (). מצאו") == "משולש שווה־שוקיים. מצאו"
