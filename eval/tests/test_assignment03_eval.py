from run_eval import faithfulness, gate, summarise


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
