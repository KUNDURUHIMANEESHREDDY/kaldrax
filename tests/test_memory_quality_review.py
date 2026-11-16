import json

from kaldrax.memory_quality_review import run_quality_label_review


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_review_edits_labels_and_exports_hash_addressed_human_reviewed_files(tmp_path):
    contradiction = _write(tmp_path / "contradiction.json", {
        "name": "contradictions",
        "cases": [{"id": "c1", "left": "allow", "right": "deny", "expected_conflict": False}],
    })
    extraction = _write(tmp_path / "extraction.json", {
        "name": "extraction",
        "cases": [{"id": "e1", "objective": "fact", "candidate": "SQLite", "expected": [{"match_terms": ["sqlite"]}]}],
    })
    answers = iter(["t", "e", '[{"match_terms":["sqlite","durable"]}]', "APPROVE CONTRADICTION", "APPROVE EXTRACTION"])
    result = run_quality_label_review(
        contradiction, extraction, reviewer="human-reviewer",
        session_path=tmp_path / "session.json", export_dir=tmp_path / "reviewed",
        input_fn=lambda _: next(answers), output_fn=lambda _: None,
    )
    assert result["status"] == "complete"
    reviewed_c = json.loads(open(result["exports"]["contradiction"], encoding="utf-8").read())
    reviewed_e = json.loads(open(result["exports"]["extraction"], encoding="utf-8").read())
    assert reviewed_c["cases"][0]["expected_conflict"] is True
    assert reviewed_e["cases"][0]["expected"][0]["match_terms"] == ["sqlite", "durable"]
    assert reviewed_c["annotation_status"] == "human_reviewed"
    assert reviewed_e["cases"][0]["review_status"] == "modified"


def test_review_quit_is_resumable_and_does_not_export(tmp_path):
    contradiction = _write(tmp_path / "contradiction.json", {
        "cases": [{"id": "c1", "left": "a", "right": "b", "expected_conflict": True}],
    })
    extraction = _write(tmp_path / "extraction.json", {
        "cases": [{"id": "e1", "objective": "x", "candidate": "y", "expected": [{"match_terms": ["y"]}]}],
    })
    session = tmp_path / "session.json"
    first = run_quality_label_review(
        contradiction, extraction, reviewer="r", session_path=session,
        export_dir=tmp_path / "out", input_fn=lambda _: "q", output_fn=lambda _: None,
    )
    assert first["status"] == "incomplete"
    assert not list((tmp_path / "out").glob("*.json")) if (tmp_path / "out").exists() else True
    answers = iter(["a", "a", "APPROVE CONTRADICTION", "APPROVE EXTRACTION"])
    second = run_quality_label_review(
        contradiction, extraction, reviewer="r", session_path=session,
        export_dir=tmp_path / "out", input_fn=lambda _: next(answers), output_fn=lambda _: None,
    )
    assert second["status"] == "complete"


def test_review_session_rejects_changed_source_dataset(tmp_path):
    contradiction = _write(tmp_path / "contradiction.json", {
        "cases": [{"id": "c1", "left": "a", "right": "b", "expected_conflict": True}],
    })
    extraction = _write(tmp_path / "extraction.json", {
        "cases": [{"id": "e1", "objective": "x", "candidate": "y", "expected": [{"match_terms": ["y"]}]}],
    })
    session = tmp_path / "session.json"
    run_quality_label_review(
        contradiction, extraction, reviewer="r", session_path=session,
        input_fn=lambda _: "q", output_fn=lambda _: None,
    )
    contradiction.write_text(contradiction.read_text() + "\n", encoding="utf-8")
    try:
        run_quality_label_review(
            contradiction, extraction, reviewer="r", session_path=session,
            input_fn=lambda _: "a", output_fn=lambda _: None,
        )
    except ValueError as exc:
        assert "source datasets changed" in str(exc)
    else:
        raise AssertionError("changed source must invalidate the review session")
