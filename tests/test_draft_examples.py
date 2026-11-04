"""scripts/draft_examples.py: drafting worked examples for a teacher to review, and merging the approved ones.
The model is a stand-in: nothing here calls the API."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.math_skills import algebra9, problems, skills_without_example

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "draft_examples.py"
spec = importlib.util.spec_from_file_location("draft_examples", SCRIPT)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)

EXAMPLE = {"question": "$(x + 5)(x − 2) = ?$",
           "steps": [{"do": "כופלים כל איבר בכל איבר: $x² − 2x + 5x − 10$", "why": "כך לא שוכחים אף מכפלה."},
                     {"do": "מחברים איברים דומים: $−2x + 5x = 3x$", "why": "רק איברים עם אותה חזקה של $x$ מתחברים."}],
           "answer": "$x² + 3x − 10$"}


class FakeClaude:
    """messages.create answers with `reply` (a dict, or a function of the request's skill name) and keeps the calls."""
    def __init__(self, reply=EXAMPLE, stop_reason="end_turn", text=None):
        self.calls, self.reply, self.stop_reason, self.text = [], reply, stop_reason, text
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        skill = json.loads(kwargs["messages"][0]["content"])["skill"]
        body = self.text if self.text is not None else json.dumps(self.reply(skill) if callable(self.reply) else self.reply)
        return SimpleNamespace(stop_reason=self.stop_reason, model=kwargs["model"],
                               content=[SimpleNamespace(type="text", text=body)])


def test_a_unit_gets_a_well_formed_draft_for_each_skill_without_an_example():
    graph = copy.deepcopy(algebra9())
    graph["skills"][0]["example"] = copy.deepcopy(EXAMPLE)   # t_ext already has one: it is not drafted again
    client = FakeClaude()
    review = script.draft_unit(client, "test-model", graph, "t")
    wanted = [s["id"] for s in graph["skills"] if s["unit"] == "t" and "example" not in s]
    assert list(review["drafts"]) == wanted and "t_ext" not in review["drafts"] and len(client.calls) == len(wanted)
    assert all(d["problems"] == [] and d["example"] == EXAMPLE and d["approved"] is False and d["reviewed_by"] == ""
               for d in review["drafts"].values())
    assert review["unit"] == "t" and review["model"] == "test-model" and "לא נבדקה" in review["status"]


def test_the_request_gives_the_model_the_skill_and_asks_for_the_examples_structure():
    graph = algebra9()
    client = FakeClaude()
    script.draft_unit(client, "test-model", graph, "t", only=["t_ext"])
    (call,) = client.calls
    assert call["model"] == "test-model" and call["system"] == script.SYSTEM and call["max_tokens"] == 8000
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": script.EXAMPLE_SCHEMA}
    assert call["output_config"]["effort"] == "high"
    assert not {"thinking", "temperature", "top_p", "top_k", "tool_choice"} & set(call)   # removed or rejected on current models
    brief = json.loads(call["messages"][0]["content"])
    skill = next(s for s in graph["skills"] if s["id"] == "t_ext")
    assert brief["skill"] == skill["name"] and len(brief["practice_questions"]) == len(skill["questions"])
    first = brief["practice_questions"][0]
    assert first["right_answer"] == "$x² − 2x − 15$" and first["common_mistakes"][0]["tip"]


def test_a_draft_that_breaks_the_rules_says_what_is_wrong():
    graph = algebra9()
    skill = next(s for s in graph["skills"] if s["id"] == "t_ext")
    copied = {**EXAMPLE, "question": skill["questions"][1]["question"]}
    review = script.draft_unit(FakeClaude(copied), "m", graph, "t", only=["t_ext"])
    assert review["drafts"]["t_ext"]["problems"] == ["t_ext example: repeats one of the skill's practice questions"]
    review = script.draft_unit(FakeClaude({**EXAMPLE, "steps": []}), "m", graph, "t", only=["t_ext"])
    assert review["drafts"]["t_ext"]["problems"] == ["t_ext example: needs at least one step"]


@pytest.mark.parametrize("client,expected", [
    (FakeClaude(stop_reason="refusal"), "stop_reason=refusal"),
    (FakeClaude(stop_reason="max_tokens"), "stop_reason=max_tokens"),
    (FakeClaude(text="not json"), "the answer was not JSON")])
def test_a_skill_the_model_cannot_draft_is_reported_and_the_others_go_on(client, expected):
    review = script.draft_unit(client, "m", algebra9(), "t", limit=2)
    drafts = review["drafts"]
    assert len(drafts) == 2 and all(d["example"] is None and expected in d["problems"][0] for d in drafts.values())


def test_the_command_writes_a_review_file_and_never_the_data_file(tmp_path, monkeypatch, capsys):
    data = script.GRAPH.read_bytes()
    client = FakeClaude()
    monkeypatch.setattr(script, "photo_client", lambda key: client)
    monkeypatch.setattr(script, "math_model", lambda: "test-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    out = tmp_path / "t.json"
    assert script.main(["draft", "--unit", "t", "--out", str(out)]) == 0
    review = json.loads(out.read_text(encoding="utf-8"))
    assert set(review["drafts"]) == {s["id"] for s in algebra9()["skills"] if s["unit"] == "t"}
    assert script.GRAPH.read_bytes() == data                      # the data file is for the merge step alone
    calls = len(client.calls)
    assert script.main(["draft", "--unit", "t", "--out", str(out)]) == 2   # it may hold a teacher's review
    assert len(client.calls) == calls and "--force" in capsys.readouterr().err
    assert script.main(["draft", "--unit", "t", "--out", str(out), "--force", "--limit", "1"]) == 0
    assert len(json.loads(out.read_text(encoding="utf-8"))["drafts"]) == 1


def test_a_dry_run_and_a_missing_key_call_nothing(tmp_path, monkeypatch, capsys):
    def no_client(key):
        raise AssertionError("the API must not be called")
    monkeypatch.setattr(script, "photo_client", no_client)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    assert script.main(["draft", "--unit", "t", "--dry-run"]) == 0
    assert "dry run: 5 requests" in capsys.readouterr().out
    assert script.main(["draft", "--unit", "t", "--out", str(tmp_path / "x.json")]) == 2
    assert script.main(["draft", "--unit", "nope"]) == 2
    assert not (tmp_path / "x.json").exists()


# ---- merging what a teacher approved
def review_with(**entries):
    return {"drafts": {sid: {"approved": False, "reviewed_by": "", "example": copy.deepcopy(EXAMPLE), "problems": [], **entry}
                       for sid, entry in entries.items()}}


def test_only_approved_and_named_and_valid_drafts_are_merged():
    graph = copy.deepcopy(algebra9())
    practice = next(s for s in graph["skills"] if s["id"] == "t_simplify")["questions"][0]["question"]
    review = review_with(
        t_ext={"approved": True, "reviewed_by": "מורה כהן"},
        t_simplify={"approved": True, "reviewed_by": "מורה כהן", "example": {**EXAMPLE, "question": practice}},   # copies a question
        t_ext_eq={"approved": True},                                  # no reviewer's name
        t_area={},                                                    # not approved
        nope={"approved": True, "reviewed_by": "x"})
    merged_graph, merged, skipped = script.merge_approved(review, graph)
    assert merged == ["t_ext"] and next(s for s in merged_graph["skills"] if s["id"] == "t_ext")["example"] == EXAMPLE
    reasons = dict(line.split(": ", 1) for line in skipped)
    assert "repeats one of the skill's practice questions" in reasons["t_simplify"]
    assert "reviewer's name" in reasons["t_ext_eq"] and reasons["t_area"] == "not approved" and reasons["nope"] == "no such skill"
    assert problems(merged_graph) == []


def test_an_example_already_in_the_data_is_not_overwritten():
    graph = copy.deepcopy(algebra9())
    graph["skills"][0]["example"] = {**EXAMPLE, "answer": "קיים"}
    _, merged, skipped = script.merge_approved(review_with(t_ext={"approved": True, "reviewed_by": "מורה"}), graph)
    assert merged == [] and skipped == ["t_ext: already has an example"]


def test_the_merge_command_changes_only_the_approved_skills_in_the_data_file(tmp_path, monkeypatch, capsys):
    data = tmp_path / "math_algebra9.json"
    original = script.GRAPH.read_text(encoding="utf-8")
    data.write_text(original, encoding="utf-8")
    monkeypatch.setattr(script, "GRAPH", data)
    review = tmp_path / "t.json"
    review.write_text(json.dumps(review_with(t_ext={"approved": True, "reviewed_by": "מורה כהן"}, t_area={})), encoding="utf-8")
    assert script.main(["merge", str(review)]) == 0
    after = json.loads(data.read_text(encoding="utf-8"))
    skill = next(s for s in after["skills"] if s["id"] == "t_ext")
    assert skill["example"] == EXAMPLE and problems(after) == []
    assert "t_area" in skills_without_example(after) and "t_ext" not in skills_without_example(after)
    skill.pop("example")   # nothing else moved: the file is the old one plus that example, in the same format
    assert json.dumps(after, ensure_ascii=False, indent=1) + "\n" == original
    assert script.main(["merge", str(review)]) == 1                # a second time there is nothing to add
    assert "already has an example" in capsys.readouterr().out
