import json
from pathlib import Path
from metrics import ndcg
from gate import evaluate
from offline_common import load_passages


def test_golden_cannot_manufacture_retrieval_evidence(tmp_path):
    passages, info = load_passages(tmp_path, [{'question':'secret answer', 'expect':'42',
                                             'relevant':[{'source':'missing.pdf','page':1}]}])
    assert passages == []
    assert info['fallback_passages'] == 0


def test_repeated_page_cannot_inflate_ndcg():
    assert ndcg({('a', 1)}, [('a', 1)] * 5, 5) == 1


def test_old_reference_experiment_is_rejected():
    experiment = json.loads(Path('eval/results/change-topk4.json').read_text())
    config = json.loads(Path('eval/gate.json').read_text())
    result = evaluate(experiment, config)
    assert result['status'] == 'FAIL'
    assert any('Reference/synthetic' in reason for reason in result['failures'])
