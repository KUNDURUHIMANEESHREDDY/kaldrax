"""Labeled evaluation for contradiction-candidate detection."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .memory import MemoryRecord, MemoryType
from .memory_contradictions import find_contradiction_candidates

def run_contradiction_benchmark(dataset_path: str | Path, *, embedder: Any | None = None) -> dict[str, Any]:
    try:
        dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read contradiction benchmark: {type(exc).__name__}") from None
    if not isinstance(dataset, dict) or not isinstance(dataset.get("cases"), list) or not dataset["cases"]:
        raise ValueError("contradiction benchmark requires a non-empty cases array")
    results, totals, categories = [], dict.fromkeys(("tp","fp","fn","tn"),0), {}
    for case in dataset["cases"]:
        if not isinstance(case, dict): raise ValueError("each contradiction case must be an object")
        cid, left, right, expected = case.get("id"), case.get("left"), case.get("right"), case.get("expected_conflict")
        if not isinstance(cid,str) or not cid.strip() or not isinstance(left,str) or not left.strip() or not isinstance(right,str) or not right.strip() or not isinstance(expected,bool):
            raise ValueError("each case requires id, left, right, and boolean expected_conflict")
        records = [MemoryRecord.create(project_id="contradiction-benchmark",memory_type=MemoryType.SEMANTIC,content=value,status="active") for value in (left,right)]
        candidates = find_contradiction_candidates(records,embedder=embedder)
        predicted = bool(candidates)
        key = "tp" if expected and predicted else "fn" if expected else "fp" if predicted else "tn"
        totals[key] += 1
        category = str(case.get("category","uncategorized"))
        group = categories.setdefault(category,dict.fromkeys(("tp","fp","fn","tn"),0))
        group[key] += 1
        results.append({"id":cid,"category":category,"expected_conflict":expected,"predicted_conflict":predicted,"outcome":key.upper(),"reason":candidates[0][2] if candidates else None})
    def metrics(counts):
        tp,fp,fn,tn=(counts[k] for k in ("tp","fp","fn","tn"))
        p=tp/(tp+fp) if tp+fp else 0.0
        r=tp/(tp+fn) if tp+fn else 0.0
        return {"true_positives":tp,"false_positives":fp,"false_negatives":fn,"true_negatives":tn,"precision":round(p,4),"recall":round(r,4),"f1":round(2*p*r/(p+r),4) if p+r else 0.0}
    return {"dataset":str(dataset_path),"dataset_name":str(dataset.get("name",Path(dataset_path).stem)),"provenance":dataset.get("provenance","unspecified"),"annotation_status":dataset.get("annotation_status","unspecified"),"benchmark_validation":"exploratory_only" if dataset.get("annotation_status")!="human_reviewed" else "human_reviewed","case_count":len(results),**metrics(totals),"by_category":{k:metrics(v) for k,v in sorted(categories.items())},"cases":results,"interpretation":"Heuristic candidate detection; metrics apply only to these labels and never imply automatic resolution."}
