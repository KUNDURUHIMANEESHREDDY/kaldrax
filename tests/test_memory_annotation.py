import json

import pytest

from kaldrax.memory_annotation import (
    assess_dataset_review,
    get_annotation_review_state,
    export_approved_dataset,
    run_annotation_review,
    verify_dataset_integrity,
)
from kaldrax.memory_benchmarks import run_retrieval_benchmark


def _dataset(path):
    path.write_text(json.dumps({
        "name": "annotation-test",
        "provenance": "public_repository_snapshot",
        "source_revision": "source-revision-1",
        "privacy_screening": {
            "scope": "Public repository files listed in the dataset.",
            "status": "pending_operator_signoff",
            "note": "Review source paths and copied content.",
        },
        "annotation_status": "assistant_proposed_pending_human_review",
        "memories": [
            {"id": "one", "category": "Architecture", "content": "SQLite stores durable project memory.", "summary": "SQLite persistence", "source": {"path": "README.md", "anchor": "memory"}},
            {"id": "two", "category": "Operations", "content": "Docker runs untrusted Python with network disabled.", "summary": "Isolated Docker execution", "source": {"path": "docs/ARCHITECTURE.md", "anchor": "sandbox"}},
        ],
        "queries": [{
            "id": "q-memory",
            "category": "Persistence",
            "query": "Where does KALDRAX persist project memory?",
            "relevant": ["one"],
            "rationale": "Assistant-proposed source match.",
            "annotation_status": "assistant_proposed_pending_human_review",
            "reviewer": None,
        }],
    }), encoding="utf-8")


