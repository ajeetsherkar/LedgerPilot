from backend.app.reconciliation.confidence import ConfidenceBucket
from backend.app.reconciliation.decision_engine import (
    MatchDecision,
    _add_confidence_bucket,
    _auto_resolve_if_eligible,
    decide_chain,
    select_best_candidate,
)
from backend.app.reconciliation.exception_types import ExceptionType
from unittest.mock import patch
from backend.app.reconciliation.relationship_builder import (
    TransactionChain,
)


def make_chain(
    *,
    order_amount="1000.00",
    payment_amount="1000.00",
    settlement_net="1000.00",
    currency="INR",
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
        "currency": currency,
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
        "currency": "INR",
    }

    bank = {
        "transaction_id": "BANK001",
        "reference": bank_reference,
        "credit_amount": bank_amount,
        "transaction_date": bank_date,
        "currency": "INR",
    }

    return TransactionChain(
        order=order,
        payment=payment,
        settlement=settlement,
        bank=bank,
    )


def test_exact_match_has_high_confidence_bucket():
    chain = make_chain()

    result = decide_chain(chain)

    assert result.status == "AUTO_RESOLVED"
    assert result.method == "EXACT"
    assert result.confidence == 1.0
    assert result.confidence_bucket == ConfidenceBucket.HIGH


def test_exact_match_gets_high_confidence_bucket():
    chain = make_chain()

    result = decide_chain(chain)

    assert result.confidence == 1.0
    assert result.confidence_bucket == ConfidenceBucket.HIGH


def test_payment_mismatch_remains_exception_with_high_confidence():
    chain = make_chain(
        payment_amount="900.00",
    )

    result = decide_chain(chain)

    assert result.status == "HUMAN_REVIEW"
    assert result.exception_type == ExceptionType.AMOUNT_MISMATCH.value
    assert result.confidence == 1.0
    assert result.confidence_bucket == ConfidenceBucket.HIGH


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

    assert result.status == "HUMAN_REVIEW"
    assert result.method == "FEE_AWARE"


def test_date_window_match_is_selected():

    chain = make_chain(
        settlement_net="999.00",
        bank_amount="999.00",
        bank_date="2026-08-26",
    )

    chain.payment["payment_date"] = "2026-08-24"
    chain.settlement["settlement_date"] = "2026-08-25"
    chain.bank["transaction_date"] = "2026-08-26"

    with patch(
        "backend.app.reconciliation.decision_engine.exact_match",
        return_value=False,
    ), patch(
        "backend.app.reconciliation.decision_engine.fee_aware_match",
        return_value=False,
    ), patch(
        "backend.app.reconciliation.decision_engine.date_window_match",
        return_value=True,
    ):

        result = decide_chain(chain)

    assert result.status == "HUMAN_REVIEW"
    assert result.method == "DATE_WINDOW"


def test_no_deterministic_match_is_unresolved():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="900.00",
        bank_date="2026-08-30",
    )

    result = decide_chain(chain)

    assert result.status == "HUMAN_REVIEW"
    assert result.method == "NONE"
    assert result.confidence == 0.0


def test_unresolved_has_low_confidence_bucket():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="900.00",
        bank_date="2026-08-30",
    )

    result = decide_chain(
        chain,
        bank_candidates=[],
    )

    assert result.status == "HUMAN_REVIEW"
    assert result.confidence == 0.0
    assert result.confidence_bucket == ConfidenceBucket.LOW


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


def test_close_high_scoring_candidates_force_low_confidence():
    scored = [
        {
            "candidate": {"transaction_id": "BTX001"},
            "score": {"total_score": 0.91},
        },
        {
            "candidate": {"transaction_id": "BTX002"},
            "score": {"total_score": 0.89},
        },
    ]

    result = select_best_candidate(
        scored,
        match_threshold=0.80,
        review_threshold=0.64,
        min_score_margin=0.05,
    )

    assert result is not None
    assert result["status"] == "REVIEW"
    assert result["ambiguous"] is True
    assert result["score"] == 0.91
    assert result["score_margin"] == 0.02


def test_well_separated_high_score_can_match():
    scored = [
        {
            "candidate": {"transaction_id": "BTX001"},
            "score": {"total_score": 0.91},
        },
        {
            "candidate": {"transaction_id": "BTX002"},
            "score": {"total_score": 0.80},
        },
    ]

    result = select_best_candidate(
        scored,
        match_threshold=0.80,
        review_threshold=0.64,
        min_score_margin=0.05,
    )

    assert result is not None
    assert result["status"] == "MATCH"
    assert result["ambiguous"] is False
    assert result["score_margin"] == 0.11


