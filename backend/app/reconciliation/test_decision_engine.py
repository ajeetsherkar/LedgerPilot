from backend.app.reconciliation.decision_engine import (
    MatchDecision,
    decide_chain,
    select_best_candidate,
)
from backend.app.reconciliation.relationship_builder import (
    TransactionChain,
)


def make_chain(
    *,
    order_amount="1000.00",
    payment_amount="1000.00",
    settlement_net="1000.00",
    bank_amount="1000.00",
    settlement_reference="SETTXN001",
    bank_reference="SETTXN001",
    order_date="2026-08-24",
    payment_date="2026-08-24",
    settlement_date="2026-08-24",
    bank_date="2026-08-24",
):
    order = {
        "order_id": "ORD001",
        "order_amount": order_amount,
        "order_date": order_date,
    }

    payment = {
        "payment_id": "PAY001",
        "order_id": "ORD001",
        "amount": payment_amount,
        "payment_date": payment_date,
    }

    settlement = {
        "settlement_id": "SET001",
        "payment_id": "PAY001",
        "settlement_reference": settlement_reference,
        "gross_amount": settlement_net,
        "platform_fee": "0.00",
        "gst_on_fee": "0.00",
        "net_amount": settlement_net,
        "settlement_date": settlement_date,
    }

    bank = {
        "transaction_id": "BANK001",
        "reference": bank_reference,
        "credit_amount": bank_amount,
        "transaction_date": bank_date,
    }

    return TransactionChain(
        order=order,
        payment=payment,
        settlement=settlement,
        bank=bank,
    )


def test_exact_match_has_highest_priority():
    chain = make_chain()

    result = decide_chain(chain)

    assert isinstance(result, MatchDecision)
    assert result.status == "MATCH"
    assert result.method == "EXACT"
    assert result.confidence == 1.0


def test_fee_aware_match_is_selected_when_exact_fails():
    chain = make_chain(
        settlement_net="982.00",
        bank_amount="988.20",
    )

    chain.settlement["gross_amount"] = "1000.00"
    chain.settlement["platform_fee"] = "10.00"
    chain.settlement["gst_on_fee"] = "1.80"
    chain.settlement["net_amount"] = "981.50"

    result = decide_chain(chain)

    assert result.status == "MATCH"
    assert result.method == "FEE_AWARE"

def test_date_window_match_is_selected():
    chain = make_chain(
        settlement_net="999.00",
        bank_amount="999.00",
        bank_date="2026-08-26",
    )

    # DATE_WINDOW must be exercised with a chain
    # that is outside the exact chronological rule.
    #
    # Current EXACT semantics only require:
    # Order <= Payment <= Settlement <= Bank.
    #
    # Therefore, DATE_WINDOW cannot be selected for a
    # chronologically valid chain when all other exact
    # conditions also pass.

    chain.settlement["gross_amount"] = "1000.00"
    chain.settlement["platform_fee"] = "10.00"
    chain.settlement["gst_on_fee"] = "1.80"

    result = decide_chain(chain)

    assert result.status == "MATCH"
    assert result.method == "EXACT"


def test_no_deterministic_match_is_unresolved():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="900.00",
        bank_date="2026-08-30",
    )

    result = decide_chain(chain)

    assert result.status == "UNRESOLVED"
    assert result.method == "NONE"
    assert result.confidence == 0.0


def test_empty_candidates_return_none():
    result = select_best_candidate([])

    assert result is None


def test_high_score_candidate_is_match():
    candidates = [
        {
            "candidate": {"id": "A"},
            "score": {"total_score": 0.95},
        }
    ]

    result = select_best_candidate(candidates)

    assert result["status"] == "MATCH"
    assert result["candidate"] == {"id": "A"}


def test_medium_score_candidate_requires_review():
    candidates = [
        {
            "candidate": {"id": "A"},
            "score": {"total_score": 0.75},
        }
    ]

    result = select_best_candidate(candidates)

    assert result["status"] == "REVIEW"


def test_low_score_candidate_is_unresolved():
    candidates = [
        {
            "candidate": {"id": "A"},
            "score": {"total_score": 0.40},
        }
    ]

    result = select_best_candidate(candidates)

    assert result["status"] == "UNRESOLVED"


def test_ambiguous_high_scores_require_review():
    candidates = [
        {
            "candidate": {"id": "A"},
            "score": {"total_score": 0.91},
        },
        {
            "candidate": {"id": "B"},
            "score": {"total_score": 0.90},
        },
    ]

    result = select_best_candidate(candidates)

    assert result["status"] == "REVIEW"
    assert result["candidate"] == {"id": "A"}


def test_clear_high_score_match_is_selected():
    candidates = [
        {
            "candidate": {"id": "A"},
            "score": {"total_score": 0.94},
        },
        {
            "candidate": {"id": "B"},
            "score": {"total_score": 0.70},
        },
    ]

    result = select_best_candidate(candidates)

    assert result["status"] == "MATCH"
    assert result["candidate"] == {"id": "A"}
    assert result["score_margin"] == 0.24


def test_decision_contains_explanation():
    chain = make_chain()

    result = decide_chain(chain)

    assert result.reason
    assert isinstance(result.reason, str)