def _inputs(values):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_human_review_and_privacy_are_separate_gates_and_export_is_immutable(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    result = run_annotation_review(
        source,
        reviewer="reviewer-a",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        version="1.0.0",
        input_fn=_inputs(["e", "two", "The query is about the runtime sandbox.", "a", "s"]),
        output_fn=lambda _line: None,
    )

    assert result["query_status_counts"] == {"modified": 1}
    assert result["dataset_approval_status"] == "approved"
    assert result["privacy_approval_status"] == "pending"
    assert result["export_path"] is None

    session = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert session["queries"]["q-memory"]["reviewer"] == "reviewer-a"
    assert session["queries"]["q-memory"]["reviewed_at"].endswith("Z")
    assert session["dataset_approval"]["status"] == "approved"
    assert session["privacy_screening"]["status"] == "pending"

    second = run_annotation_review(
        source,
        reviewer="privacy-reviewer",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        version="1.0.0",
        input_fn=_inputs(["s", "a", "APPROVE"]),
        output_fn=lambda _line: None,
    )
    assert second["benchmark_status"] == "validated_exported"
    export_path = second["export_path"]
    assert export_path is not None

    exported = json.loads(open(export_path, encoding="utf-8").read())
    assert exported["queries"][0]["relevant"] == ["two"]
    assert exported["queries"][0]["review_status"] == "modified"
    assert exported["queries"][0]["reviewer"] == "reviewer-a"
    assert exported["dataset_approval"]["reviewer"] == "reviewer-a"
    assert exported["privacy_screening"]["reviewer"] == "privacy-reviewer"
    assert verify_dataset_integrity(exported) is True
    assert assess_dataset_review(exported)["validated"] is True

    source_dataset = json.loads(source.read_text(encoding="utf-8"))
    completed_session = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    repeated_path = export_approved_dataset(
        source_dataset,
        completed_session,
        export_dir=tmp_path / "exports",
        version="1.0.0",
    )
    original_bytes = open(export_path, "rb").read()
    assert str(repeated_path) == export_path
    assert repeated_path.read_bytes() == original_bytes


def test_privacy_review_displays_full_content_for_every_memory(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    output = []

    result = run_annotation_review(
        source,
        reviewer="privacy-reviewer",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        input_fn=_inputs(["a", "a", "a", "APPROVE"]),
        output_fn=output.append,
    )

    rendered = "\\n".join(output)
    assert "SQLite stores durable project memory." in rendered
    assert "Docker runs untrusted Python with network disabled." in rendered
    assert "README.md#memory" in rendered
    assert "docs/ARCHITECTURE.md#sandbox" in rendered
    assert result["privacy_approval_status"] == "approved"


def test_rejected_query_blocks_dataset_approval_and_export(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    result = run_annotation_review(
        source,
        reviewer="reviewer-a",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        input_fn=_inputs(["r", "Incorrect proposed label.", "s"]),
        output_fn=lambda _line: None,
    )
    assert result["query_status_counts"] == {"rejected": 1}
    assert result["dataset_approval_status"] == "pending"
    assert result["export_path"] is None
    assert not list((tmp_path / "exports").glob("*.json"))


def test_unreviewed_dataset_is_exploratory_not_validated(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    result = run_retrieval_benchmark(source, k=1)
    assert result["benchmark_validation"]["status"] == "exploratory_only"
    assert result["benchmark_validation"]["validated"] is False
    assert result["benchmark_validation"]["blocking_reasons"]


def test_structured_review_api_requires_separate_privacy_approval(tmp_path):
    from kaldrax.memory_annotation import (
        get_annotation_review_state,
        update_annotation_review,
    )

    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"
    export_dir = tmp_path / "exports"

    state = get_annotation_review_state(source, reviewer="reviewer-a", session_path=session)
    assert state["queries"][0]["status"] == "pending"
    assert state["privacy_screening"]["status"] == "pending"
    assert state["memories"][0]["source"]["path"] == "README.md"

    state = update_annotation_review(
        source, reviewer="reviewer-a", action="query", query_id="q-memory",
        decision="modify", relevant_ids=["two"],
        note="The query refers to the isolated workspace runtime.",
        session_path=session, export_dir=export_dir,
    )
    assert state["queries"][0]["status"] == "modified"
    assert state["queries"][0]["decision_source"] == "human"
    assert state["dataset_approval"]["status"] == "pending"
    assert state["export_path"] is None

    state = update_annotation_review(
        source, reviewer="reviewer-a", action="dataset-approval", approval="approve",
        session_path=session, export_dir=export_dir,
    )
    assert state["dataset_approval"]["status"] == "approved"
    assert state["privacy_screening"]["status"] == "pending"
    assert state["export_path"] is None

    with pytest.raises(ValueError, match="APPROVE"):
        update_annotation_review(
            source, reviewer="privacy-reviewer", action="privacy-approval",
            approval="approve", privacy_confirmation="yes",
            session_path=session, export_dir=export_dir,
        )

    state = update_annotation_review(
        source, reviewer="privacy-reviewer", action="privacy-approval",
        approval="approve", privacy_confirmation="APPROVE",
        session_path=session, export_dir=export_dir,
    )
    assert state["privacy_screening"]["reviewer"] == "privacy-reviewer"
    assert state["benchmark_status"] == "validated_exported"
    assert state["export_path"]
    reloaded = get_annotation_review_state(
        source, reviewer="privacy-reviewer", session_path=session, export_dir=export_dir,
    )
    assert reloaded["export_path"] == state["export_path"]
    exported = json.loads(open(state["export_path"], encoding="utf-8").read())
    assert assess_dataset_review(exported)["validated"] is True


def test_structured_review_api_rejects_unknown_memory_ids_and_resets_approval(tmp_path):
    from kaldrax.memory_annotation import (
        get_annotation_review_state,
        update_annotation_review,
    )

    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"

    with pytest.raises(ValueError, match="unknown memory"):
        update_annotation_review(
            source, reviewer="reviewer-a", action="query", query_id="q-memory",
            decision="modify", relevant_ids=["not-in-dataset"], session_path=session,
        )

    update_annotation_review(
        source, reviewer="reviewer-a", action="query",
        query_id="q-memory", decision="approve", session_path=session,
    )
    approved = update_annotation_review(
        source, reviewer="reviewer-a", action="dataset-approval",
        approval="approve", session_path=session,
    )
    assert approved["dataset_approval"]["status"] == "approved"

    changed = update_annotation_review(
        source, reviewer="reviewer-b", action="query", query_id="q-memory",
        decision="modify", relevant_ids=["two"], session_path=session,
    )
    assert changed["dataset_approval"]["status"] == "pending"
    assert changed["privacy_screening"]["status"] == "pending"



def test_auto_approve_marks_proposals_as_machine_reviewed_without_unlocking_human_gates(tmp_path):
    from kaldrax.memory_annotation import update_annotation_review

    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"
    export_dir = tmp_path / "exports"

    state = update_annotation_review(
        source,
        reviewer="operator-trigger",
        action="auto-approve-proposals",
        session_path=session,
        export_dir=export_dir,
    )

    query = state["queries"][0]
    assert query["status"] == "auto_approved"
    assert query["relevant"] == query["proposed_relevant"] == ["one"]
    assert query["reviewer"] is None
    assert query["reviewed_at"] is None
    assert query["decision_source"] == "automated"
    assert state["auto_approved_count"] == 1
    assert state["review_ready"] is False
    assert state["benchmark_status"] == "machine_reviewed_pending_human"
    assert state["dataset_approval"]["status"] == "pending"
    assert state["privacy_screening"]["status"] == "pending"
    assert state["export_path"] is None
    run = state["automation_runs"][0]
    assert run["policy"] == "accept-source-proposed-relevance-v1"
    assert run["triggered_by"] == "operator-trigger"
    assert run["source_sha256"] == state["source_sha256"]
    assert run["query_ids"] == ["q-memory"]
    assert run["triggered_at"]
    assert not list(export_dir.glob("*.json"))

    with pytest.raises(ValueError, match="every query must be approved or modified"):
        update_annotation_review(
            source, reviewer="operator-trigger", action="dataset-approval",
            approval="approve", session_path=session, export_dir=export_dir,
        )


def test_auto_approved_proposal_requires_human_reconfirmation_before_validation(tmp_path):
    from kaldrax.memory_annotation import update_annotation_review

    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"

    update_annotation_review(
        source, reviewer="operator-trigger", action="auto-approve-proposals",
        session_path=session,
    )
    state = update_annotation_review(
        source, reviewer="human-reviewer", action="query", query_id="q-memory",
        decision="approve", session_path=session,
    )

    query = state["queries"][0]
    assert query["status"] == "approved"
    assert query["decision_source"] == "human"
    assert query["reviewer"] == "human-reviewer"
    assert query["reviewed_at"]
    assert state["review_ready"] is True
    assert state["auto_approved_count"] == 0
    assert state["automation_runs"][0]["query_ids"] == ["q-memory"]
    assert state["dataset_approval"]["status"] == "pending"
    assert state["privacy_screening"]["status"] == "pending"
    assert state["export_path"] is None


def test_auto_approve_preserves_existing_human_decisions_and_rejects_tampered_machine_state(tmp_path):
    from kaldrax.memory_annotation import update_annotation_review

    source = tmp_path / "dataset.json"
    payload = {
        "name": "mixed-review",
        "privacy_screening": {"scope": "Public source only.", "status": "pending"},
        "memories": [
            {"id": "m1", "content": "SQLite stores project data."},
            {"id": "m2", "content": "Docker isolates execution."},
        ],
        "queries": [
            {"id": "q-human", "query": "Where is data stored?", "relevant": ["m1"]},
            {"id": "q-auto", "query": "How is execution isolated?", "relevant": ["m2"]},
        ],
    }
    source.write_text(json.dumps(payload), encoding="utf-8")
    session = tmp_path / "session.json"

    update_annotation_review(
        source, reviewer="human-reviewer", action="query", query_id="q-human",
        decision="approve", session_path=session,
    )
    state = update_annotation_review(
        source, reviewer="operator-trigger", action="auto-approve-proposals",
        session_path=session,
    )

    assert [query["status"] for query in state["queries"]] == ["approved", "auto_approved"]
    assert state["queries"][0]["reviewer"] == "human-reviewer"
    assert state["queries"][1]["reviewer"] is None
    assert state["review_ready"] is False
    assert state["auto_approved_count"] == 1

    saved = json.loads(session.read_text(encoding="utf-8"))
    saved["queries"]["q-auto"]["decision_source"] = []
    session.write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(ValueError, match="auto-approved query q-auto lacks valid machine provenance"):
        update_annotation_review(
            source, reviewer="operator-trigger", action="auto-approve-proposals",
            session_path=session,
        )




def test_terminal_review_can_human_reconfirm_machine_accepted_proposal(tmp_path):
    from kaldrax.memory_annotation import update_annotation_review

    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"

    update_annotation_review(
        source, reviewer="operator-trigger", action="auto-approve-proposals",
        session_path=session,
    )
    result = run_annotation_review(
        source,
        reviewer="human-reviewer",
        session_path=session,
        input_fn=_inputs(["a", "s", "s"]),
        output_fn=lambda _line: None,
    )

    saved = json.loads(session.read_text(encoding="utf-8"))
    query = saved["queries"]["q-memory"]
    assert query["status"] == "approved"
    assert query["decision_source"] == "human"
    assert query["reviewer"] == "human-reviewer"
    assert query["reviewed_at"]
    assert result["dataset_approval_status"] == "pending"
    assert result["privacy_approval_status"] == "pending"
    assert result["export_path"] is None


def test_auto_approve_rejects_duplicate_proposed_relevance_ids(tmp_path):
    from kaldrax.memory_annotation import update_annotation_review

    source = tmp_path / "dataset.json"
    source.write_text(json.dumps({
        "name": "duplicate-proposal",
        "privacy_screening": {"scope": "Public source only.", "status": "pending"},
        "memories": [{"id": "m1", "content": "One valid source memory."}],
        "queries": [{"id": "q1", "query": "Question?", "relevant": ["m1", "m1"]}],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate relevance IDs"):
        update_annotation_review(
            source, reviewer="operator", action="auto-approve-proposals",
            session_path=tmp_path / "session.json",
        )


def test_tampered_export_fails_integrity_assessment(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    run_annotation_review(
        source,
        reviewer="reviewer-a",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        input_fn=_inputs(["a", "a", "a", "APPROVE"]),
        output_fn=lambda _line: None,
    )
    export_path = next((tmp_path / "exports").glob("*.json"))
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert assess_dataset_review(exported)["validated"] is True
    exported["queries"][0]["query"] = "tampered query"
    assert assess_dataset_review(exported)["validated"] is False

def test_tampered_review_session_approval_and_query_provenance_are_rejected(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    session_path = tmp_path / "session.json"

    get_annotation_review_state(source, reviewer="reviewer-a", session_path=session_path)
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["dataset_approval"] = {
        "status": "approved", "reviewer": None, "reviewed_at": None,
    }
    session_path.write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(ValueError, match="dataset approval lacks valid reviewer provenance"):
        get_annotation_review_state(source, reviewer="reviewer-a", session_path=session_path)

    query_session_path = tmp_path / "query-session.json"
    get_annotation_review_state(source, reviewer="reviewer-a", session_path=query_session_path)
    session = json.loads(query_session_path.read_text(encoding="utf-8"))
    session["queries"]["q-memory"]["status"] = "approved"
    query_session_path.write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed query q-memory lacks valid labels or reviewer provenance"):
        get_annotation_review_state(source, reviewer="reviewer-a", session_path=query_session_path)


def test_tampered_review_session_rejects_unknown_relevance_ids(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    session_path = tmp_path / "session.json"
    get_annotation_review_state(source, reviewer="reviewer-a", session_path=session_path)
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["queries"]["q-memory"]["relevant"] = ["not-in-dataset"]
    session_path.write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid relevance labels"):
        get_annotation_review_state(source, reviewer="reviewer-a", session_path=session_path)