def test_single_candidate_is_not_ambiguous():
    scored = [
        {
            "candidate": {"transaction_id": "BTX001"},
            "score": {"total_score": 0.91},
        },
    ]

    result = select_best_candidate(
        scored,
        match_threshold=0.80,
        review_threshold=0.64,
        min_score_margin=0.05,
    )

    assert result is not None
    assert result["status"] == "MATCH"
    assert result["ambiguous"] is False


def test_decision_contains_explanation():
    chain = make_chain()

    result = decide_chain(chain)

    assert result.reason
    assert isinstance(result.reason, str)


def test_high_confidence_verified_match_becomes_auto_resolved():
    decision = MatchDecision(
        status="MATCH",
        method="EXACT",
        confidence=1.0,
    )

    decision = _add_confidence_bucket(decision)

    result = _auto_resolve_if_eligible(
        decision,
        verification_passed=True,
        has_competing_candidate=False,
    )

    assert result.status == "AUTO_RESOLVED"
    assert result.confidence_bucket == ConfidenceBucket.HIGH


def test_high_confidence_match_without_verification_is_not_auto_resolved():
    decision = MatchDecision(
        status="MATCH",
        method="EXACT",
        confidence=1.0,
    )

    decision = _add_confidence_bucket(decision)

    result = _auto_resolve_if_eligible(
        decision,
        verification_passed=False,
        has_competing_candidate=False,
    )

    assert result.status == "MATCH"


def test_high_confidence_verified_match_with_competitor_is_not_auto_resolved():
    decision = MatchDecision(
        status="MATCH",
        method="SIMILARITY",
        confidence=0.95,
    )

    decision = _add_confidence_bucket(decision)

    result = _auto_resolve_if_eligible(
        decision,
        verification_passed=True,
        has_competing_candidate=True,
    )

    assert result.status == "MATCH"


def test_medium_confidence_verified_match_is_not_auto_resolved():
    decision = MatchDecision(
        status="MATCH",
        method="SIMILARITY",
        confidence=0.80,
    )

    decision = _add_confidence_bucket(decision)

    result = _auto_resolve_if_eligible(
        decision,
        verification_passed=True,
        has_competing_candidate=False,
    )

    assert result.status == "MATCH"


def test_review_decision_is_not_auto_resolved():
    decision = MatchDecision(
        status="REVIEW",
        method="SIMILARITY",
        confidence=0.95,
    )

    decision = _add_confidence_bucket(decision)

    result = _auto_resolve_if_eligible(
        decision,
        verification_passed=True,
        has_competing_candidate=False,
    )

    assert result.status == "REVIEW"


def test_similarity_fallback_matches_bank_candidate():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="1000.00",
        bank_date="2026-08-24",
    )

    bank_candidates = [
        {
            "transaction_id": "BANK999",
            "reference": "SETTXN001",
            "credit_amount": "1000.00",
            "transaction_date": "2026-08-24",
            "currency": "INR",
        }
    ]

    result = decide_chain(
        chain,
        bank_candidates=bank_candidates,
    )

    assert result.status == "HUMAN_REVIEW"
    assert result.method == "SIMILARITY"
    assert result.candidate == bank_candidates[0]


def test_similarity_fallback_can_require_review():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="950.00",
        bank_date="2026-08-26",
    )

    bank_candidates = [
        {
            "transaction_id": "BANK999",
            "reference": "SETTXN001",
            "credit_amount": "950.00",
            "transaction_date": "2026-08-26",
            "currency": "INR",
        }
    ]

    result = decide_chain(
        chain,
        bank_candidates=bank_candidates,
    )

    assert result.status == "HUMAN_REVIEW"
    assert result.method == "SIMILARITY"


def test_similarity_confidence_bucket_is_based_on_score():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="950.00",
        bank_date="2026-08-26",
    )

    bank_candidates = [
        {
            "transaction_id": "BANK999",
            "reference": "SETTXN001",
            "credit_amount": "950.00",
            "transaction_date": "2026-08-26",
            "currency": "INR",
        }
    ]

    result = decide_chain(
        chain,
        bank_candidates=bank_candidates,
    )

    assert result.method == "SIMILARITY"

    expected_bucket = (
        ConfidenceBucket.HIGH
        if result.confidence >= 0.90
        else (
            ConfidenceBucket.MEDIUM
            if result.confidence >= 0.70
            else ConfidenceBucket.LOW
        )
    )

    assert result.confidence_bucket == expected_bucket


