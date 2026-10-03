"""Execution-independent sampling and read-only recorded selection consumption."""

import csv
import json
from pathlib import Path

import pytest

from rcqasyn.config import load_experiment_config
from rcqasyn.experiments import run_experiment
from rcqasyn.experiments.diagnostics import p1_human_review_sample


@pytest.fixture
def matching_executions(tmp_path):
    fixture = tmp_path / 'sampling-provider.json'
    generation = [
        {'call_id': f'fixture-generation-{batch}', 'response': [
            {'age': 25 + i / 10, 'score': 0.5 + i / 1000, 'color': 'red', 'label': label}
            for i in range(50)
        ]}
        for batch, label in enumerate(('no', 'yes'))
    ]
    fixture.write_text(json.dumps({'generation': generation, 'judge': [
        {'response': {'score': 0.8, 'verdict': 'pass', 'reasons': ['fixture']}}
        for _ in range(100)
    ]}), encoding='utf-8')
    config, _ = load_experiment_config(Path('configs/experiments/replay.yaml'))
    config = config.model_copy(update={
        'run_id': None, 'artifact_root': tmp_path / 'executions',
        'generation': config.generation.model_copy(update={
            'requested_count': 100, 'batch_size': 50,
            'class_strategy': 'explicit', 'class_quotas': {'no': 50, 'yes': 50},
        }),
        'generator': config.generator.model_copy(update={'fixture': fixture}),
        'judge': config.judge.model_copy(update={
            'provider': config.judge.provider.model_copy(update={'fixture': fixture}),
        }),
    })
    return [run_experiment(config, replay=True) for _ in range(2)]


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def test_actual_executions_preserve_sample_identity_and_order(matching_executions, tmp_path):
    first, second = matching_executions
    assert first.run_id != second.run_id
    assert first.comparison['specification_fingerprint'] == second.comparison['specification_fingerprint']
    samples = []
    for index, run in enumerate((first, second)):
        destination = tmp_path / f'sample-{index}.csv'
        result = p1_human_review_sample([run.artifact_dir], Path.cwd(), destination, target=20, seed=42)
        assert result['row_count'] == 20
        samples.append(read_rows(destination))
    assert [r['record_id'] for r in samples[0]] == [r['record_id'] for r in samples[1]]
    assert [r['canonical_hash'] for r in samples[0]] == [r['canonical_hash'] for r in samples[1]]
    assert [{k: v for k, v in row.items() if k != 'run_id'} for row in samples[0]] == [
        {k: v for k, v in row.items() if k != 'run_id'} for row in samples[1]
    ]
    alternate = tmp_path / 'different-seed.csv'
    p1_human_review_sample([first.artifact_dir], Path.cwd(), alternate, target=20, seed=43)
    assert [r['record_id'] for r in samples[0]] != [r['record_id'] for r in read_rows(alternate)]


@pytest.fixture
def legacy_recording(tmp_path):
    source = tmp_path / 'historical-source'
    source.mkdir()
    (source / 'manifest.json').write_text(json.dumps({
        'schema_version': 'm1-run-v1', 'status': 'completed',
        'run_id': 'recorded-run', 'dataset_id': 'dev-small',
    }), encoding='utf-8')
    (source / 'candidates_raw.jsonl').write_text('\n'.join(
        json.dumps({'record_id': record_id}) for record_id in ('record-b', 'record-a', 'not-selected')
    ), encoding='utf-8')
    recorded = source / 'p1_human_review.csv'
    recorded.write_bytes(
        b'run_id,dataset_id,record_id,canonical_hash,human_valid,human_notes\r\n'
        b'recorded-run,dev-small,record-b,hash-b,yes,"saved review, keep it"\r\n'
        b'recorded-run,dev-small,record-a,hash-a,,\r\n'
    )
    return source, recorded


def test_legacy_bundle_consumes_recorded_export_without_resampling(legacy_recording, tmp_path):
    source, recorded = legacy_recording
    inventory = {p.name: p.read_bytes() for p in source.iterdir()}
    destination = tmp_path / 'copied-selection.csv'
    result = p1_human_review_sample([source], Path.cwd(), destination, target=1, seed=999)
    assert destination.read_bytes() == recorded.read_bytes()
    assert result['row_count'] == 2
    assert result['recorded_selection'] is True
    assert result['human_columns_blank'] is False
    assert {p.name: p.read_bytes() for p in source.iterdir()} == inventory
    assert [row['record_id'] for row in read_rows(destination)] == ['record-b', 'record-a']


def test_same_recorded_export_path_is_read_only(legacy_recording):
    source, recorded = legacy_recording
    original = recorded.read_bytes()
    result = p1_human_review_sample([source], Path.cwd(), recorded, target=1, seed=999)
    assert result['recorded_selection'] is True
    assert recorded.read_bytes() == original


def test_explicit_aggregate_recorded_export_is_preserved(legacy_recording, tmp_path):
    source, original = legacy_recording
    aggregate = tmp_path / 'aggregate.csv'
    original.rename(aggregate)
    destination = tmp_path / 'consumed.csv'
    result = p1_human_review_sample(
        [source], Path.cwd(), destination, recorded_sample=aggregate, target=1, seed=999,
    )
    assert destination.read_bytes() == aggregate.read_bytes()
    assert result['recorded_selection'] is True
    assert 'strata_hits' not in result


@pytest.mark.parametrize('column,value', [
    ('run_id', 'wrong-run'), ('dataset_id', 'wrong-dataset'), ('record_id', 'absent-record'),
])
def test_recorded_export_rejects_wrong_source_identity(legacy_recording, tmp_path, column, value):
    source, recorded = legacy_recording
    rows = read_rows(recorded)
    rows[0][column] = value
    with recorded.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    destination = tmp_path / 'invalid-copy.csv'
    with pytest.raises(ValueError, match='recorded.*(source|identity)'):
        p1_human_review_sample([source], Path.cwd(), destination)
    assert not destination.exists()
