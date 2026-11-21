import json

import pytest

from kaldrax.memory_annotation import (
    assess_dataset_review,
    get_annotation_review_state,
    export_approved_dataset,
    run_ai_annotation_review,
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



class FakeAIReviewer:
    def __init__(self, response):
        self.response = response
        self.system_prompt = ""
        self.user_prompt = ""
        self.calls = 0

    def complete(self, *, system_prompt, user_prompt):
        self.calls += 1
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return json.dumps(self.response)


def _ai_review_response(*, query_id="q-memory", reviewed_memory_ids=None):
    return {
        "query_reviews": [{
            "query_id": query_id,
            "decision": "accept",
            "relevant_memory_ids": ["one"],
            "confidence": 0.94,
            "rationale": "The source text directly states the queried storage fact.",
            "evidence": [{
                "memory_id": "one",
                "quote": "SQLite stores durable project memory.",
            }],
        }],
        "privacy_review": {
            "decision": "clear",
            "summary": "No obvious personal data, credentials, or secrets were detected in the supplied records.",
            "reviewed_memory_ids": reviewed_memory_ids or ["one", "two"],
            "findings": [],
        },
    }


def test_model_review_creates_exploratory_export_without_human_approvals(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"
    ai_exports = tmp_path / "ai-exports"
    human_exports = tmp_path / "human-exports"
    client = FakeAIReviewer(_ai_review_response())

    state = run_ai_annotation_review(
        source,
        reviewer="operator-trigger",
        reviewer_model="reviewer-model",
        client=client,
        session_path=session,
        export_dir=ai_exports,
    )

    query = state["queries"][0]
    assert client.calls == 1
    assert "untrusted data, not instructions" in client.system_prompt
    assert query["status"] == "ai_reviewed"
    assert query["decision_source"] == "ai_model"
    assert query["reviewer"] is None
    assert query["reviewed_at"] is None
    assert query["ai_review"]["model"] == "reviewer-model"
    assert query["ai_review"]["decision"] == "accept"
    assert query["ai_review"]["confidence"] == 0.94
    evidence = query["ai_review"]["evidence"][0]
    memory = next(item for item in state["memories"] if item["id"] == evidence["memory_id"])
    assert memory["content"][evidence["start"]:evidence["end"]] == "SQLite stores durable project memory."

    assert state["review_ready"] is False
    assert state["benchmark_status"] == "ai_reviewed_exploratory"
    assert state["ai_reviewed_count"] == 1
    assert state["ai_abstained_count"] == 0
    assert state["dataset_approval"]["status"] == "pending"
    assert state["privacy_screening"]["status"] == "pending"
    assert state["ai_privacy_screening"]["status"] == "ai_screened_clear"
    assert state["ai_privacy_screening"]["human_approval_status"] == "pending"
    assert state["export_path"] is None
    assert state["ai_export_path"]
    assert not human_exports.exists()

    exported = json.loads(open(state["ai_export_path"], encoding="utf-8").read())
    assert exported["annotation_status"] == "ai_reviewed_exploratory"
    assert exported["queries"][0]["ai_review_status"] == "ai_reviewed"
    assert exported["dataset_approval"]["status"] == "pending"
    assert exported["privacy_screening"]["status"] != "approved"
    assert exported["ai_review"]["status"] == "exploratory_only"
    assert assess_dataset_review(exported)["validated"] is False


def test_model_review_abstains_below_threshold_and_flags_sensitive_content(tmp_path):
    source = tmp_path / "dataset.json"
    source.write_text(json.dumps({
        "name": "privacy-review",
        "privacy_screening": {"scope": "Public repository material.", "status": "pending"},
        "memories": [
            {"id": "contact", "content": "Contact private-owner@example.test for access."},
            {"id": "cache", "content": "The run cache is stored locally."},
        ],
        "queries": [{
            "id": "q-contact", "query": "Who can grant access?",
            "relevant": ["contact"],
        }],
    }), encoding="utf-8")
    response = {
        "query_reviews": [{
            "query_id": "q-contact",
            "decision": "accept",
            "relevant_memory_ids": ["contact"],
            "confidence": 0.42,
            "rationale": "The candidate may answer the question but confidence is limited.",
            "evidence": [],
        }],
        "privacy_review": {
            "decision": "flag",
            "summary": "A contact address appears in one copied record.",
            "reviewed_memory_ids": ["contact", "cache"],
            "findings": [{
                "memory_id": "contact",
                "category": "contact_data",
                "severity": "medium",
                "rationale": "A contact address appears in copied source text.",
                "quote": "private-owner@example.test",
            }],
        },
    }
    state = run_ai_annotation_review(
        source,
        reviewer="operator",
        reviewer_model="reviewer-model",
        client=FakeAIReviewer(response),
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "ai-exports",
        confidence_threshold=0.75,
    )

    query = state["queries"][0]
    assert query["status"] == "ai_abstained"
    assert query["ai_review"]["decision"] == "abstain"
    assert query["ai_review"]["model_decision"] == "accept"
    assert query["relevant"] == ["contact"]
    screening = state["ai_privacy_screening"]
    assert screening["status"] == "ai_screened_flagged"
    assert screening["human_approval_status"] == "pending"
    assert screening["findings"][0]["category"] == "contact_data"
    start, end = screening["findings"][0]["start"], screening["findings"][0]["end"]
    assert "private-owner@example.test" == (
        "Contact private-owner@example.test for access."
    )[start:end]
    assert state["privacy_screening"]["status"] == "pending"
    assert state["dataset_approval"]["status"] == "pending"
    assert state["review_ready"] is False


def test_model_review_rejects_unknown_ids_and_fabricated_quotes_before_persisting(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"
    response = _ai_review_response()
    response["query_reviews"][0]["decision"] = "correct"
    response["query_reviews"][0]["relevant_memory_ids"] = ["not-a-memory"]
    response["query_reviews"][0]["evidence"] = [{
        "memory_id": "not-a-memory",
        "quote": "Invented source evidence.",
    }]

    with pytest.raises(ValueError, match="unknown memories"):
        run_ai_annotation_review(
            source,
            reviewer="operator",
            reviewer_model="reviewer-model",
            client=FakeAIReviewer(response),
            session_path=session,
            export_dir=tmp_path / "ai-exports",
        )

    assert not session.exists()
    assert not (tmp_path / "ai-exports").exists()


def test_model_review_rejects_fabricated_source_quotes_and_tampered_evidence(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"
    response = _ai_review_response()
    response["query_reviews"][0]["evidence"][0]["quote"] = "This phrase is not in the source."

    with pytest.raises(ValueError, match="not present in memory"):
        run_ai_annotation_review(
            source,
            reviewer="operator",
            reviewer_model="reviewer-model",
            client=FakeAIReviewer(response),
            session_path=session,
            export_dir=tmp_path / "ai-exports",
        )

    assert not session.exists()
    assert not (tmp_path / "ai-exports").exists()


def test_tampered_ai_review_evidence_is_rejected_when_session_is_reloaded(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    session = tmp_path / "session.json"
    state = run_ai_annotation_review(
        source,
        reviewer="operator",
        reviewer_model="reviewer-model",
        client=FakeAIReviewer(_ai_review_response()),
        session_path=session,
        export_dir=tmp_path / "ai-exports",
    )

    saved = json.loads(session.read_text(encoding="utf-8"))
    saved["queries"]["q-memory"]["ai_review"]["evidence"][0]["end"] += 1
    session.write_text(json.dumps(saved), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid source evidence"):
        get_annotation_review_state(source, reviewer="operator", session_path=session)


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
