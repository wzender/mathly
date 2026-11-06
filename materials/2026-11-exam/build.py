"""Build the November mock exam and its answer key as HTML, then PDF (Chrome via Playwright)."""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])


def m(s):
    """Math inline: $...$ -> LTR span, letters italic."""
    def one(mt):
        t = mt.group(1)
        t = re.sub(r"([a-zA-Z]+)", r"<i>\1</i>", t)
        return f'<span class="m" dir="ltr">{t}</span>'
    return re.sub(r"\$(.+?)\$", one, s)


CSS = """
@page { size: A4; margin: 16mm 16mm 16mm 16mm; }
body { font-family: 'Noto Sans Hebrew', sans-serif; direction: rtl; font-size: 12pt; line-height: 1.55; color: #111; }
h1 { font-size: 18pt; margin: 0 0 2mm; text-align: center; }
.sub { text-align: center; color: #444; margin-bottom: 4mm; }
.box { border: 1px solid #999; border-radius: 4px; padding: 3mm 4mm; margin-bottom: 5mm; font-size: 11pt; }
h2 { font-size: 13.5pt; border-bottom: 2px solid #333; padding-bottom: 1mm; margin: 6mm 0 3mm; }
.q { break-inside: avoid; margin-bottom: 5mm; }
.qh { font-weight: 700; }
.pts { font-weight: 400; color: #555; }
ol.parts { list-style: none; padding-right: 4mm; margin: 1mm 0; }
ol.parts li { margin: 1mm 0; }
.lbl { font-weight: 700; margin-left: 1.5mm; }
.m { font-family: 'Noto Serif', 'DejaVu Serif', serif; unicode-bidi: isolate; white-space: nowrap; }
.m i { font-style: italic; }
.fig { float: left; margin: 0 4mm 2mm 0; }
.clear { clear: both; }
.ans { margin: 1mm 0 1mm; padding-right: 4mm; }
.key .q { border-right: 3px solid #bbb; padding-right: 3mm; }
.note { color: #555; font-size: 10.5pt; }
.foot { text-align: center; margin-top: 6mm; font-size: 13pt; }
"""

# ---------- figures (SVG) ----------
def svg(w, h, body):
    return (f'<svg class="fig" width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="Noto Serif, serif" font-style="italic" font-size="15">{body}</svg>')

KITE = svg(230, 260, """
<polygon points="115,30 30,95 115,240 200,95" fill="none" stroke="#111" stroke-width="1.8"/>
<line x1="115" y1="30" x2="115" y2="240" stroke="#111" stroke-width="1.2"/>
<line x1="30" y1="95" x2="200" y2="95" stroke="#111" stroke-width="1.2"/>
<text x="110" y="22">A</text><text x="14" y="90">B</text><text x="110" y="257">C</text><text x="206" y="90">D</text>
<text x="120" y="112">E</text>
<line x1="68" y1="58" x2="76" y2="66" stroke="#111"/><line x1="154" y1="66" x2="162" y2="58" stroke="#111"/>
<g stroke="#111"><line x1="66" y1="170" x2="76" y2="165"/><line x1="70" y1="174" x2="80" y2="169"/>
<line x1="154" y1="165" x2="164" y2="170"/><line x1="150" y1="169" x2="160" y2="174"/></g>
""")

GRID = (lambda: svg(230, 250, "".join(
    [f'<line x1="{20+i*20}" y1="10" x2="{20+i*20}" y2="230" stroke="#ddd"/>' for i in range(11)] +
    [f'<line x1="20" y1="{10+j*20}" x2="220" y2="{10+j*20}" stroke="#ddd"/>' for j in range(12)]) + """
<line x1="20" y1="150" x2="220" y2="150" stroke="#111" stroke-width="1.3"/>
<line x1="60" y1="230" x2="60" y2="10" stroke="#111" stroke-width="1.3"/>
<text x="222" y="146" font-size="12">x</text><text x="64" y="16" font-size="12">y</text>
<text x="48" y="164" font-size="11" font-style="normal">0</text>
<polygon points="100,30 40,110 100,210 160,110" fill="none" stroke="#111" stroke-width="1.8"/>
<g fill="#111"><circle cx="100" cy="30" r="2.5"/><circle cx="40" cy="110" r="2.5"/><circle cx="100" cy="210" r="2.5"/><circle cx="160" cy="110" r="2.5"/></g>
<text x="106" y="30">A</text><text x="24" y="106">B</text><text x="106" y="224">C</text><text x="164" y="106">D</text>
"""))()

