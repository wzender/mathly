"""The drafting tool, with a fake AI client: nothing here calls the network or spends money."""
import copy
import json

import anthropic
import httpx
import pytest

from mathly2.bank import BANK_PATH, check_bank, load_bank
from mathly2.scripts import draft_examples as tool


@pytest.fixture(autouse=True)
def the_real_bank_is_never_touched():
    """A test that writes to the real bank would add fake examples to the app's content: fail loudly."""
    before = BANK_PATH.read_bytes()
    yield
    assert BANK_PATH.read_bytes() == before, "a test changed the real exercise bank"


@pytest.fixture
def data():
    return copy.deepcopy(load_bank().data)


def good_model_answer():
    return {"worked_example": {"question": "$x² + 5x + 6$", "answer": "$(x + 2)(x + 3)$", "steps": [
        {"do": "מוצאים 2 ו־3", "why": "כי המכפלה 6 והסכום 5"},
        {"do": "כותבים $(x + 2)(x + 3)$", "why": "כך מפרקים טרינום לגורמים"}]}}


class Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class Response:
    def __init__(self, text, stop="end_turn"):
        self.content, self.stop_reason = [Block(text)], stop


class FakeClient:
    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, Response) else Response(json.dumps(answer, ensure_ascii=False))


def first_without_example(data, lesson="t"):
    return tool.skills_without_examples(data, lesson)[0]


# --- draft ---

def test_a_good_draft_is_in_the_bank_shape_and_has_no_problems(data):
    skill = first_without_example(data)
    client = FakeClient(good_model_answer())
    review = tool.draft_lesson(client, "m", data, "t", only=[skill["id"]])
    entry = review["drafts"][skill["id"]]
    assert entry["problems"] == [] and entry["approved"] is False and entry["reviewed_by"] == ""
    assert set(entry["example"]) == {"worked_example"} and entry["example"]["worked_example"]["steps"][0]["why"] == "כי המכפלה 6 והסכום 5"
    assert client.requests[0]["system"] == tool.SYSTEM


def test_the_schema_asks_for_one_plain_text_example_and_no_faded_ones():
    schema = tool.EXAMPLE_SCHEMA
    assert schema["required"] == ["worked_example"]
    step = schema["properties"]["worked_example"]["properties"]["steps"]["items"]["properties"]
    assert step["why"] == {"type": "string"} and "faded_examples" not in json.dumps(schema)


def test_the_request_shows_the_skill_and_its_common_mistakes(data):
    skill = first_without_example(data)
    client = FakeClient(good_model_answer())
    tool.draft_lesson(client, "m", data, "t", only=[skill["id"]])
    sent = json.loads(client.requests[0]["messages"][0]["content"])
    assert sent["skill"] == skill["name"] and 0 < len(sent["practice_questions"]) <= tool.SAMPLE_QUESTIONS
    assert sent["common_mistakes"] and all({"name", "tip"} <= set(m) for m in sent["common_mistakes"])


def test_a_draft_that_breaks_the_bank_rules_is_flagged(data):
    skill = first_without_example(data)
    answer = good_model_answer()
    answer["worked_example"]["steps"][0]["why"] = ""
    answer["worked_example"]["answer"] = ""
    entry = tool.draft_lesson(FakeClient(answer), "m", data, "t", only=[skill["id"]])["drafts"][skill["id"]]
    assert any("needs a question, steps and an answer" in p for p in entry["problems"])
    assert any("step 1: 'why' must be text" in p for p in entry["problems"])


def test_a_failed_request_becomes_a_problem_not_a_crash(data):
    skills = tool.skills_without_examples(data, "t")[:3]
    error = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.test"))
    client = FakeClient(error, Response("{}", stop="refusal"), Response("not json"))
    review = tool.draft_lesson(client, "m", data, "t", only=[s["id"] for s in skills])
    problems = [review["drafts"][s["id"]]["problems"][0] for s in skills]
    assert all(p.startswith("no draft:") for p in problems)
    assert "stop_reason=refusal" in problems[1] and "not the expected JSON" in problems[2]
    assert all(review["drafts"][s["id"]]["example"] is None for s in skills)


def test_limit_and_only_choose_the_skills(data):
    ids = [s["id"] for s in tool.skills_without_examples(data, "t")]
    assert len(tool.draft_lesson(FakeClient(*[good_model_answer()] * 2), "m", data, "t", limit=2)["drafts"]) == 2
    only = tool.draft_lesson(FakeClient(good_model_answer()), "m", data, "t", only=[ids[1]])
    assert list(only["drafts"]) == [ids[1]]


