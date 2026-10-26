"""The evaluation judge must not pass answers by accident (it once did: a flat must_contain list was
iterated character by character)."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("run_eval", Path(__file__).parent.parent / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)

REFUSAL = "I could not find this in the document."


def test_a_flat_must_contain_list_means_every_string_is_required():
    q = {"must_contain": ["1.6"], "must_not": ["6.3"]}

    assert run_eval.judge(q, "Growth is 1.6 percent in 2026.", REFUSAL)
    assert not run_eval.judge(q, "Pakistan's growth is 3.0 percent for 2026/27.", REFUSAL)  # no '1.6'
    assert not run_eval.judge(q, "The figure is 1.6 percent, not 6.3.", REFUSAL)  # forbidden '6.3'


def test_nested_groups_mean_one_of_each_group():
    q = {"must": [["85"], ["10,214", "10,000"]]}

    assert run_eval.judge(q, "85 webinars with 10,214 registrants", REFUSAL)
    assert run_eval.judge(q, "85 webinars, more than 10,000 participants", REFUSAL)
    assert not run_eval.judge(q, "85 webinars", REFUSAL)


def test_numbers_are_compared_without_thousands_separators_and_percent_wording():
    q = {"must_contain": [["1,737"], ["58%"]]}

    assert run_eval.judge(q, "1737 staff and 58 percent less energy", REFUSAL)


def test_refusals_accept_the_exact_sentence_or_a_clear_decline():
    q = {"refusal": True}

    assert run_eval.judge(q, REFUSAL, REFUSAL)
    assert run_eval.judge(q, "I do not have information about that in the provided documents.", REFUSAL)
    assert not run_eval.judge(q, "The capital of France is Paris.", REFUSAL)


def test_a_refusal_question_can_also_accept_a_named_canned_reply():
    q = {"refusal": True, "refusal_or": ["there is no chapter 7"]}

    assert run_eval.judge(q, "The document has 4 chapters; there is no Chapter 7.", REFUSAL)


def test_an_answer_question_fails_when_the_model_refuses():
    assert not run_eval.judge({"must_contain": ["x"]}, REFUSAL, REFUSAL)