# right triangle, angle C = 90, angle A = 30, AB horizontal
TRI_ALT = svg(314, 200, """<g transform="translate(14,0)">
<polygon points="20,170 284,170 218,55.7" fill="none" stroke="#111" stroke-width="1.8"/>
<line x1="218" y1="55.7" x2="218" y2="170" stroke="#111" stroke-width="1.2"/>
<polyline points="218,160 228,160 228,170" fill="none" stroke="#111"/>
<path d="M 60 170 A 40 40 0 0 0 54.6 150" fill="none" stroke="#111"/>
<text x="66" y="162" font-style="normal" font-size="12">30°</text>
<text x="4" y="176">A</text><text x="288" y="176">B</text><text x="212" y="46">C</text><text x="212" y="190">D</text></g>
""")

TRI_MED = svg(314, 200, """<g transform="translate(14,0)">
<polygon points="20,170 284,170 218,55.7" fill="none" stroke="#111" stroke-width="1.8"/>
<line x1="218" y1="55.7" x2="152" y2="170" stroke="#111" stroke-width="1.2"/>
<text x="4" y="176">A</text><text x="288" y="176">B</text><text x="212" y="46">C</text><text x="146" y="190">M</text>
<g stroke="#111"><line x1="86" y1="165" x2="86" y2="175"/><line x1="218" y1="165" x2="218" y2="175"/></g></g>
""")

