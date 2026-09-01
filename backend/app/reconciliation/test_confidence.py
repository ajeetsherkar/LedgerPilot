import pytest

from backend.app.reconciliation.confidence import (
    ConfidenceBucket,
    ConfidenceThresholds,
    classify_confidence,
)


def test_high_confidence_goes_to_high_bucket():
    thresholds = ConfidenceThresholds(
        high=0.90,
        medium=0.70,
    )

    result = classify_confidence(
        0.95,
        thresholds,
    )

    assert result == ConfidenceBucket.HIGH


def test_medium_confidence_goes_to_medium_bucket():
    thresholds = ConfidenceThresholds(
        high=0.90,
        medium=0.70,
    )

    result = classify_confidence(
        0.80,
        thresholds,
    )

    assert result == ConfidenceBucket.MEDIUM


def test_low_confidence_goes_to_low_bucket():
    thresholds = ConfidenceThresholds(
        high=0.90,
        medium=0.70,
    )

    result = classify_confidence(
        0.50,
        thresholds,
    )

    assert result == ConfidenceBucket.LOW


def test_high_threshold_is_inclusive():
    thresholds = ConfidenceThresholds(
        high=0.90,
        medium=0.70,
    )

    result = classify_confidence(
        0.90,
        thresholds,
    )

    assert result == ConfidenceBucket.HIGH


def test_medium_threshold_is_inclusive():
    thresholds = ConfidenceThresholds(
        high=0.90,
        medium=0.70,
    )

    result = classify_confidence(
        0.70,
        thresholds,
    )

    assert result == ConfidenceBucket.MEDIUM


def test_thresholds_are_configurable():
    strict_thresholds = ConfidenceThresholds(
        high=0.95,
        medium=0.80,
    )

    relaxed_thresholds = ConfidenceThresholds(
        high=0.80,
        medium=0.60,
    )

    assert (
        classify_confidence(
            0.85,
            strict_thresholds,
        )
        == ConfidenceBucket.MEDIUM
    )

    assert (
        classify_confidence(
            0.85,
            relaxed_thresholds,
        )
        == ConfidenceBucket.HIGH
    )


def test_high_threshold_cannot_be_lower_than_medium():
    with pytest.raises(ValueError):
        ConfidenceThresholds(
            high=0.60,
            medium=0.80,
        )


def test_thresholds_must_be_between_zero_and_one():
    with pytest.raises(ValueError):
        ConfidenceThresholds(
            high=1.10,
            medium=0.70,
        )

    with pytest.raises(ValueError):
        ConfidenceThresholds(
            high=0.90,
            medium=-0.10,
        )


def test_confidence_must_be_between_zero_and_one():
    thresholds = ConfidenceThresholds(
        high=0.90,
        medium=0.70,
    )

    with pytest.raises(ValueError):
        classify_confidence(
            1.10,
            thresholds,
        )

    with pytest.raises(ValueError):
        classify_confidence(
            -0.10,
            thresholds,
        )
