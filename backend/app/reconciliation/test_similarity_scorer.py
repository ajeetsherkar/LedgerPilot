import pytest

from backend.app.reconciliation.similarity_scorer import (
    AMOUNT_WEIGHT,
    DATE_SIMILARITY_MAX_DAYS,
    DATE_WEIGHT,
    MERCHANT_WEIGHT,
    CURRENCY_WEIGHT,
    REFERENCE_WEIGHT,
    amount_similarity,
    currency_match,
    date_similarity,
    merchant_match,
    reference_similarity,
    score_candidate,
    score_candidates,
)


def make_target():
    return {
        "order_id": "ORD001",
        "merchant_id": "MERCH001",
        "currency": "INR",
        "order_amount": "1000.00",
        "order_date": "2026-08-24",
        "reference": "SETTXN0001",
    }


def make_candidate(
    order_id="ORD002",
    merchant_id="MERCH001",
    currency="INR",
    order_amount="1000.00",
    order_date="2026-08-24",
    reference="SETTXN0002",
):
    return {
        "order_id": order_id,
        "merchant_id": merchant_id,
        "currency": currency,
        "order_amount": order_amount,
        "order_date": order_date,
        "reference": reference,
    }

def test_exact_amount_similarity():
    assert amount_similarity("1000.00", "1000.00") == 1.0


def test_amount_similarity_decreases_with_difference():
    score = amount_similarity("1000.00", "1050.00")

    assert 0.0 < score < 1.0


def test_large_amount_difference_reaches_zero():
    assert amount_similarity("1000.00", "2500.00") == 0.0


def test_invalid_amount_returns_zero():
    assert amount_similarity("INVALID", "1000.00") == 0.0


def test_same_date_similarity_is_one():
    assert date_similarity(
        "2026-08-24",
        "2026-08-24",
    ) == 1.0


def test_date_similarity_decreases_with_distance():
    score = date_similarity(
        "2026-08-24",
        "2026-08-25",
        max_days=3,
    )

    assert 0.0 < score < 1.0


def test_date_at_maximum_window_is_zero():
    assert date_similarity(
        "2026-08-24",
        "2026-08-27",
        max_days=3,
    ) == 0.0


def test_date_outside_window_is_zero():
    assert date_similarity(
        "2026-08-24",
        "2026-08-28",
        max_days=3,
    ) == 0.0


def test_invalid_date_returns_zero():
    assert date_similarity(
        "INVALID",
        "2026-08-24",
    ) == 0.0


def test_exact_reference_similarity_is_one():
    assert reference_similarity(
        "SETTXN0001",
        "SETTXN0001",
    ) == 1.0


def test_reference_similarity_is_partial():
    score = reference_similarity(
        "SETTXN0001",
        "SETTXN0002",
    )

    assert 0.0 < score < 1.0


def test_reference_normalization_is_used():
    assert reference_similarity(
        "RZP/SET-441",
        "SET_441",
    ) == 1.0


def test_invalid_reference_returns_zero():
    assert reference_similarity(
        None,
        "SETTXN0001",
    ) == 0.0


def test_same_merchant_matches():
    assert merchant_match(
        make_target(),
        make_candidate(),
    ) == 1.0


def test_wrong_merchant_does_not_match():
    assert merchant_match(
        make_target(),
        make_candidate(merchant_id="MERCH999"),
    ) == 0.0


def test_same_currency_matches():
    assert currency_match(
        make_target(),
        make_candidate(),
    ) == 1.0


def test_currency_matching_is_case_insensitive():
    assert currency_match(
        make_target(),
        make_candidate(currency="inr"),
    ) == 1.0


def test_wrong_currency_does_not_match():
    assert currency_match(
        make_target(),
        make_candidate(currency="USD"),
    ) == 0.0


def test_missing_merchant_is_not_assumed_to_match():
    candidate = make_candidate()
    candidate.pop("merchant_id")

    assert merchant_match(
        make_target(),
        candidate,
    ) == 0.0


def test_missing_currency_is_not_assumed_to_match():
    candidate = make_candidate()
    candidate.pop("currency")

    assert currency_match(
        make_target(),
        candidate,
    ) == 0.0


