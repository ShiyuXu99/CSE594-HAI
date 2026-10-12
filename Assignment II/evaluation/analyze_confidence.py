"""Compare model confidence with observed correctness on the study dataset."""
from pathlib import Path
import csv
import json
import math
import numpy as np
from sklearn.metrics import roc_auc_score


def wilson_interval(correct, total):
    z = 1.96
    p = correct / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return center - half, center + half


def summarize_bins(confidence, correctness, edges):
    result = []
    for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
        mask = (confidence >= lower) & ((confidence <= upper) if index == len(edges) - 2 else (confidence < upper))
        n = int(mask.sum())
        if not n:
            continue
        successes = int(correctness[mask].sum())
        accuracy = successes / n
        average = float(confidence[mask].mean())
        low, high = wilson_interval(successes, n)
        result.append({
            'confidence_range': f'{lower:.1f}-{upper:.1f}',
            'n': n, 'correct': successes, 'errors': n - successes,
            'mean_confidence': average, 'accuracy': accuracy,
            'confidence_minus_accuracy': average - accuracy,
            'absolute_gap': abs(average - accuracy),
            'accuracy_ci95_low': low, 'accuracy_ci95_high': high,
        })
    assert sum(row['n'] for row in result) == len(confidence)
    return result


def analyze(dataset, output):
    with dataset.open() as file:
        rows = list(csv.DictReader(file))
    confidence = np.array([float(row['model_confidence']) for row in rows])
    correctness = np.array([int(row['model_prediction'] == row['true_label']) for row in rows])
    assert all(int(row['correct']) == value for row, value in zip(rows, correctness))
    assert len(rows) and np.isfinite(confidence).all()
    assert ((confidence >= 0) & (confidence <= 1)).all()
    groups = summarize_bins(confidence, correctness, [0, 0.5, 0.7, 0.9, 1])
    calibration = summarize_bins(confidence, correctness, np.linspace(0, 1, 11))
    for name, table in [('confidence_by_range.csv', groups), ('confidence_calibration_bins.csv', calibration)]:
        with (output / name).open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows(table)
    thresholds = []
    for threshold in [0.5, 0.7, 0.9]:
        mask = confidence >= threshold
        n = int(mask.sum())
        thresholds.append({'threshold': threshold, 'n': n, 'coverage': n / len(rows), 'accuracy': float(correctness[mask].mean()) if n else None, 'errors': int(n - correctness[mask].sum())})
    mean_confidence = float(confidence.mean())
    accuracy = float(correctness.mean())
    metrics = {
        'n': len(rows), 'accuracy': accuracy, 'mean_confidence': mean_confidence,
        'mean_confidence_minus_accuracy': mean_confidence - accuracy,
        'mean_confidence_correct': float(confidence[correctness == 1].mean()) if correctness.any() else None,
        'mean_confidence_incorrect': float(confidence[correctness == 0].mean()) if (correctness == 0).any() else None,
        'ece_10_equal_width_bins': sum(row['n'] / len(rows) * row['absolute_gap'] for row in calibration),
        'correctness_roc_auc': float(roc_auc_score(correctness, confidence)) if len(set(correctness)) == 2 else None,
        'thresholds': thresholds,
        'method': 'ECE: weighted absolute difference between average confidence and accuracy in 10 equal-width bins. ROC AUC: confidence discriminating correct from incorrect trials. Range intervals are left-inclusive and right-exclusive, except the final interval includes 1.0. Accuracy intervals are 95% Wilson intervals.',
        'reference': 'Guo et al. (2017), On Calibration of Modern Neural Networks. https://proceedings.mlr.press/v70/guo17a.html',
        'limitations': 'Rounded, four-class-renormalized confidence scores; deliberately curated sample of 200; original dataset labels; upstream validation reuse. These are descriptive checks on this study set, not validation on independent data or evidence that displaying confidence improves human decisions. ECE depends on binning; small-bin uncertainty is substantial.',
    }
    (output / 'confidence_metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
    print('\nConfidence analysis')
    print('Range       N   Mean confidence   Actual accuracy')
    for row in groups:
        print(f"{row['confidence_range']:10} {row['n']:3} {row['mean_confidence']:16.1%} {row['accuracy']:17.1%}")
    print(f'Mean confidence: {mean_confidence:.2%}; overall accuracy: {accuracy:.2%}')
    print(f"ECE (10 bins): {metrics['ece_10_equal_width_bins']:.4f}")
    if metrics['correctness_roc_auc'] is not None:
        print(f"Correctness ROC AUC: {metrics['correctness_roc_auc']:.4f}")
    return metrics


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    analyze(root / 'data/study_dataset.csv', root / 'evaluation')