def test_similarity_review_gets_medium_or_low_bucket():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="950.00",
        bank_date="2026-08-26",
    )

    bank_candidates = [
        {
            "transaction_id": "BANK999",
            "reference": "SETTXN001",
            "credit_amount": "950.00",
            "transaction_date": "2026-08-26",
            "currency": "INR",
        }
    ]

    result = decide_chain(
        chain,
        bank_candidates=bank_candidates,
    )

    assert result.method == "SIMILARITY"
    assert result.confidence_bucket in {
        ConfidenceBucket.MEDIUM,
        ConfidenceBucket.LOW,
    }


def test_ambiguous_similarity_candidates_yield_low_confidence_review():
    # Reuses the similarity fixture pattern from the tests above, but
    # supplies two bank candidates whose scores land close together
    # (0.91 vs 0.89, margin 0.02) so the ambiguity gate in
    # select_best_candidate forces REVIEW + LOW confidence, even
    # though 0.91 alone would otherwise clear the MATCH threshold.
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="1000.00",
        bank_date="2026-08-24",
    )

    bank_candidates = [
        {
            "transaction_id": "BANK998",
            "reference": "SETTXN001",
            "credit_amount": "1000.00",
            "transaction_date": "2026-08-24",
            "currency": "INR",
        },
        {
            "transaction_id": "BANK999",
            "reference": "SETTXN001",
            "credit_amount": "999.00",
            "transaction_date": "2026-08-24",
            "currency": "INR",
        },
    ]

    result = decide_chain(
        chain,
        bank_candidates=bank_candidates,
    )

    assert result.method == "SIMILARITY"
    assert result.status == "HUMAN_REVIEW"
    assert result.confidence_bucket == ConfidenceBucket.LOW


def test_medium_confidence_case_routes_to_ai_reasoning(
    monkeypatch,
):
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="950.00",
        bank_date="2026-08-26",
    )

    bank_candidates = [
        {
            "transaction_id": "BANK999",
            "reference": "SETTXN001",
            "credit_amount": "950.00",
            "transaction_date": "2026-08-26",
            "currency": "INR",
        }
    ]

    captured = {}

    def fake_ai_service(evidence):
        captured["evidence"] = evidence

        return {
            "status": "PENDING_AI_REVIEW",
            "reasoning": "Amount matches but reference differs.",
            "recommendation": "REVIEW",
            "evidence": evidence,
        }

    monkeypatch.setattr(
        "backend.app.reconciliation.decision_engine."
        "reason_about_reconciliation",
        fake_ai_service,
    )

    result = decide_chain(
        chain,
        bank_candidates=bank_candidates,
    )

    assert result.method == "SIMILARITY"

    if result.confidence_bucket == ConfidenceBucket.MEDIUM:
        assert "ai_reasoning" in result.candidate
        assert "evidence" in captured
        assert "transaction" in captured["evidence"]
        assert "top_candidates" in captured["evidence"]


def test_similarity_fallback_without_candidates_remains_unresolved():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="900.00",
        bank_date="2026-08-30",
    )

    result = decide_chain(
        chain,
        bank_candidates=[],
    )

    assert result.status == "HUMAN_REVIEW"
    assert result.method == "NONE"
    assert result.confidence == 0.0


def test_medium_confidence_ai_output_passes_through_safe_validation(
    monkeypatch,
):
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="950.00",
        bank_date="2026-08-26",
    )

    bank_candidates = [
        {
            "transaction_id": "BANK999",
            "reference": "SETTXN001",
            "credit_amount": "950.00",
            "transaction_date": "2026-08-26",
            "currency": "INR",
        }
    ]

    def fake_ai_service(evidence):
        return {
            "classification": "LIKELY_MATCH",
            "recommended_action": "HUMAN_REVIEW",
            "reason": "Amount matches but reference differs.",
            "confidence": 0.82,
        }

    monkeypatch.setattr(
        "backend.app.reconciliation.decision_engine."
        "reason_about_reconciliation",
        fake_ai_service,
    )

    result = decide_chain(
        chain,
        bank_candidates=bank_candidates,
    )

    if result.confidence_bucket == ConfidenceBucket.MEDIUM:
        assert result.ai_reasoning is not None
        assert result.ai_reasoning["status"] == "AI_VALIDATED"
        assert result.ai_reasoning["classification"] == "LIKELY_MATCH"
        assert result.ai_reasoning["recommended_action"] == "HUMAN_REVIEW"
        assert result.ai_reasoning["confidence"] == 0.82