# ---------- content ----------
# Each question: (title, points, intro, [parts], figure, [answers per part])
Q = [
    ("נוסחאות הכפל המקוצר", 12,
     "",
     ["פשטו את הביטוי והראו שערכו אינו תלוי ב־$x$:&nbsp; $(2x − 3)² − (x + 1)(x − 1) − 3x(x − 4)$",
      "חשבו בלי מחשבון, בעזרת נוסחאות הכפל המקוצר, והראו כיצד:&nbsp; $53² − 47²$ &nbsp;ו־&nbsp; $999²$",
      "נתון: $a + b = 7$ ו־$ab = 10$. חשבו את $a² + b²$ ואת $(a − b)²$ (בלי למצוא את $a$ ואת $b$)."],
     "",
     ["$4x² − 12x + 9 − (x² − 1) − 3x² + 12x = 10$. הערך הוא $10$ לכל $x$.",
      "$53² − 47² = (53 − 47)(53 + 47) = 6 · 100 = 600$. &nbsp; $999² = (1000 − 1)² = 1,000,000 − 2,000 + 1 = 998,001$.",
      "$a² + b² = (a + b)² − 2ab = 49 − 20 = 29$. &nbsp; $(a − b)² = a² + b² − 2ab = 29 − 20 = 9$."]),

    ("פירוק לגורמים", 14,
     "פרקו לגורמים ככל האפשר:",
     ["$3x² − 12$", "$x² − x − 20$", "$2x² + 7x + 3$", "$x³ − 6x² + 9x$"],
     "",
     ["$3(x² − 4) = 3(x − 2)(x + 2)$",
      "$(x − 5)(x + 4)$ (מכפלה $−20$, סכום $−1$)",
      "$(2x + 1)(x + 3)$. בדיקה: $2x² + 6x + x + 3$.",
      "$x(x² − 6x + 9) = x(x − 3)²$"]),

    ("משוואות ריבועיות בפירוק לגורמים", 16,
     "פתרו את המשוואות בעזרת פירוק לגורמים:",
     ["$x² − 9x + 14 = 0$", "$4x² = 12x$", "$(x + 3)² = 2(x + 3) + 15$",
      "אורך של מלבן גדול ב־$3$ ס״מ מרוחבו, ושטחו $40$ סמ״ר. מצאו את מידות המלבן."],
     "",
     ["$(x − 2)(x − 7) = 0$, ולכן $x = 2$ או $x = 7$.",
      "$4x² − 12x = 0 ⇒ 4x(x − 3) = 0$, ולכן $x = 0$ או $x = 3$. <span class=\"note\">טעות נפוצה: לחלק ב־$x$ ולאבד את $x = 0$.</span>",
      "פתיחת סוגריים: $x² + 4x − 12 = 0 ⇒ (x + 6)(x − 2) = 0$, ולכן $x = 2$ או $x = −6$. (אפשר גם להציב $t = x + 3$: $t² − 2t − 15 = 0$, $t = 5$ או $t = −3$.)",
      "רוחב $x$, אורך $x + 3$: $x(x + 3) = 40 ⇒ x² + 3x − 40 = 0 ⇒ (x + 8)(x − 5) = 0$. $x = −8$ נפסל (אורך חיובי). המלבן: $5$ ס״מ על $8$ ס״מ."]),

    ("דלתון", 16,
     "$ABCD$ הוא דלתון שבו $AB = AD$ ו־$CB = CD$. האלכסונים נחתכים בנקודה $E$. <span class=\"note\">(הסעיפים ב׳ ו־ג׳ אינם תלויים זה בזה; השרטוט סכמטי.)</span>",
     ["הוכיחו: $AC ⊥ BD$ ו־$BE = ED$.",
      "נתון: $∢BAD = 80°$ ו־$∢BCD = 40°$. חשבו את $∢ABC$ ואת $∢CBD$.",
      "נתון: $AE = 6$ ס״מ, $BD = 16$ ס״מ, $EC = 15$ ס״מ. חשבו את היקף הדלתון ואת שטחו."],
     KITE,
     ["$△ABC ≅ △ADC$ (צ.צ.צ: $AB = AD$, $CB = CD$, $AC$ משותפת), ולכן $∢BAC = ∢DAC$. במשולש שווה השוקיים $ABD$ ($AB = AD$), $AE$ חוצה את זווית הראש, ולכן הוא גם גובה וגם תיכון: $AC ⊥ BD$ ו־$BE = ED$.",
      "$∢ABC = ∢ADC$ (מחפיפת המשולשים), ולכן $∢ABC = (360° − 80° − 40°) : 2 = 120°$. במשולש שווה השוקיים $CBD$: $∢CBD = (180° − 40°) : 2 = 70°$. (בדיקה: $∢ABD = 50°$, ו־$50° + 70° = 120°$.)",
      "$BE = 8$ (האלכסון הראשי חוצה את המשני). פיתגורס: $AB = √(6² + 8²) = 10$, $BC = √(15² + 8²) = 17$. היקף: $2(10 + 17) = 54$ ס״מ. שטח: $AC · BD : 2 = 21 · 16 : 2 = 168$ סמ״ר."]),

    ("דלתון במערכת צירים", 12,
     "נתונות הנקודות $A(2, 6)$, $B(−1, 2)$, $C(2, −3)$, $D(5, 2)$.",
     ["חשבו את אורכי הצלעות של המרובע $ABCD$ והראו שהוא דלתון.",
      "הראו ש־$AC ⊥ BD$ ושהאלכסון $AC$ עובר באמצע $BD$.",
      "חשבו את שטח הדלתון.",
      "על הישר $AC$ יש נקודה $P$ (שונה מ־$A$) כך שבמרובע $ABPD$ כל ארבע הצלעות שוות. מצאו את שיעורי $P$."],
     GRID,
     ["$AB = √(3² + 4²) = 5$, $AD = √(3² + 4²) = 5$, $CB = √(3² + 5²) = √34$, $CD = √34$. שני זוגות של צלעות סמוכות שוות, ולכן $ABCD$ דלתון.",
      "$AC$ אנכי (על הישר $x = 2$), $BD$ אופקי (על הישר $y = 2$), ולכן הם מאונכים. אמצע $BD$ הוא $(2, 2)$, והוא על הישר $x = 2$.",
      "$AC = 9$, $BD = 6$, שטח $= 9 · 6 : 2 = 27$ יח״ר.",
      "$P(2, y)$ עם $PB = 5$: $3² + (y − 2)² = 25 ⇒ (y − 2)² = 16 ⇒ y = 6$ או $y = −2$. $y = 6$ היא $A$, ולכן $P(2, −2)$. בדיקה: $PD = 5$ גם כן."]),

    ("משולש ישר זווית עם זווית של $30°$", 14,
     "במשולש $ABC$: $∢ACB = 90°$ ו־$∢A = 30°$. $CD$ הוא הגובה ליתר $AB$, ונתון $BD = 3$ ס״מ.",
     ["חשבו את $BC$, את $AB$ ואת $AD$. נמקו כל שלב.",
      "חשבו את $CD$.",
      "<b>שאלה נפרדת:</b> במשולש $KLM$ נתון $∢L = 90°$ ו־$KM = 2 · LM$. מצאו את $∢K$ ואת $∢M$, וציינו באיזה משפט השתמשתם."],
     TRI_ALT,
     ["$∢B = 60°$, ולכן במשולש $BCD$ (ישר זווית ב־$D$): $∢BCD = 30°$. הניצב שמול זווית של $30°$ שווה לחצי היתר: $BD = BC : 2$, ולכן $BC = 6$. במשולש $ABC$: $BC$ מול $∢A = 30°$, ולכן $AB = 2 · BC = 12$. $AD = 12 − 3 = 9$ ס״מ.",
      "פיתגורס במשולש $BCD$: $CD = √(6² − 3²) = √27 = 3√3 ≈ 5.2$ ס״מ.",
      "המשפט ההפוך: אם במשולש ישר זווית ניצב שווה לחצי היתר, הזווית שמולו היא $30°$. $LM$ מול $∢K$, ולכן $∢K = 30°$ ו־$∢M = 60°$."]),

    ("התיכון ליתר", 16,
     "במשולש $ABC$ הנקודה $M$ היא אמצע הצלע $AB$, ונתון: $CM = AM$.",
     ["הוכיחו ש־$∢ACB = 90°$.",
      "נתון בנוסף: $CM = BC$. הוכיחו ש־$∢A = 30°$.",
      "נתון: $AB = 12$ ס״מ (בנוסף לנתוני סעיף ב׳). חשבו את $BC$ ואת $∢AMC$."],
     TRI_MED,
     ["$MA = MC = MB$. במשולש $AMC$: $∢A = ∢ACM = α$; במשולש $BMC$: $∢B = ∢BCM = β$. סכום זוויות $△ABC$: $2α + 2β = 180°$, ולכן $∢ACB = α + β = 90°$. (מותר גם לצטט את המשפט ההפוך לתיכון ליתר: תיכון ששווה לחצי הצלע שאליה הוא יורד.)",
      "לפי המשפט (התיכון ליתר שווה לחצי היתר): $CM = MB$. עם $CM = BC$ מתקבל $△CMB$ שווה צלעות, ולכן $∢B = 60°$ ו־$∢A = 90° − 60° = 30°$.",
      "$BC = CM = AB : 2 = 6$ ס״מ. $∢AMC$ זווית חיצונית למשולש שווה הצלעות $CMB$: $∢AMC = 180° − 60° = 120°$."]),
]


