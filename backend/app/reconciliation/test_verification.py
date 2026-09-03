from backend.app.reconciliation.verification import verify_match


def make_settlement(**overrides):
    settlement = {
        "settlement_id": "SET-001",
        "payment_id": "PAY-001",
        "settlement_reference": "SET-441",
        "gross_amount": "1000.00",
        "platform_fee": "20.00",
        "gst_on_fee": "3.60",
        "net_amount": "976.40",
        "settlement_date": "2026-08-24",
        "currency": "INR",
    }
    settlement.update(overrides)
    return settlement


def make_bank(**overrides):
    bank = {
        "transaction_id": "BANK-001",
        "reference": "RZP/SET-441",
        "credit_amount": "976.40",
        "transaction_date": "2026-08-25",
        "currency": "INR",
    }
    bank.update(overrides)
    return bank


def test_all_verification_checks_pass():
    settlement = make_settlement()
    candidate = make_bank()

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is True
    assert result.amount_passed is True
    assert result.fee_passed is True
    assert result.date_passed is True
    assert result.currency_passed is True
    assert result.reference_passed is True
    assert result.uniqueness_passed is True


def test_amount_mismatch_fails_verification():
    settlement = make_settlement()
    candidate = make_bank(credit_amount="975.40")

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is False
    assert result.amount_passed is False


def test_fee_mismatch_fails_verification():
    settlement = make_settlement(
        platform_fee="30.00",
    )
    candidate = make_bank()

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is False
    assert result.fee_passed is False


def test_date_mismatch_fails_verification():
    settlement = make_settlement(
        settlement_date="2026-08-26",
    )
    candidate = make_bank(
        transaction_date="2026-08-25",
    )

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is False
    assert result.date_passed is False


def test_currency_mismatch_fails_verification():
    settlement = make_settlement(
        currency="INR",
    )
    candidate = make_bank(
        currency="USD",
    )

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is False
    assert result.currency_passed is False


def test_missing_currency_fails_verification():
    settlement = make_settlement()
    candidate = make_bank()
    candidate.pop("currency")

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is False
    assert result.currency_passed is False


def test_reference_mismatch_fails_verification():
    settlement = make_settlement(
        settlement_reference="SET-999",
    )
    candidate = make_bank()

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is False
    assert result.reference_passed is False


def test_duplicate_candidate_fails_uniqueness():
    settlement = make_settlement()
    candidate = make_bank()

    duplicate = make_bank()

    result = verify_match(
        settlement,
        candidate,
        [candidate, duplicate],
    )

    assert result.passed is False
    assert result.uniqueness_passed is False


def test_candidate_without_transaction_id_fails_uniqueness():
    settlement = make_settlement()
    candidate = make_bank()
    candidate.pop("transaction_id")

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is False
    assert result.uniqueness_passed is False


def test_invalid_reference_fails_verification():
    settlement = make_settlement(
        settlement_reference=None,
    )
    candidate = make_bank()

    result = verify_match(
        settlement,
        candidate,
        [candidate],
    )

    assert result.passed is False
    assert result.reference_passed is False
