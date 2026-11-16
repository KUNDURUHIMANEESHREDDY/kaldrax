from kaldrax.engine import RecursiveEngine
from kaldrax.execution import LLMExecutor
from kaldrax.memory import MemoryMatch, MemoryRecord, MemoryType, SQLiteMemoryStore, WorkingMemory
from kaldrax.models import RunStatus, Task


def test_memory_survives_reopen_and_is_project_scoped(tmp_path):
    database = tmp_path / "memory.sqlite3"
    store = SQLiteMemoryStore(database)
    store.save(MemoryRecord.create(
        project_id="alpha", memory_type=MemoryType.SEMANTIC,
        content="Lesson: use SQLite transactions for durable project memory",
        source_run_id="run-1", tags=("lesson",),
    ))
    store.close()
    reopened = SQLiteMemoryStore(database)
    assert len(reopened.search("durable project memory", project_id="alpha")) == 1
    assert reopened.search("durable project memory", project_id="beta") == []
    reopened.close()


def test_agent_search_sees_own_and_shared_memory_but_not_other_agents(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    for owner in (None, "agent-a", "agent-b"):
        store.save(MemoryRecord.create(
            project_id="project", memory_type=MemoryType.EPISODIC,
            content=f"Build pipeline result for {owner or 'shared'}", agent_id=owner,
        ))
    matches = store.search("build pipeline result", project_id="project", agent_id="agent-a")
    assert {match.record.agent_id for match in matches} == {None, "agent-a"}
    assert len(store.search("build pipeline result", project_id="project")) == 3
    store.close()


def test_consolidation_merges_duplicates_and_preserves_source_runs(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    for run_id in ("run-1", "run-2"):
        store.save(MemoryRecord.create(
            project_id="project", memory_type=MemoryType.SEMANTIC,
            content="Lesson: keep evaluator independent", source_run_id=run_id,
            source_event_sequences=(1, 2),
        ))
    assert store.consolidate("project") == 1
    matches = store.search("evaluator independent", project_id="project")
    assert len(matches) == 1
    assert matches[0].record.metadata["consolidated_source_run_ids"] == ["run-1", "run-2"]
    assert matches[0].record.metadata["consolidated_source_event_sequences"] == [1, 2]
    store.close()


class MemoryAwareExecutor:
    def __init__(self): self.memory_counts = []
    def execute(self, task, feedback, iteration): return "legacy path"
    def execute_with_memory(self, task, context):
        self.memory_counts.append(len(context.retrieved_memories))
        if context.iteration > 1:
            assert context.previous_candidate
        return "Lesson: preserve independent evaluator\nAcceptance passed"


def test_engine_retrieves_prior_memory_and_extracts_explicit_lessons(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    task = Task("Preserve independent evaluator", ("Acceptance passed",), project_id="core")
    executor = MemoryAwareExecutor()
    engine = RecursiveEngine(executor, memory_store=store)
    first = engine.run(task)
    second = engine.run(task)
    assert first.status is RunStatus.PASSED
    assert executor.memory_counts == [0, 2]
    assert store.count(project_id="core") == 4
    semantic = store.search("independent evaluator", project_id="core", memory_types=(MemoryType.SEMANTIC,))
    assert semantic
    assert semantic[0].record.source_run_id in {first.run_id, second.run_id}
    assert semantic[0].record.metadata["extraction_method"] == "explicit_marker_v1"
    store.close()


def test_failed_run_is_stored_as_episode_but_not_semantic_knowledge(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    class IncompleteExecutor:
        def execute(self, task, feedback, iteration): return "still incomplete"
    report = RecursiveEngine(IncompleteExecutor(), memory_store=store).run(
        Task("Build durable memory", ("not present",), max_iterations=1, project_id="p")
    )
    assert report.status is RunStatus.LIMIT_REACHED
    assert store.count(project_id="p") == 1
    assert store.search("durable memory", project_id="p")[0].record.source_run_id == report.run_id
    store.close()


def test_llm_executor_includes_memory_content_and_provenance_in_prompt():
    class FakeChatClient:
        def complete(self, *, system_prompt, user_prompt):
            self.system_prompt = system_prompt
            self.payload = __import__("json").loads(user_prompt)
            return "candidate"
    client = FakeChatClient()
    executor = LLMExecutor(client)
    record = MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC,
        content="Lesson: keep evaluators independent", source_run_id="run-123",
        source_event_sequences=(2, 3),
    )
    context = WorkingMemory(
        run_id="run-current", project_id="p",
        retrieved_memories=(MemoryMatch(record, 0.91),), iteration=1,
    )
    result = executor.execute_with_memory(
        Task("Keep evaluators independent", ("candidate",), project_id="p"), context,
    )
    assert result == "candidate"
    assert client.payload["relevant_memory"][0]["source_run_id"] == "run-123"
    assert client.payload["relevant_memory"][0]["content"] == record.content
    assert client.payload["run_id"] == "run-current"
    assert "untrusted historical data" in client.system_prompt


def test_memory_limit_must_be_positive():
    class StubExecutor:
        def execute(self, task, feedback, iteration): return ""
    try:
        RecursiveEngine(StubExecutor(), memory_limit=0)
    except ValueError as exc:
        assert "memory_limit" in str(exc)
    else:
        raise AssertionError("expected invalid memory limit to be rejected")


def test_consolidation_does_not_merge_agent_private_records(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    for agent in ("agent-a", "agent-b"):
        store.save(MemoryRecord.create(
            project_id="project", memory_type=MemoryType.SEMANTIC,
            content="Lesson: isolated private note", source_run_id=agent, agent_id=agent,
        ))
    assert store.consolidate("project") == 0
    assert len(store.search("isolated private note", project_id="project", agent_id="agent-a")) == 1
    assert len(store.search("isolated private note", project_id="project", agent_id="agent-b")) == 1
    store.close()


def test_memory_search_rejects_invalid_project_or_limit(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    import pytest
    with pytest.raises(ValueError, match="project_id"):
        store.search("something", project_id=" ")
    with pytest.raises(ValueError, match="limit"):
        store.search("something", project_id="project", limit=0)
    store.close()


def test_working_memory_carries_failed_candidate_and_feedback_to_retry():
    class CorrectingExecutor:
        def __init__(self): self.contexts = []
        def execute(self, task, feedback, iteration): return "legacy path"
        def execute_with_memory(self, task, context):
            self.contexts.append((context.iteration, context.feedback, context.previous_candidate))
            return "rough draft" if context.iteration == 1 else "required result is present"

    executor = CorrectingExecutor()
    task = Task("Correct a candidate", ("required result is present",), max_iterations=2)
    report = RecursiveEngine(executor).run(task)
    assert report.status is RunStatus.PASSED
    assert executor.contexts == [
        (1, (), ""),
        (2, ("required result is present",), "rough draft"),
    ]


def test_consolidation_preserves_negation_distinctions(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    store.save(MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC, content="Rule: deploy the release",
    ))
    store.save(MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC, content="Rule: do not deploy the release",
    ))
    assert store.consolidate("p") == 0
    assert store.count(project_id="p") == 2
    store.close()


def test_semantic_extraction_requires_nonempty_explicit_lesson_and_deduplicates():
    from kaldrax.memory import extract_reusable_knowledge
    records = extract_reusable_knowledge(
        project_id="p", source_run_id="run-1", source_event_sequences=(1, 2),
        candidate=(
            "Decision:\n"
            "Lesson: preserve evaluator independence\n"
            "Lesson: Preserve evaluator independence\n"
            "unmarked sentence that looks like advice\n"
            "Rule: keep project memory scoped\n"
        ),
    )
    assert [record.content for record in records] == [
        "Lesson: preserve evaluator independence",
        "Rule: keep project memory scoped",
    ]


def test_task_project_scope_is_backward_compatible_and_validated():
    from pytest import raises
    assert Task("Legacy task", ("criterion",)).project_id == "default"
    with raises(ValueError, match="project_id"):
        Task("Scoped task", ("criterion",), project_id=" ")
