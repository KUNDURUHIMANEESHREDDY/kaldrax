import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PENDING = "assistant_proposed_pending_human_review"


def _dataset(name):
    return json.loads((ROOT / "benchmarks" / name).read_text(encoding="utf-8"))


def test_contradiction_candidate_corpus_meets_balanced_release_sample_floor():
    dataset = _dataset("memory_contradictions_v1.json")
    cases = dataset["cases"]
    assert len(cases) == 50
    assert Counter(case["expected_conflict"] for case in cases) == {True: 25, False: 25}
    assert dataset["annotation_status"] == PENDING
    assert dataset["candidate_expansion"]["added_cases"] == 42
    assert sum(case["candidate_origin"] == "assistant_generated_candidate" for case in cases) == 42
    assert all(case["annotation_status"] == PENDING and case["review_status"] == "pending" for case in cases)
    assert len({case["id"] for case in cases}) == len(cases)


def test_extraction_candidate_corpus_meets_release_case_and_claim_floors():
    dataset = _dataset("memory_extraction_v1.json")
    cases = dataset["cases"]
    expected_claims = [claim for case in cases for claim in case["expected"]]
    assert len(cases) == 30
    assert len(expected_claims) == 70
    assert dataset["annotation_status"] == PENDING
    assert dataset["candidate_expansion"]["added_cases"] == 20
    assert sum(case["candidate_origin"] == "assistant_generated_candidate" for case in cases) == 20
    assert all(case["annotation_status"] == PENDING and case["review_status"] == "pending" for case in cases)
    assert len({case["id"] for case in cases}) == len(cases)


def test_extraction_candidate_labels_are_grounded_in_their_candidate_text():
    dataset = _dataset("memory_extraction_v1.json")
    for case in dataset["cases"]:
        candidate = case["candidate"].casefold()
        for claim in case["expected"]:
            assert claim["match_terms"]
            assert all(term.casefold() in candidate for term in claim["match_terms"]), case["id"]