def test_a_skill_that_already_has_a_solved_example_is_not_drafted(data):
    skill = first_without_example(data)
    skill["worked_example"] = good_model_answer()["worked_example"]
    assert skill["id"] not in [s["id"] for s in tool.skills_without_examples(data, "t")]


# --- merge ---

@pytest.fixture
def bank_copy(tmp_path, monkeypatch):
    path = tmp_path / "bank.json"
    path.write_text(BANK_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(tool, "BANK_PATH", path)
    return path


def three(data):
    return [s["id"] for s in tool.skills_without_examples(data, "t")[:3]]


def review_file(tmp_path, data, approve, reviewer="מורה"):
    drafts = {sid: {"approved": sid in approve, "reviewed_by": reviewer if sid in approve else "",
                    "example": tool.clean(good_model_answer()), "problems": []} for sid in three(data)}
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"drafts": drafts}, ensure_ascii=False), encoding="utf-8")
    return path


def test_merge_adds_only_the_approved_drafts_and_the_bank_still_loads(tmp_path, data, bank_copy, capsys):
    ids = three(data)
    assert tool.main(["merge", str(review_file(tmp_path, data, {ids[0]}))]) == 0
    merged = json.loads(bank_copy.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in merged["skills"]}
    assert by_id[ids[0]]["worked_example"]["steps"][0]["why"] == "כי המכפלה 6 והסכום 5"
    assert "worked_example" not in by_id[ids[1]] and "worked_example" not in by_id[ids[2]]
    assert check_bank(merged) == [] and load_bank(bank_copy)
    out = capsys.readouterr().out
    assert f"added solved examples to bank.json: {ids[0]}" in out and f"{ids[1]}: not approved" in out


def test_merge_leaves_out_an_approval_without_a_reviewer_name(tmp_path, data, bank_copy, capsys):
    before = bank_copy.read_text(encoding="utf-8")
    assert tool.main(["merge", str(review_file(tmp_path, data, {three(data)[0]}, reviewer="  "))]) == 1
    assert "approved without the reviewer's name" in capsys.readouterr().out
    assert bank_copy.read_text(encoding="utf-8") == before


def test_merge_refuses_a_draft_that_breaks_the_rules_even_if_approved(tmp_path, data, bank_copy, capsys):
    ids = three(data)
    path = review_file(tmp_path, data, {ids[0]})
    review = json.loads(path.read_text(encoding="utf-8"))
    review["drafts"][ids[0]]["example"]["worked_example"]["steps"][0]["why"] = ""
    path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    before = bank_copy.read_text(encoding="utf-8")
    assert tool.main(["merge", str(path)]) == 1
    assert "'why' must be text" in capsys.readouterr().out
    assert bank_copy.read_text(encoding="utf-8") == before


def test_merge_never_overwrites_a_skill_that_already_has_a_solved_example(tmp_path, data, bank_copy, capsys):
    path = review_file(tmp_path, data, {three(data)[0]})
    assert tool.main(["merge", str(path)]) == 0
    assert tool.main(["merge", str(path)]) == 1                      # the same review again
    assert "already has a solved example" in capsys.readouterr().out


def test_writing_the_bank_keeps_the_files_own_format():
    assert BANK_PATH.read_text(encoding="utf-8") == json.dumps(load_bank().data, ensure_ascii=False, indent=1) + "\n"


# --- the command line ---

def test_dry_run_sends_nothing_and_needs_no_key(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise AssertionError("the dry run must not create a client")
    monkeypatch.setattr(anthropic, "Anthropic", boom)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    before = BANK_PATH.read_bytes()
    assert tool.main(["draft", "--lesson", "t", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "5 skills without a solved example" in out and "nothing was sent" in out and "system prompt" in out
    assert BANK_PATH.read_bytes() == before


def test_draft_without_a_key_or_with_a_bad_lesson_or_over_a_review_stops(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    assert tool.main(["draft", "--lesson", "nope"]) == 2
    assert tool.main(["draft", "--lesson", "t"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    existing = tmp_path / "review.json"
    existing.write_text("{}", encoding="utf-8")
    assert tool.main(["draft", "--lesson", "t", "--out", str(existing)]) == 2        # may hold a teacher's review
    assert existing.read_text(encoding="utf-8") == "{}"
