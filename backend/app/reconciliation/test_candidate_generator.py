from backend.app.reconciliation.candidate_generator import (
    CANDIDATE_AMOUNT_TOLERANCE_PERCENT,
    CANDIDATE_DATE_WINDOW_MAX_DAYS,
    MAX_CANDIDATES,
    generate_candidates,
)


def make_target():
    return {
        "order_id": "ORD001",
        "merchant_id": "MERCH001",
        "currency": "INR",
        "order_amount": "1000.00",
        "order_date": "2026-08-24",
    }


def make_candidate(
    *,
    order_id="ORD002",
    merchant_id="MERCH001",
    currency="INR",
    order_amount="1000.00",
    order_date="2026-08-24",
):
    return {
        "order_id": order_id,
        "merchant_id": merchant_id,
        "currency": currency,
        "order_amount": order_amount,
        "order_date": order_date,
    }


def test_exact_plausible_candidate_is_returned():
    result = generate_candidates(
        make_target(),
        [make_candidate()],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert len(result) == 1
    assert result[0]["order_id"] == "ORD002"


def test_amount_within_rough_range_is_returned():
    result = generate_candidates(
        make_target(),
        [make_candidate(order_amount="1090.00")],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert len(result) == 1


def test_amount_outside_rough_range_is_rejected():
    result = generate_candidates(
        make_target(),
        [make_candidate(order_amount="1200.00")],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert result == []


def test_nearby_date_is_returned():
    result = generate_candidates(
        make_target(),
        [make_candidate(order_date="2026-08-27")],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert len(result) == 1


def test_date_outside_window_is_rejected():
    result = generate_candidates(
        make_target(),
        [make_candidate(order_date="2026-08-28")],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert result == []


def test_wrong_merchant_is_rejected():
    result = generate_candidates(
        make_target(),
        [make_candidate(merchant_id="MERCH999")],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert result == []


def test_wrong_currency_is_rejected():
    result = generate_candidates(
        make_target(),
        [make_candidate(currency="USD")],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert result == []


def test_missing_merchant_information_does_not_reject():
    candidate = make_candidate()
    candidate.pop("merchant_id")

    result = generate_candidates(
        make_target(),
        [candidate],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert len(result) == 1


def test_missing_currency_information_does_not_reject():
    candidate = make_candidate()
    candidate.pop("currency")

    result = generate_candidates(
        make_target(),
        [candidate],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert len(result) == 1


def test_invalid_amount_is_rejected():
    result = generate_candidates(
        make_target(),
        [make_candidate(order_amount="not-an-amount")],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert result == []


def test_invalid_date_is_rejected():
    result = generate_candidates(
        make_target(),
        [make_candidate(order_date="not-a-date")],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert result == []


def test_max_candidates_is_respected():
    candidates = [
        make_candidate(order_id=f"ORD{i:03d}")
        for i in range(20)
    ]

    result = generate_candidates(
        make_target(),
        candidates,
        amount_field="order_amount",
        date_field="order_date",
        max_candidates=5,
    )

    assert len(result) == 5


def test_results_preserve_candidate_order():
    candidates = [
        make_candidate(order_id="ORD002"),
        make_candidate(order_id="ORD003"),
        make_candidate(order_id="ORD004"),
    ]

    result = generate_candidates(
        make_target(),
        candidates,
        amount_field="order_amount",
        date_field="order_date",
    )

    assert [
        candidate["order_id"]
        for candidate in result
    ] == [
        "ORD002",
        "ORD003",
        "ORD004",
    ]


def test_amount_tolerance_is_configurable():
    target = make_target()

    result = generate_candidates(
        target,
        [make_candidate(order_amount="1150.00")],
        amount_field="order_amount",
        date_field="order_date",
        amount_tolerance_percent=0.20,
    )

    assert len(result) == 1


def test_date_window_is_configurable():
    target = make_target()

    result = generate_candidates(
        target,
        [make_candidate(order_date="2026-08-29")],
        amount_field="order_amount",
        date_field="order_date",
        date_window_days=5,
    )

    assert len(result) == 1


def test_target_record_is_not_returned_as_candidate():
    target = make_target()

    result = generate_candidates(
        target,
        [target],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert result == []


def test_default_development_constants():
    assert CANDIDATE_AMOUNT_TOLERANCE_PERCENT == 0.10
    assert CANDIDATE_DATE_WINDOW_MAX_DAYS == 3
    assert MAX_CANDIDATES == 10


def test_zero_tolerance_requires_exact_amount():
    result = generate_candidates(
        make_target(),
        [make_candidate(order_amount="1000.01")],
        amount_field="order_amount",
        date_field="order_date",
        amount_tolerance_percent=0,
    )

    assert result == []


def test_negative_date_window_returns_empty():
    result = generate_candidates(
        make_target(),
        [make_candidate()],
        amount_field="order_amount",
        date_field="order_date",
        date_window_days=-1,
    )

    assert result == []


def test_negative_max_candidates_returns_empty():
    result = generate_candidates(
        make_target(),
        [make_candidate()],
        amount_field="order_amount",
        date_field="order_date",
        max_candidates=-1,
    )

    assert result == []


def test_currency_matching_is_case_insensitive():
    target = make_target()
    candidate = make_candidate(currency="inr")

    result = generate_candidates(
        target,
        [candidate],
        amount_field="order_amount",
        date_field="order_date",
    )

    assert len(result) == 1
