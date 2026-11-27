from run_eval import faithfulness, gate, summarise
import json
import os

import pytest


def test_faithfulness_uses_context_captured_in_trace():
    response = {"answered_from_context": True, "answer": "Attendance is 80%."}
    trace = {"context": ["Students must maintain attendance of 80 percent."]}
    assert faithfulness(response, trace) == 1.0
    assert faithfulness(response, None) == 0.0
    assert faithfulness({"answered_from_context": False, "answer": ""}, trace) is None


def test_gate_checks_faithfulness_latency_and_abstention_regression():
    result = {
        "recall_at_3": 0.8,
        "recall_at_5": 0.9,
        "citation_validity": 1.0,
        "faithfulness": 0.95,
        "latency_ms_p95": 1000,
        "abstention_rate": 0.9,
    }
    baseline = {"recall_at_5": 0.9, "abstention_rate": 1.0}
    failures = gate(result, baseline)
    assert any("abstention correctness" in failure for failure in failures)
    assert not any("faithfulness" in failure or "latency" in failure for failure in failures)


def test_summary_reports_component_and_end_to_end_metrics():
    rows = [{
        "id": "q1",
        "type": "ordinary",
        "must_abstain": False,
        "relevant": [{"source": "policy.md", "section": "Attendance"}],
        "response": {
            "retrieved": [{"source": "policy.md", "section": "Attendance"}],
            "citations": [{"source": "policy.md", "section": "Attendance", "page": 1}],
            "answered_from_context": True,
        },
        "faithfulness": 1.0,
        "seconds": 0.25,
    }]
    summary = summarise(rows)
    assert summary["mrr"] == 1.0
    assert summary["ndcg_at_5"] == 1.0
    assert summary["latency_ms_p95"] == 250.0
    assert summary["faithfulness"] == 1.0


def test_cluster_suite_evaluates_configured_candidate_top_k(monkeypatch, tmp_path):
    import run_cluster_suite as cluster

    golden = tmp_path / "golden.jsonl"
    golden.write_text(json.dumps({"id": "q1"}) + "\n")
    observed = []
    monkeypatch.setenv("TOP_K", "4")
    monkeypatch.setattr(cluster, "run_module_level", lambda **kw: {})

    def component(*args, **kwargs):
        observed.append(kwargs["top_k"])
        return {"baseline": {}, "noise_test": {}}

    def answers(command, **kwargs):
        from types import SimpleNamespace
        output = command[command.index("--out") + 1]
        assert float(command[command.index('--request-timeout') + 1]) >= 600
        from pathlib import Path
        Path(output).write_text(json.dumps({"faithfulness": 0.0}))
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(cluster, "run_component_level", component)
    monkeypatch.setattr(cluster.subprocess, "run", answers)
    result = cluster.run_suite("http://candidate", golden, tmp_path / "baseline.json",
                               tmp_path / "trace.jsonl", tmp_path / "result.json")
    assert observed == [4, 4]
    assert result["configuration"]["top_k"] == 4
    assert result["gate_status"] == "FAIL"


def test_drift_requires_distinct_collections_and_restores_environment(monkeypatch, tmp_path):
    import drift

    monkeypatch.setenv("CHROMA_COLLECTION", "live")
    with pytest.raises(ValueError, match="distinct"):
        drift.run_drift(tmp_path, tmp_path / "golden", "same", "same")
    observed = []

    def suite(*args):
        observed.append(os.environ["CHROMA_COLLECTION"])
        raise RuntimeError("unavailable")

    monkeypatch.setattr(drift, "run_suite", suite)
    with pytest.raises(RuntimeError, match="unavailable"):
        drift.run_drift(tmp_path, tmp_path / "golden", "before", "after")
    assert observed == ["before"]
    assert os.environ["CHROMA_COLLECTION"] == "live"