def test_default_weights_sum_to_one():
    assert (
        AMOUNT_WEIGHT
        + DATE_WEIGHT
        + REFERENCE_WEIGHT
        + MERCHANT_WEIGHT
        + CURRENCY_WEIGHT
    ) == pytest.approx(1.0)


def test_exact_candidate_gets_perfect_score():
    result = score_candidate(
        make_target(),
        make_candidate(reference="SETTXN0001"),
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    assert result["total_score"] == 1.0
    assert result["amount_similarity"] == 1.0
    assert result["date_similarity"] == 1.0
    assert result["reference_similarity"] == 1.0
    assert result["merchant_match"] == 1.0
    assert result["currency_match"] == 1.0


def test_partial_candidate_gets_partial_score():
    result = score_candidate(
        make_target(),
        make_candidate(
            order_amount="1050.00",
            order_date="2026-08-25",
            reference="SETTXN0002",
        ),
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    assert 0.0 < result["total_score"] < 1.0


def test_wrong_merchant_reduces_score():
    good = score_candidate(
        make_target(),
        make_candidate(),
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    bad = score_candidate(
        make_target(),
        make_candidate(merchant_id="MERCH999"),
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    assert bad["total_score"] < good["total_score"]


def test_wrong_currency_reduces_score():
    good = score_candidate(
        make_target(),
        make_candidate(),
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    bad = score_candidate(
        make_target(),
        make_candidate(currency="USD"),
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    assert bad["total_score"] < good["total_score"]


def test_custom_weights_are_supported():
    result = score_candidate(
        make_target(),
        make_candidate(reference="SETTXN0001"),
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
        amount_weight=0.50,
        date_weight=0.10,
        reference_weight=0.20,
        merchant_weight=0.10,
        currency_weight=0.10,
    )

    assert result["total_score"] == 1.0


def test_invalid_weights_raise_error():
    with pytest.raises(ValueError):
        score_candidate(
            make_target(),
            make_candidate(),
            amount_field="order_amount",
            date_field="order_date",
            target_reference_field="reference",
            candidate_reference_field="reference",
            amount_weight=0.90,
            date_weight=0.20,
            reference_weight=0.10,
            merchant_weight=0.10,
            currency_weight=0.10,
        )


def test_negative_date_window_raises_error():
    with pytest.raises(ValueError):
        score_candidate(
            make_target(),
            make_candidate(),
            amount_field="order_amount",
            date_field="order_date",
            target_reference_field="reference",
            candidate_reference_field="reference",
            date_window_days=-1,
        )


def test_explanation_is_returned():
    result = score_candidate(
        make_target(),
        make_candidate(),
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    assert "explanation" in result
    assert "amount" in result["explanation"]
    assert "date" in result["explanation"]
    assert "reference" in result["explanation"]
    assert "merchant" in result["explanation"]
    assert "currency" in result["explanation"]


def test_score_candidates_scores_every_candidate():
    candidates = [
        make_candidate(order_id="ORD002"),
        make_candidate(
            order_id="ORD003",
            order_amount="1050.00",
        ),
    ]

    results = score_candidates(
        make_target(),
        candidates,
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    assert len(results) == 2
    assert results[0]["candidate"]["order_id"] == "ORD002"
    assert results[1]["candidate"]["order_id"] == "ORD003"


def test_score_candidates_preserves_candidate_order():
    candidates = [
        make_candidate(order_id="ORD003"),
        make_candidate(order_id="ORD002"),
        make_candidate(order_id="ORD004"),
    ]

    results = score_candidates(
        make_target(),
        candidates,
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    assert [
        result["candidate"]["order_id"]
        for result in results
    ] == [
        "ORD003",
        "ORD002",
        "ORD004",
    ]


def test_score_does_not_select_a_winner():
    candidates = [
        make_candidate(order_id="ORD002"),
        make_candidate(order_id="ORD003"),
    ]

    results = score_candidates(
        make_target(),
        candidates,
        amount_field="order_amount",
        date_field="order_date",
        target_reference_field="reference",
        candidate_reference_field="reference",
    )

    assert len(results) == 2
    assert all("score" in result for result in results)
