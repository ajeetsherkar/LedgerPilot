from evaluation.evaluate import evaluate


def test_evaluate_returns_required_metrics():
    metrics = evaluate()

    required_fields = {
        "total_ground_truth",
        "predicted_matches",
        "correct_matches",
        "match_rate",
        "precision",
        "recall",
        "f1",
        "auto_resolved_total",
        "auto_resolved_correct",
        "auto_resolution_precision",
    }

    assert required_fields.issubset(metrics.keys())


def test_evaluation_counts_are_consistent():
    metrics = evaluate()

    assert metrics["total_ground_truth"] == 350
    assert metrics["predicted_matches"] >= metrics["correct_matches"]

    assert (
        metrics["auto_resolved_correct"]
        <= metrics["auto_resolved_total"]
    )


def test_evaluation_metrics_are_valid_rates():
    metrics = evaluate()

    for field in (
        "match_rate",
        "precision",
        "recall",
        "f1",
        "auto_resolution_precision",
    ):
        assert 0.0 <= metrics[field] <= 1.0


def test_f1_matches_precision_and_recall():
    metrics = evaluate()

    precision = metrics["precision"]
    recall = metrics["recall"]

    expected_f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    assert abs(metrics["f1"] - expected_f1) < 1e-12


def test_auto_resolution_precision_matches_counts():
    metrics = evaluate()

    expected_precision = (
        metrics["auto_resolved_correct"]
        / metrics["auto_resolved_total"]
        if metrics["auto_resolved_total"]
        else 0.0
    )

    assert (
        abs(
            metrics["auto_resolution_precision"]
            - expected_precision
        )
        < 1e-12
    )


def test_current_dev_evaluation_baseline():
    metrics = evaluate()

    assert metrics["total_ground_truth"] == 350
    assert metrics["predicted_matches"] == 325
    assert metrics["correct_matches"] == 300

    assert abs(metrics["match_rate"] - 300 / 350) < 1e-12
    assert abs(metrics["precision"] - 300 / 325) < 1e-12
    assert abs(metrics["recall"] - 300 / 350) < 1e-12
    assert abs(metrics["f1"] - 0.8888888888888888) < 1e-12

    assert metrics["auto_resolved_total"] == 283
    assert metrics["auto_resolved_correct"] == 283
    assert metrics["auto_resolution_precision"] == 1.0