def question_html(i, q, key):
    title, pts, intro, parts, fig, answers = q
    h = [f'<div class="q"><div class="qh">שאלה {i} — {m(title)} <span class="pts">({pts} נקודות)</span></div>']
    if not key and fig:
        h.append(fig)
    if intro:
        h.append(f"<div>{m(intro)}</div>")
    letters = "אבגדה"
    h.append('<ol class="parts">')
    for j, p in enumerate(parts):
        if key:
            h.append(f'<li><span class="lbl">{letters[j]}.</span>{m(p)}<div class="ans">✔ {m(answers[j])}</div></li>')
        else:
            h.append(f'<li><span class="lbl">{letters[j]}.</span>{m(p)}</li>')
    h.append("</ol>")
    if not key and fig:
        h.append('<div class="clear"></div>')
    h.append("</div>")
    return "".join(h)


def page(key):
    total = sum(q[1] for q in Q)
    assert total == 100, total
    head = ("מבחן לדוגמה — פתרונות ומחוון" if key else "מבחן לדוגמה — נובמבר")
    sub = "מתמטיקה כיתה ט׳ מצוינות · תשפ״ז · הכנה למבחן 15–16.11.2026"
    box = ("" if key else
           '<div class="box">זמן: 90 דקות · 7 שאלות · 100 נקודות. ענו על כל השאלות. '
           "כתבו את הפתרון המלא, כולל נימוקים, על דף משלכם, וצלמו את כל הדפים להגשה במתלי. "
           "מותר להשתמש במחשבון רגיל (בשאלה 1 סעיף ב׳ — בלי מחשבון). "
           "השרטוטים אינם בהכרח בקנה מידה.</div>")
    body = [f"<h1>{head}</h1><div class=\"sub\">{sub}</div>{box}"]
    body.append(f'<h2>חלק א׳ — אלגברה ({sum(q[1] for q in Q[:3])} נקודות)</h2>')
    for i, q in enumerate(Q[:3], 1):
        body.append(question_html(i, q, key))
    body.append(f'<h2>חלק ב׳ — גיאומטריה ({sum(q[1] for q in Q[3:])} נקודות)</h2>')
    for i, q in enumerate(Q[3:], 4):
        body.append(question_html(i, q, key))
    if key:
        body.append('<h2>תרגול ממוקד במתלי לפי שאלה</h2><div class="note">'
                    "שאלה 1: נוסחאות הכפל המקוצר · שאלה 2: פירוק טרינום ריבועי, פירוק בנוסחאות הכפל המקוצר · "
                    "שאלה 3: משוואות ריבועיות בסיסיות בפירוק לגורמים · שאלה 4: זוויות בדלתון, האלכסון הראשי בדלתון · "
                    "שאלה 5: דלתון במערכת צירים · שאלה 6: ניצב מול זווית של 30°, המשפט ההפוך · "
                    "שאלה 7: התיכון ליתר, המשפט ההפוך לתיכון ליתר</div>")
    else:
        body.append('<div class="foot">בהצלחה!</div>')
    return (f'<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><title>{head}</title>'
            f"<style>{CSS}</style></head><body>{''.join(body)}</body></html>")


OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome")
    pg = browser.new_page()
    for key, name in [(False, "mock-exam"), (True, "mock-exam-answer-key")]:
        html = page(key)
        (OUT / f"{name}.html").write_text(html, encoding="utf-8")
        pg.set_content(html)
        pg.pdf(path=str(OUT / f"{name}.pdf"), format="A4", print_background=True, prefer_css_page_size=True)
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    browser.close()
print("ok")
