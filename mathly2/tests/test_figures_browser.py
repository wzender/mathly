import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.bank import load_bank
from mathly2.main import create_app
from mathly2.tests.serve import offline_formulas, running


def bank_questions():
    return [q for s in load_bank().skills for q in s.get("questions", [])]


def test_a_geometry_figure_and_a_graph_are_drawn():
    figure = next(q for q in bank_questions() if "figure" in q)
    graph = next(q for q in bank_questions() if "graph" in q)
    with running(create_app()) as url, playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = offline_formulas(browser.new_page(viewport={"width": 390, "height": 844}))
        page.goto(url)
        page.evaluate("""async ([figure, graph]) => {
            const { figures } = await import('/static/figures.js');
            const box = document.createElement('div');
            box.id = 'probe';
            box.innerHTML = figures(figure) + figures(graph);
            document.body.append(box);
        }""", [figure, graph])
        assert page.locator("#probe .mx-figure svg").count() == 1
        assert page.locator("#probe .mx-figure svg .s, #probe .mx-figure svg .d").count() >= 1   # a shape was drawn
        assert page.locator("#probe .mx-figure text.v").count() >= 1                             # with its point names
        assert page.locator("#probe .mx-plot svg path.c").count() == 1
        assert page.locator("#probe .mx-plot svg circle").count() == len(graph["graph"]["points"])
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()


def test_every_figure_and_graph_in_the_bank_can_be_drawn():
    drawn = [q for q in bank_questions() if "figure" in q or "graph" in q]
    assert len(drawn) == 463
    with running(create_app()) as url, playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = offline_formulas(browser.new_page())
        page.goto(url)
        failures = page.evaluate("""async (questions) => {
            const { figures } = await import('/static/figures.js');
            const bad = [];
            questions.forEach((q, i) => {
                try {
                    const holder = document.createElement('div');
                    holder.innerHTML = figures(q);
                    if (!holder.querySelector('svg')) bad.push(i + ': no svg');
                    if (/NaN|undefined|Infinity/.test(holder.innerHTML)) bad.push(i + ': bad number');
                } catch (error) { bad.push(i + ': ' + error.message); }
            });
            return bad;
        }""", drawn)
        browser.close()
    assert failures == []
