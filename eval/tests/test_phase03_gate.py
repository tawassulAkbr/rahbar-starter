"""Gate integrity tests use explicit test doubles, never submission evidence."""
from copy import deepcopy

from gate import evaluate


def experiment():
    baseline = {
        'configuration': {'embed_model': 'nomic-embed-text', 'generator': 'test-model', 'top_k': 5},
        'module': {'provider': 'ollama'},
        'component': {'retriever': 'chroma', 'baseline': {'recall_at_5': .8}},
        'end_to_end': {'mode': 'serving-pipeline', 'faithfulness': 1.,
                      'latency_ms_p95': 100., 'abstention_correctness': 1.,
                      'answers': [{'trace_id': 'test-only'}]},
    }
    candidate = deepcopy(baseline)
    candidate['configuration']['top_k'] = 4
    return {'baseline': baseline, 'candidate': candidate}


CONFIG = {'thresholds': {'recall_at_5_max_drop': .05, 'faithfulness_min': .9,
                         'p95_latency_max_ms': 180000, 'abstention_correctness_min': 1.}}


def test_valid_measurements_and_retrieval_regression():
    measured = experiment()
    assert evaluate(measured, CONFIG)['status'] == 'PASS'
    measured['candidate']['component']['baseline']['recall_at_5'] = .5
    assert evaluate(measured, CONFIG)['status'] == 'FAIL'


def test_changing_generator_is_not_a_top_k_only_experiment():
    measured = experiment()
    measured['candidate']['configuration']['generator'] = 'another-model'
    assert any('generator' in reason for reason in evaluate(measured, CONFIG)['failures'])


def test_nonfinite_measurements_cannot_pass():
    measured = experiment()
    measured['candidate']['end_to_end']['faithfulness'] = float('nan')
    assert evaluate(measured, CONFIG)['status'] == 'FAIL'


def test_configmap_environment_override_changes_outcome(monkeypatch):
    assert evaluate(experiment(), CONFIG)['status'] == 'PASS'
    monkeypatch.setenv('GATE_P95_MAX_MS', '1')
    assert evaluate(experiment(), CONFIG)['status'] == 'FAIL'


def test_no_answer_evidence_is_rejected():
    measured = experiment()
    measured['candidate']['end_to_end']['answers'] = []
    assert evaluate(measured, CONFIG)['status'] == 'FAIL'
