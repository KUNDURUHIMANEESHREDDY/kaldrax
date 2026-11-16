import json

import pytest

from kaldrax.memory import MemoryStatus
from kaldrax.memory_intelligence import LLMMemoryExtractor, MemoryExtractionError
from kaldrax.models import Task


class FakeChatClient:
    def __init__(self, output):
        self.output = output
        self.system_prompt = ""
        self.user_prompt = ""

    def complete(self, *, system_prompt, user_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.output


def test_llm_extractor_requires_candidate_backed_quotes_and_queues_for_review():
    candidate = "Decision: Use SQLite for local persistence. The app remains offline-first."
    payload = {
        "memories": [{
            "content": "Decision: SQLite is the local persistence layer.",
            "summary": "Use SQLite locally.",
            "evidence": "Use SQLite for local persistence.",
            "confidence": 0.82,
            "tags": ["storage", "architecture"],
        }]
    }
    extractor = LLMMemoryExtractor(FakeChatClient(json.dumps(payload)))
    task = Task("Design memory", ("local persistence",), project_id="kaldrax")
    records = extractor.extract(
        task, candidate, source_run_id="run-1", source_event_sequences=(1, 2),
    )
    assert len(records) == 1
    record = records[0]
    assert record.status is MemoryStatus.PENDING
    assert record.confidence == 0.82
    assert record.source_run_id == "run-1"
    assert record.source_event_sequences == (1, 2)
    assert record.metadata["evidence_quote"] in candidate
    assert record.metadata["approval_required"] is True
    assert record.metadata["model_reported_confidence"] == 0.82
    assert "not assumed calibrated" in record.metadata["confidence_semantics"]


@pytest.mark.parametrize("payload", [
    "not-json",
    json.dumps({"other": []}),
    json.dumps({"memories": [{"content": "Fact", "evidence": "fabricated"}]}),
    json.dumps({"memories": [{"content": "Fact", "evidence": "Fact", "confidence": 2.0}]}),
    json.dumps({"memories": [{"content": "A fact", "evidence": "This is the data", "confidence": 0.8}]}),
    json.dumps({"memories": [{"content": "A durable fact", "evidence": "Only candidate evidence is available."}]}),
])
def test_llm_extractor_rejects_unverified_or_malformed_records(payload):
    extractor = LLMMemoryExtractor(FakeChatClient(payload))
    with pytest.raises(MemoryExtractionError):
        extractor.extract(
            Task("Extract facts", ("criteria",)),
            "Only candidate evidence is available.",
            source_run_id="run-1",
            source_event_sequences=(1,),
        )


def test_empty_candidate_produces_no_memory_records():
    client = FakeChatClient("not json")
    extractor = LLMMemoryExtractor(client)
    assert extractor.extract(
        Task("Extract", ("criterion",)), "",
        source_run_id="run-1", source_event_sequences=(),
    ) == []
