"""The evaluation question files are data the results docs depend on - keep them well-formed."""
import json
from pathlib import Path

import pytest

QUESTIONS = Path(__file__).resolve().parent.parent / "eval" / "questions"
COUNTS = {"report": 15, "visual": 21, "long": 15}


def load(mode):
    return json.loads((QUESTIONS / f"{mode}.json").read_text())


@pytest.mark.parametrize("mode", COUNTS)
def test_question_count_and_unique_ids(mode):
    questions = load(mode)

    assert len(questions) == COUNTS[mode]
    ids = [q["id"] for q in questions]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("mode", COUNTS)
def test_every_question_has_text_and_a_way_to_be_judged(mode):
    for q in load(mode):
        assert q["question"].strip(), q["id"]
        expects_refusal = q.get("refusal") or q.get("expect_refusal")
        checks = q.get("must_contain") or q.get("must")
        assert expects_refusal or checks, f"{q['id']} has nothing to judge the answer by"


@pytest.mark.parametrize("mode", COUNTS)
def test_required_strings_are_non_empty_strings(mode):
    for q in load(mode):
        for key in ("must_contain", "must", "must_not"):
            for item in q.get(key) or []:
                options = item if isinstance(item, list) else [item]  # a nested list = any one of these
                assert options and all(isinstance(s, str) and s.strip() for s in options), (q["id"], key)


@pytest.mark.parametrize("mode", COUNTS)
def test_there_are_core_questions_and_gold_pages_are_positive_ints(mode):
    questions = load(mode)

    assert sum(1 for q in questions if q.get("core")) >= 3
    for q in questions:
        assert all(isinstance(p, int) and p > 0 for p in q.get("gold_pages") or []), q["id"]