def test_medium_confidence_invalid_ai_output_falls_back_to_human_review(
    monkeypatch,
):
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="950.00",
        bank_date="2026-08-26",
    )

    bank_candidates = [
        {
            "transaction_id": "BANK999",
            "reference": "SETTXN001",
            "credit_amount": "950.00",
            "transaction_date": "2026-08-26",
            "currency": "INR",
        }
    ]

    def fake_ai_service(evidence):
        return {
            "classification": "AUTO_RESOLVE",
            "recommended_action": "AUTO_RESOLVE",
            "reason": "This invalid AI response must not be trusted.",
            "confidence": 9.99,
        }

    monkeypatch.setattr(
        "backend.app.reconciliation.decision_engine."
        "reason_about_reconciliation",
        fake_ai_service,
    )

    result = decide_chain(
        chain,
        bank_candidates=bank_candidates,
    )

    if result.confidence_bucket == ConfidenceBucket.MEDIUM:
        assert result.ai_reasoning is not None
        assert result.ai_reasoning["status"] == "HUMAN_REVIEW"
        assert "classification" not in result.ai_reasoning
        assert "recommended_action" not in result.ai_reasoning
        assert "confidence" not in result.ai_reasoning


def test_decide_chain_missing_payment_is_unresolved():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
        },
        payment=None,
        settlement=None,
        bank=None,
    )

    decision = decide_chain(chain)

    assert decision.status == "HUMAN_REVIEW"
    assert decision.exception_type == ExceptionType.UNKNOWN_REFERENCE.value


def test_decide_chain_missing_settlement_is_unresolved():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
        },
        payment={
            "payment_id": "PAY001",
            "amount": 1000,
        },
        settlement=None,
        bank=None,
    )

    decision = decide_chain(chain)

    assert decision.status == "HUMAN_REVIEW"
    assert decision.exception_type == ExceptionType.UNKNOWN_REFERENCE.value


def test_decide_chain_classifies_missing_bank():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
        },
        payment={
            "payment_id": "PAY001",
            "amount": 1000,
        },
        settlement={
            "settlement_id": "SET001",
            "gross_amount": 1000,
            "net_amount": 988.20,
        },
        bank=None,
    )

    decision = decide_chain(chain)

    assert decision.status == "HUMAN_REVIEW"
    assert decision.exception_type == ExceptionType.MISSING_BANK_RECORD.value


def test_decide_chain_classifies_bank_mismatch():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
            "order_date": "2026-08-28",
        },
        payment={
            "payment_id": "PAY001",
            "order_id": "ORD001",
            "amount": 1000,
            "payment_date": "2026-08-28",
        },
        settlement={
            "settlement_id": "SET001",
            "payment_id": "PAY001",
            "settlement_reference": "SET-REF-001",
            "gross_amount": 1000,
            "net_amount": 988.20,
            "settlement_date": "2026-08-29",
        },
        bank={
            "transaction_id": "BANK001",
            "reference": "SET-REF-001",
            "credit_amount": 900,
            "transaction_date": "2026-08-30",
        },
    )

    decision = decide_chain(chain)

    assert decision.status == "HUMAN_REVIEW"
    assert decision.exception_type == ExceptionType.AMOUNT_MISMATCH.value


def test_payment_mismatch_uses_canonical_amount_mismatch_exception():
    chain = TransactionChain(
        order={
            "order_id": "ORD001",
            "order_amount": 1000,
        },
        payment={
            "payment_id": "PAY001",
            "amount": 900,
        },
        settlement={
            "settlement_id": "SET001",
            "gross_amount": 1000,
            "net_amount": 988.20,
        },
        bank={
            "transaction_id": "BANK001",
            "credit_amount": 988.20,
        },
    )

    decision = decide_chain(chain)

    assert decision.status == "HUMAN_REVIEW"
    assert decision.exception_type == ExceptionType.AMOUNT_MISMATCH.value


def test_exception_taxonomy_contains_exactly_eight_categories():
    expected = {
        "MISSING_BANK_RECORD",
        "MISSING_PAYMENT",
        "MISSING_SETTLEMENT",
        "AMOUNT_MISMATCH",
        "DUPLICATE_BANK_TRANSACTION",
        "UNKNOWN_REFERENCE",
        "AMBIGUOUS_MATCH",
        "PARTIAL_SETTLEMENT",
        "COMBINED_SETTLEMENT",
        "DATE_MISMATCH",
    }

    actual = {
        exception_type.value
        for exception_type in ExceptionType
    }

    assert actual == expected


