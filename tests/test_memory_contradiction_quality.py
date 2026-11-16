import json
from kaldrax.memory_contradiction_quality import run_contradiction_benchmark

def test_labeled_contradiction_benchmark_reports_false_positives_and_misses(tmp_path):
    path=tmp_path/"pairs.json"
    path.write_text(json.dumps({"name":"fixture","provenance":"synthetic_curated","annotation_status":"assistant_proposed_pending_human_review","cases":[
      {"id":"tp","category":"availability","left":"Rule: allow worker agents to access shared project artifacts","right":"Rule: deny worker agents access to shared project artifacts","expected_conflict":True},
      {"id":"tn","category":"unrelated","left":"Rule: enable local cache invalidation for user profiles","right":"Rule: disable remote email delivery for notifications","expected_conflict":False},
      {"id":"fn","category":"paraphrase","left":"Rule: expose the tenant record endpoint to the public","right":"Rule: keep customer information behind an internal route","expected_conflict":True}
    ]}),encoding="utf-8")
    report=run_contradiction_benchmark(path)
    assert (report["true_positives"],report["false_positives"],report["false_negatives"])==(1,0,1)
    assert report["precision"]==1.0 and report["recall"]==0.5
    assert report["benchmark_validation"]=="exploratory_only"
    assert report["by_category"]["paraphrase"]["false_negatives"]==1
