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


def test_structured_quality_review_requires_human_case_and_separate_dataset_approvals(tmp_path):
    from kaldrax.memory_quality_review import (
        get_quality_review_state,
        update_quality_review,
    )

    contradiction = _write(tmp_path / "contradiction.json", {
        "name": "contradictions",
        "cases": [
            {"id": "c1", "left": "allow", "right": "deny", "expected_conflict": False},
            {"id": "c2", "left": "sync", "right": "async", "expected_conflict": True},
        ],
    })
    extraction = _write(tmp_path / "extraction.json", {
        "name": "extraction",
        "cases": [
            {
                "id": "e1", "objective": "store data", "candidate": "Use SQLite.",
                "expected": [{"match_terms": ["sqlite"]}],
            },
        ],
    })
    session = tmp_path / "quality-session.json"
    export_dir = tmp_path / "reviewed"

    state = get_quality_review_state(
        contradiction, extraction, reviewer="reviewer-a", session_path=session,
    )
    assert state["status"] == "review_pending"
    assert state["contradiction"]["reviewed"] == 0
    assert state["extraction"]["approval"]["status"] == "pending"

    state = update_quality_review(
        contradiction, extraction, reviewer="reviewer-a",
        action="case", kind="contradiction", case_id="c1", decision="modify",
        expected_conflict=True, note="The two rules are mutually exclusive.",
        session_path=session, export_dir=export_dir,
    )
    assert state["contradiction"]["cases"][0]["expected_conflict"] is True
    assert state["contradiction"]["cases"][0]["review_status"] == "modified"
    assert state["contradiction"]["approval"]["status"] == "pending"

    import pytest
    with pytest.raises(ValueError, match="all contradiction cases"):
        update_quality_review(
            contradiction, extraction, reviewer="reviewer-a",
            action="dataset-approval", kind="contradiction", approval="approve",
            confirmation="APPROVE CONTRADICTION",
            session_path=session, export_dir=export_dir,
        )

    state = update_quality_review(
        contradiction, extraction, reviewer="reviewer-a",
        action="case", kind="contradiction", case_id="c2", decision="approve",
        session_path=session, export_dir=export_dir,
    )
    state = update_quality_review(
        contradiction, extraction, reviewer="reviewer-a",
        action="case", kind="extraction", case_id="e1", decision="modify",
        expected_claims=[{"match_terms": ["sqlite", "database"]}],
        note="The expected claim should identify the storage engine.",
        session_path=session, export_dir=export_dir,
    )

    with pytest.raises(ValueError, match="type APPROVE CONTRADICTION"):
        update_quality_review(
            contradiction, extraction, reviewer="reviewer-a",
            action="dataset-approval", kind="contradiction", approval="approve",
            confirmation="APPROVE", session_path=session, export_dir=export_dir,
        )

    state = update_quality_review(
        contradiction, extraction, reviewer="reviewer-a",
        action="dataset-approval", kind="contradiction", approval="approve",
        confirmation="APPROVE CONTRADICTION",
        session_path=session, export_dir=export_dir,
    )
    assert state["contradiction"]["approval"]["status"] == "approved"
    assert state["contradiction"]["export_path"]
    assert state["extraction"]["approval"]["status"] == "pending"
    assert state["status"] == "review_pending"

    state = update_quality_review(
        contradiction, extraction, reviewer="reviewer-a",
        action="dataset-approval", kind="extraction", approval="approve",
        confirmation="APPROVE EXTRACTION",
        session_path=session, export_dir=export_dir,
    )
    assert state["status"] == "validated_exported"

    exported_c = json.loads(
        open(state["contradiction"]["export_path"], encoding="utf-8").read()
    )
    exported_e = json.loads(
        open(state["extraction"]["export_path"], encoding="utf-8").read()
    )
    assert exported_c["annotation_status"] == "human_reviewed"
    assert exported_c["cases"][0]["expected_conflict"] is True
    assert exported_e["cases"][0]["expected"][0]["match_terms"] == ["sqlite", "database"]
    assert exported_e["cases"][0]["reviewer"] == "reviewer-a"


def test_structured_quality_review_is_bound_to_reviewer_and_source_hashes(tmp_path):
    import pytest
    from kaldrax.memory_quality_review import (
        get_quality_review_state,
        update_quality_review,
    )

    contradiction = _write(tmp_path / "contradiction.json", {
        "cases": [{"id": "c1", "left": "a", "right": "b", "expected_conflict": True}],
    })
    extraction = _write(tmp_path / "extraction.json", {
        "cases": [{"id": "e1", "objective": "x", "candidate": "y", "expected": [{"match_terms": ["y"]}]}],
    })
    session = tmp_path / "session.json"
    get_quality_review_state(
        contradiction, extraction, reviewer="reviewer-a", session_path=session,
    )

    with pytest.raises(ValueError, match="different reviewer"):
        get_quality_review_state(
            contradiction, extraction, reviewer="reviewer-b", session_path=session,
        )

    update_quality_review(
        contradiction, extraction, reviewer="reviewer-a", action="case",
        kind="contradiction", case_id="c1", decision="approve", session_path=session,
    )
    extraction.write_text(extraction.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source datasets changed"):
        get_quality_review_state(
            contradiction, extraction, reviewer="reviewer-a", session_path=session,
        )


def test_structured_quality_review_rejects_invalid_labels(tmp_path):
    import pytest
    from kaldrax.memory_quality_review import (
        get_quality_review_state,
        update_quality_review,
    )

    contradiction = _write(tmp_path / "contradiction.json", {
        "cases": [{"id": "c1", "left": "a", "right": "b", "expected_conflict": True}],
    })
    extraction = _write(tmp_path / "extraction.json", {
        "cases": [{"id": "e1", "objective": "x", "candidate": "y", "expected": [{"match_terms": ["y"]}]}],
    })
    session = tmp_path / "session.json"
    get_quality_review_state(
        contradiction, extraction, reviewer="r", session_path=session,
    )
    with pytest.raises(ValueError, match="boolean"):
        update_quality_review(
            contradiction, extraction, reviewer="r", action="case",
            kind="contradiction", case_id="c1", decision="modify",
            expected_conflict="yes", session_path=session,
        )
    with pytest.raises(ValueError, match="match_terms"):
        update_quality_review(
            contradiction, extraction, reviewer="r", action="case",
            kind="extraction", case_id="e1", decision="modify",
            expected_claims=[{"match_terms": [" "]}], session_path=session,
        )