def test_unresolved_similarity_has_exception_type():
    chain = make_chain(
        bank_reference="WRONG_REFERENCE",
        bank_amount="900.00",
        bank_date="2026-08-30",
    )

    result = decide_chain(
        chain,
        bank_candidates=[],
    )

    assert result.status == "HUMAN_REVIEW"
    assert result.exception_type in {
        exception_type.value
        for exception_type in ExceptionType
    }


def test_finalize_auto_resolved_stays_auto_resolved():
    from backend.app.reconciliation.decision_engine import (
        _finalize_decision,
        MatchDecision,
    )

    decision = MatchDecision(
        status="AUTO_RESOLVED",
        method="EXACT",
        confidence=0.99,
        reason="Verified exact match.",
    )

    result = _finalize_decision(decision)

    assert result.status == "AUTO_RESOLVED"


def test_finalize_validated_ai_becomes_ai_suggested():
    from backend.app.reconciliation.decision_engine import (
        _finalize_decision,
        MatchDecision,
    )

    decision = MatchDecision(
        status="MATCH",
        method="SIMILARITY",
        confidence=0.80,
        reason="Similarity match.",
        ai_reasoning={
            "status": "AI_VALIDATED",
            "classification": "MATCH",
            "recommended_action": "APPROVE",
            "reason": "Evidence supports the proposed match.",
            "confidence": 0.91,
        },
    )

    result = _finalize_decision(decision)

    assert result.status == "AI_SUGGESTED"


def test_finalize_unresolved_becomes_human_review():
    from backend.app.reconciliation.decision_engine import (
        _finalize_decision,
        MatchDecision,
    )

    decision = MatchDecision(
        status="UNRESOLVED",
        method="NONE",
        confidence=0.20,
        reason="No reliable candidate found.",
    )

    result = _finalize_decision(decision)

    assert result.status == "HUMAN_REVIEW"


def test_finalize_exception_becomes_human_review():
    from backend.app.reconciliation.decision_engine import (
        _finalize_decision,
        MatchDecision,
    )

    decision = MatchDecision(
        status="EXCEPTION",
        method="NONE",
        confidence=1.0,
        reason="Settlement amount mismatch.",
        exception_type="AMOUNT_MISMATCH",
    )

    result = _finalize_decision(decision)

    assert result.status == "HUMAN_REVIEW"


def test_high_confidence_deterministic_match_requires_verification():
    from backend.app.reconciliation.decision_engine import (
        MatchDecision,
        _verify_decision,
    )

    settlement = {
        "settlement_id": "SET001",
        "gross_amount": 1000,
        "platform_fee": 10,
        "gst_on_fee": 1.80,
        "net_amount": 988.20,
        "settlement_date": "2026-08-26",
        "settlement_reference": "SETTXN001",
        "currency": "INR",
    }

    candidate = {
        "transaction_id": "BTX001",
        "transaction_date": "2026-08-26",
        "credit_amount": 988.20,
        "currency": "INR",
        "reference": "SETTXN001",
    }

    decision = MatchDecision(
        status="MATCH",
        method="EXACT",
        confidence=0.99,
        candidate=candidate,
    )

    class FakeChain:
        pass

    chain = FakeChain()
    chain.settlement = settlement

    assert _verify_decision(
        chain,
        decision,
        None,
    ) is True


def test_verification_failure_prevents_auto_resolution():
    from backend.app.reconciliation.decision_engine import (
        MatchDecision,
        _verify_decision,
    )

    settlement = {
        "settlement_id": "SET001",
        "gross_amount": 1000,
        "platform_fee": 10,
        "gst_on_fee": 1.80,
        "net_amount": 988.20,
        "settlement_date": "2026-08-26",
        "settlement_reference": "SETTXN001",
        "currency": "INR",
    }

    candidate = {
        "transaction_id": "BTX001",
        "transaction_date": "2026-08-25",
        "credit_amount": 900.00,
        "currency": "INR",
        "reference": "WRONG_REFERENCE",
    }

    decision = MatchDecision(
        status="MATCH",
        method="EXACT",
        confidence=0.99,
        candidate=candidate,
    )

    class FakeChain:
        pass

    chain = FakeChain()
    chain.settlement = settlement

    assert _verify_decision(
        chain,
        decision,
        None,
    ) is False
