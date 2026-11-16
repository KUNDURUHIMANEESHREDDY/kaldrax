import pytest

from kaldrax.memory import MemoryRecord, MemoryStatus, MemoryType, SQLiteMemoryStore


def _record(content, *, agent_id=None):
    return MemoryRecord.create(
        project_id="project",
        memory_type=MemoryType.SEMANTIC,
        content=content,
        status=MemoryStatus.ACTIVE,
        agent_id=agent_id,
    )


def test_detects_opposing_policy_words_beyond_negation(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.save(_record("Rule: allow background workers to access the repository index"))
    store.save(_record(
        "Rule: deny background workers access to the repository index",
        agent_id="agent-a",
    ))

    conflicts = store.detect_conflicts("project")
    assert len(conflicts) == 1
    assert "availability" in conflicts[0].reason
    assert "subject Jaccard=" in conflicts[0].reason
    store.close()


def test_detects_local_vs_cloud_and_sync_vs_async_conflicts(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.save(_record("Decision: store project credentials in local encrypted memory"))
    store.save(_record("Decision: store project credentials in cloud encrypted memory"))
    store.save(_record("Rule: worker task processing must remain asynchronous"))
    store.save(_record("Rule: worker task processing must remain synchronous"))

    conflicts = store.detect_conflicts("project")
    assert len(conflicts) == 2
    assert all("Heuristic candidate only" in item.reason for item in conflicts)
    store.close()


def test_does_not_flag_disjoint_environment_scopes(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.save(_record("Rule: expose the public admin endpoint in production"))
    store.save(_record("Rule: keep the private admin endpoint in staging"))

    assert store.detect_conflicts("project") == []
    store.close()


def test_does_not_flag_unrelated_opposing_words(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.save(_record("Rule: enable local cache invalidation for user profiles"))
    store.save(_record("Rule: disable remote email delivery for notifications"))

    assert store.detect_conflicts("project") == []
    store.close()


def test_embedding_similarity_can_recall_paraphrased_conflict_candidates(tmp_path):
    class RelatedEmbedder:
        model_id = "contradiction-test"

        def embed(self, texts):
            return [[1.0, 0.0, 0.0] for _ in texts]

    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3", embedder=RelatedEmbedder())
    store.save(_record("Rule: expose the tenant record endpoint to the public"))
    store.save(_record("Rule: keep customer information behind an internal route"))

    conflicts = store.detect_conflicts("project")
    assert len(conflicts) == 1
    assert "visibility" in conflicts[0].reason
    assert "semantic similarity=1.00" in conflicts[0].reason
    store.close()


def test_conflicts_remain_project_and_agent_scoped(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.save(_record("Rule: allow scheduled worker access to private artifacts", agent_id="agent-a"))
    store.save(_record("Rule: deny scheduled worker access to private artifacts", agent_id="agent-b"))

    assert store.detect_conflicts("project") == []
    store.close()

def test_environment_aliases_refer_to_the_same_scope(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.save(_record("Rule: expose the public admin endpoint in production"))
    store.save(_record("Rule: keep the private admin endpoint in prod"))

    conflicts = store.detect_conflicts("project")
    assert len(conflicts) == 1
    store.close()


def test_embedding_provider_failure_falls_back_to_lexical_conflicts(tmp_path):
    class BrokenEmbedder:
        model_id = "broken"

        def embed(self, texts):
            raise RuntimeError("local model is unavailable")

    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3", embedder=BrokenEmbedder())
    store.save(_record("Rule: allow worker agents to access shared project artifacts"))
    store.save(_record("Rule: deny worker agents access to shared project artifacts"))

    conflicts = store.detect_conflicts("project")
    assert len(conflicts) == 1
    assert "semantic similarity=unavailable" in conflicts[0].reason
    store.close()

@pytest.mark.parametrize(("dimension", "first", "second"), [
    ("availability", "allow", "deny"),
    ("visibility", "public", "private"),
    ("location", "local", "cloud"),
    ("connectivity", "connected", "disconnected"),
    ("execution", "synchronous", "asynchronous"),
    ("mutability", "writable", "immutable"),
    ("retention", "retain", "delete"),
    ("membership", "include", "exclude"),
    ("obligation", "required", "optional"),
    ("operation", "accept", "reject"),
    ("automation", "automatic", "manual"),
    ("transport_security", "encrypted", "plaintext"),
    ("strictness", "fail_closed", "fail_open"),
])
def test_all_opposition_dimensions_are_detected(tmp_path, dimension, first, second):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.save(_record(f"Rule: {first} project artifact storage"))
    store.save(_record(f"Rule: {second} project artifact storage"))

    conflicts = store.detect_conflicts("project")
    assert len(conflicts) == 1
    assert dimension in conflicts[0].reason
    store.close()
