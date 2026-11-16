"""Independent deterministic acceptance-criteria evaluator."""
from .models import Evaluation, Task

class CriteriaEvaluator:
    name = "deterministic-criteria-v1"

    def evaluate(self, task: Task, candidate: str) -> Evaluation:
        normalized = candidate.casefold()
        satisfied = tuple(c for c in task.acceptance_criteria if c.casefold() in normalized)
        missing = tuple(c for c in task.acceptance_criteria if c.casefold() not in normalized)
        return Evaluation(not missing, satisfied, missing, self.name)
