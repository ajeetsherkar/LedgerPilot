import json
import os

import requests
import streamlit as st
from pathlib import Path


st.set_page_config(
    page_title="LedgerPilot",
    page_icon="💳",
    layout="wide",
)


API_BASE_URL = os.getenv("LEDGERPILOT_API_URL", "http://localhost:8000").rstrip("/")


def upload_screen():
    st.title("Upload")
    st.write("Upload the four reconciliation source CSV files.")

    st.info(
        "All four files are required. LedgerPilot will validate the files "
        "before reconciliation."
    )

    orders = st.file_uploader(
        "Orders CSV",
        type=["csv"],
        key="orders",
    )

    payments = st.file_uploader(
        "Payments CSV",
        type=["csv"],
        key="payments",
    )

    settlements = st.file_uploader(
        "Settlements CSV",
        type=["csv"],
        key="settlements",
    )

    bank = st.file_uploader(
        "Bank CSV",
        type=["csv"],
        key="bank",
    )

    files = {
        "Orders": orders,
        "Payments": payments,
        "Settlements": settlements,
        "Bank": bank,
    }

    uploaded_count = sum(file is not None for file in files.values())

    st.caption(f"{uploaded_count}/4 files selected")

    if uploaded_count:
        st.write("Selected files:")
        for name, file in files.items():
            if file is not None:
                st.write(f"🟢 {name}: `{file.name}`")

    if st.button(
        "Run Reconciliation",
        type="primary",
        use_container_width=True,
    ):
        missing = [
            name
            for name, file in files.items()
            if file is None
        ]

        if missing:
            st.error(
                "Please select all four CSV files before running "
                f"reconciliation. Missing: {', '.join(missing)}."
            )
            return

        invalid = [
            name
            for name, file in files.items()
            if not file.name.lower().endswith(".csv")
        ]

        if invalid:
            st.error(
                "The following files must be CSV files: "
                f"{', '.join(invalid)}."
            )
            return

        upload_payload = {
            "orders": (
                orders.name,
                orders.getvalue(),
                "text/csv",
            ),
            "payments": (
                payments.name,
                payments.getvalue(),
                "text/csv",
            ),
            "settlements": (
                settlements.name,
                settlements.getvalue(),
                "text/csv",
            ),
            "bank": (
                bank.name,
                bank.getvalue(),
                "text/csv",
            ),
        }

        try:
            with st.spinner("Uploading and validating CSV files..."):
                upload_response = requests.post(
                    f"{API_BASE_URL}/upload",
                    files=upload_payload,
                    timeout=60,
                )

            if upload_response.status_code != 200:
                try:
                    detail = upload_response.json().get(
                        "detail",
                        "Upload failed.",
                    )
                except ValueError:
                    detail = "Upload failed with an unexpected response."

                st.error(f"Upload rejected: {detail}")
                return

            upload_data = upload_response.json()
            batch_id = upload_data.get("batch_id")

            if not batch_id:
                st.error("Upload succeeded but no batch ID was returned.")
                return

            st.success(
                f"Files uploaded successfully. Batch ID: `{batch_id}`"
            )

            st.write(
                f"**Records uploaded:** "
                f"{upload_data.get('records_uploaded', 0)}"
            )

            with st.spinner("Running reconciliation..."):
                reconciliation_response = requests.post(
                    f"{API_BASE_URL}/reconciliation/run",
                    json={"batch_id": batch_id},
                    timeout=120,
                )

            if reconciliation_response.status_code != 200:
                try:
                    detail = reconciliation_response.json().get(
                        "detail",
                        "Reconciliation failed.",
                    )
                except ValueError:
                    detail = (
                        "Reconciliation failed with an unexpected response."
                    )

                st.error(f"Reconciliation failed: {detail}")
                return

            result = reconciliation_response.json()

            st.success("Reconciliation completed successfully.")

            st.subheader("Run Summary")

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Total", result.get("total", 0))
            col2.metric(
                "Auto-resolved",
                result.get("auto_resolved", 0),
            )
            col3.metric(
                "AI-suggested",
                result.get("ai_suggested", 0),
            )
            col4.metric(
                "Human review",
                result.get("human_review", 0),
            )

            st.caption(f"Batch ID: `{result.get('batch_id', batch_id)}`")

        except requests.exceptions.Timeout:
            st.error(
                "The backend request timed out. "
                "Please verify that the LedgerPilot API is running."
            )
        except requests.exceptions.ConnectionError:
            st.error(
                "Could not connect to the LedgerPilot API. "
                f"Expected API at `{API_BASE_URL}`."
            )
        except requests.exceptions.RequestException as exc:
            st.error(f"Backend request failed: {type(exc).__name__}.")
        except ValueError:
            st.error(
                "The backend returned an invalid response. "
                "Please check the API logs."
            )


def dashboard_screen():
    st.title("Dashboard")
    st.write("Live reconciliation summary from the backend.")

    try:
        response = requests.get(
            f"{API_BASE_URL}/results",
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        st.error("The results request timed out. Please try again.")
        return
    except requests.exceptions.ConnectionError:
        st.error(
            f"Could not connect to the LedgerPilot API at {API_BASE_URL}."
        )
        return
    except requests.exceptions.RequestException as exc:
        st.error(f"Could not load reconciliation results: {exc}")
        return

    try:
        payload = response.json()
    except ValueError:
        st.error("The results API returned an invalid response.")
        return

    # The backend normally returns the reconciliation records as a list.
    # Also support common wrapped response shapes without hardcoding values.
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = None

        for key in ("results", "data", "items"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                records = candidate
                break

        if records is None:
            records = []
    else:
        st.error("The results API returned an unexpected response format.")
        return

    total = len(records)

    auto_resolved = 0
    ai_suggested = 0
    human_review = 0

    for record in records:
        if not isinstance(record, dict):
            continue

        status = (
            record.get("status")
            or record.get("decision")
            or record.get("final_status")
            or ""
        )

        status = str(status).upper()

        if status == "AUTO_RESOLVED":
            auto_resolved += 1
        elif status == "AI_SUGGESTED":
            ai_suggested += 1
        elif status == "HUMAN_REVIEW":
            human_review += 1

    st.subheader("Reconciliation Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total", total)

    with col2:
        st.metric("Auto-resolved", auto_resolved)

    with col3:
        st.metric("AI-suggested", ai_suggested)

    with col4:
        st.metric("Human review", human_review)

    st.subheader("Held-out Evaluation Metrics")

    metrics_path = (
        Path(__file__).resolve().parent.parent
        / "evaluation"
        / "results"
        / "held_out_metrics.json"
    )

    if not metrics_path.exists():
        st.error(
            "Frozen held-out evaluation metrics are unavailable."
        )
        return

    try:
        metrics_payload = json.loads(metrics_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        st.error(
            f"Could not load frozen held-out evaluation metrics: {exc}"
        )
        return

    required_metrics = [
        "match_rate",
        "precision",
        "recall",
        "f1",
        "auto_resolution_precision",
    ]

    missing_metrics = [
        metric
        for metric in required_metrics
        if metric not in metrics_payload
        or not isinstance(metrics_payload[metric], (int, float))
    ]

    if missing_metrics:
        st.error(
            "Frozen held-out evaluation metrics are incomplete: "
            + ", ".join(missing_metrics)
        )
        return

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = (
        st.columns(5)
    )

    with metric_col1:
        st.metric(
            "Match rate",
            f"{metrics_payload['match_rate']:.2%}",
        )

    with metric_col2:
        st.metric(
            "Precision",
            f"{metrics_payload['precision']:.2%}",
        )

    with metric_col3:
        st.metric(
            "Recall",
            f"{metrics_payload['recall']:.2%}",
        )

    with metric_col4:
        st.metric(
            "F1",
            f"{metrics_payload['f1']:.2%}",
        )

    with metric_col5:
        st.metric(
            "Auto-resolution precision",
            f"{metrics_payload['auto_resolution_precision']:.2%}",
        )


def exceptions_screen():
    st.title("Exceptions")
    st.write("Review reconciliation exceptions and their categories.")

    canonical_exception_types = [
        "MISSING_BANK_RECORD",
        "AMOUNT_MISMATCH",
        "DUPLICATE_BANK_TRANSACTION",
        "UNKNOWN_REFERENCE",
        "AMBIGUOUS_MATCH",
        "PARTIAL_SETTLEMENT",
        "COMBINED_SETTLEMENT",
        "DATE_MISMATCH",
        "MISSING_PAYMENT",
        "MISSING_SETTLEMENT",
    ]

    try:
        response = requests.get(
            f"{API_BASE_URL}/exceptions",
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout:
        st.error("The backend timed out while loading exceptions.")
        return
    except requests.ConnectionError:
        st.error(
            "Could not connect to the LedgerPilot backend. "
            "Make sure FastAPI is running."
        )
        return
    except requests.RequestException as exc:
        st.error(f"Failed to load exceptions: {exc}")
        return
    except ValueError:
        st.error("The backend returned an invalid exceptions response.")
        return

    if not isinstance(payload, dict):
        st.error("Invalid exceptions response from backend.")
        return

    exceptions = payload.get("exceptions", [])

    if not isinstance(exceptions, list):
        st.error("Invalid exceptions data returned by backend.")
        return

    st.metric("Total exceptions", len(exceptions))

    available_types = {
        str(item.get("exception_type"))
        for item in exceptions
        if isinstance(item, dict) and item.get("exception_type")
    }

    filter_options = [
        exception_type
        for exception_type in canonical_exception_types
        if exception_type in available_types
    ]

    category_options = ["All categories"] + filter_options

    selected_category = st.selectbox(
        "Exception Category",
        category_options,
    )

    filtered_exceptions = exceptions

    if selected_category != "All categories":
        filtered_exceptions = [
            item
            for item in exceptions
            if isinstance(item, dict)
            and item.get("exception_type") == selected_category
        ]

    if not filtered_exceptions:
        st.info("No exceptions match the selected category.")
        return

    table_rows = []

    for item in filtered_exceptions:
        amount = item.get("amount")

        if amount is None:
            display_amount = "—"
        else:
            try:
                display_amount = f"{float(amount):,.2f}"
            except (TypeError, ValueError):
                display_amount = str(amount)

        table_rows.append(
            {
                "ID": item.get("exception_id", "—"),
                "Type": item.get("exception_type", "—"),
                "Amount": display_amount,
                "Status": item.get("status", "—"),
            }
        )

    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
    )


def transaction_detail_screen():
    st.title("Transaction Detail")
    st.write(
        "Inspect the evidence chain, deterministic verification, "
        "and final decision."
    )

    try:
        response = requests.get(
            f"{API_BASE_URL}/results",
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout:
        st.error("The backend timed out while loading reconciliation results.")
        return
    except requests.ConnectionError:
        st.error(
            "Could not connect to the LedgerPilot backend. "
            "Make sure FastAPI is running."
        )
        return
    except requests.RequestException as exc:
        st.error(f"Failed to load reconciliation results: {exc}")
        return
    except ValueError:
        st.error("The backend returned an invalid results response.")
        return

    if isinstance(payload, list):
        results = payload
    elif isinstance(payload, dict):
        results = payload.get("results")
        if results is None:
            results = payload.get("data")
        if results is None:
            results = payload.get("items")
    else:
        results = None

    if not isinstance(results, list):
        st.error("Invalid reconciliation results returned by backend.")
        return

    valid_results = [
        item
        for item in results
        if isinstance(item, dict) and item.get("result_id")
    ]

    if not valid_results:
        st.info("No reconciliation results are available.")
        return

    result_options = [
        item["result_id"]
        for item in valid_results
    ]

    selected_result_id = st.selectbox(
        "Select Transaction",
        result_options,
    )

    try:
        detail_response = requests.get(
            f"{API_BASE_URL}/results/{selected_result_id}",
            timeout=10,
        )
        detail_response.raise_for_status()
        detail = detail_response.json()
    except requests.Timeout:
        st.error("The backend timed out while loading transaction details.")
        return
    except requests.ConnectionError:
        st.error(
            "Could not connect to the LedgerPilot backend. "
            "Make sure FastAPI is running."
        )
        return
    except requests.RequestException as exc:
        st.error(f"Failed to load transaction details: {exc}")
        return
    except ValueError:
        st.error(
            "The backend returned an invalid transaction detail response."
        )
        return

    if not isinstance(detail, dict):
        st.error("Invalid transaction detail response from backend.")
        return

    status = detail.get("status", "UNKNOWN")
    method = detail.get("method", "UNKNOWN")
    confidence = detail.get("confidence")

    st.divider()

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

    with summary_col1:
        st.metric("Decision", status)

    with summary_col2:
        st.metric("Method", method)

    with summary_col3:
        if isinstance(confidence, (int, float)):
            st.metric("Confidence", f"{float(confidence):.2%}")
        else:
            st.metric("Confidence", "—")

    with summary_col4:
        st.metric(
            "Confidence bucket",
            detail.get("confidence_bucket", "—"),
        )

    st.subheader("Evidence Chain")

    evidence_chain = detail.get("evidence_chain") or {}

    order = evidence_chain.get("order") or {}
    payment = evidence_chain.get("payment") or {}
    settlement = evidence_chain.get("settlement") or {}
    bank = evidence_chain.get("bank") or {}

    evidence_columns = st.columns(4)

    with evidence_columns[0]:
        st.markdown("### Order")
        st.write(
            f"**ID:** "
            f"{order.get('id', detail.get('order_id', '—'))}"
        )
        st.write(f"**Amount:** {order.get('amount', '—')}")
        st.write(f"**Currency:** {order.get('currency', '—')}")
        st.write(f"**Date:** {order.get('date', '—')}")

    with evidence_columns[1]:
        st.markdown("### Payment")
        st.write(
            f"**ID:** "
            f"{payment.get('id', detail.get('payment_id', '—'))}"
        )
        st.write(f"**Amount:** {payment.get('amount', '—')}")
        st.write(f"**Currency:** {payment.get('currency', '—')}")
        st.write(f"**Date:** {payment.get('date', '—')}")

    with evidence_columns[2]:
        st.markdown("### Settlement")
        st.write(
            f"**ID:** "
            f"{settlement.get('id', detail.get('settlement_id', '—'))}"
        )
        st.write(f"**Gross:** {settlement.get('gross_amount', '—')}")
        st.write(f"**Fee:** {settlement.get('platform_fee', '—')}")
        st.write(f"**GST:** {settlement.get('gst_on_fee', '—')}")
        st.write(f"**Net:** {settlement.get('net_amount', '—')}")
        st.write(f"**Date:** {settlement.get('date', '—')}")
        st.write(
            f"**Reference:** "
            f"{settlement.get('reference', '—')}"
        )

    with evidence_columns[3]:
        st.markdown("### Bank")

        if bank:
            st.write(
                f"**ID:** "
                f"{bank.get('id', detail.get('bank_transaction_id', '—'))}"
            )
            st.write(f"**Credit:** {bank.get('credit_amount', '—')}")
            st.write(f"**Currency:** {bank.get('currency', '—')}")
            st.write(f"**Date:** {bank.get('date', '—')}")
            st.write(f"**Reference:** {bank.get('reference', '—')}")
            st.write(f"**Narration:** {bank.get('narration', '—')}")
        else:
            st.warning(
                "No final bank transaction was selected. "
                "The system did not resolve a bank record."
            )

    st.divider()

    st.subheader("Verification Checklist")

    verification = detail.get("verification") or {}

    verification_items = [
        ("Amount", "amount"),
        ("Fee", "fee"),
        ("Date", "date"),
        ("Currency", "currency"),
        ("Reference", "reference"),
        ("Uniqueness", "uniqueness"),
    ]

    verification_rows = []

    for label, key in verification_items:
        check = verification.get(key) or {}
        result_label = check.get("status", "—")

        verification_rows.append(
            {
                "Check": label,
                "Result": result_label,
            }
        )

    st.dataframe(
        verification_rows,
        use_container_width=True,
        hide_index=True,
    )

    verification_reasons = verification.get("reasons") or []

    if verification_reasons:
        with st.expander("Verification details"):
            for reason in verification_reasons:
                st.write(f"• {reason}")

    st.divider()

    st.subheader("Why this decision?")

    explanation = detail.get("decision_explanation") or {}
    explanation_text = detail.get("reason") or "No explanation available."

    if status == "AUTO_RESOLVED":
        st.success(
            f"**AUTO_RESOLVED** — {explanation_text}"
        )

        st.write(
            f"**Evidence matched:** "
            f"{explanation.get('method', method)}"
        )

        if isinstance(confidence, (int, float)):
            st.write(
                f"**Final confidence:** {float(confidence):.2%}"
            )

        st.write(
            "The selected evidence passed deterministic verification "
            "before the transaction was automatically resolved."
        )

    elif status == "AI_SUGGESTED":
        st.info(
            f"**AI_SUGGESTED** — {explanation_text}"
        )

        ai_reasoning = detail.get("ai_reasoning") or {}

        if ai_reasoning.get("status") == "AI_VALIDATED":
            st.markdown("### AI Reasoning")

            ai_col1, ai_col2 = st.columns(2)

            with ai_col1:
                st.write(
                    f"**Classification:** "
                    f"{ai_reasoning.get('classification', '—')}"
                )
                st.write(
                    f"**Recommended action:** "
                    f"{ai_reasoning.get('recommended_action', '—')}"
                )

            with ai_col2:
                ai_confidence = ai_reasoning.get("confidence")

                if isinstance(ai_confidence, (int, float)):
                    st.write(
                        f"**AI confidence:** "
                        f"{float(ai_confidence):.2%}"
                    )
                else:
                    st.write("**AI confidence:** —")

                st.write(
                    f"**Validation status:** "
                    f"{ai_reasoning.get('status', '—')}"
                )

            st.write(
                f"**Reason:** "
                f"{ai_reasoning.get('reason', 'No AI reason available.')}"
            )

        else:
            st.warning(
                "AI reasoning is not available as a validated structured response."
            )

    elif status == "HUMAN_REVIEW":
        st.warning(
            f"**HUMAN_REVIEW** — {explanation_text}"
        )
        ambiguity = detail.get("ambiguity") or {}
        top_two = ambiguity.get("top_two_candidates") or []
        if len(top_two) >= 2:
            st.write("**Closest candidates:**")
            candidate_rows = []
            for candidate in top_two[:2]:
                score = candidate.get("score")
                if isinstance(score, (int, float)):
                    display_score = f"{float(score):.2%}"
                else:
                    display_score = "—"
                candidate_rows.append(
                    {
                        "Candidate": candidate.get(
                            "transaction_id",
                            "—",
                        ),
                        "Amount": candidate.get(
                            "credit_amount",
                            "—",
                        ),
                        "Reference": candidate.get(
                            "reference",
                            "—",
                        ),
                        "Score": display_score,
                    }
                )
            st.dataframe(
                candidate_rows,
                use_container_width=True,
                hide_index=True,
            )
            score_margin = ambiguity.get("margin_percentage_points")
            if isinstance(score_margin, (int, float)):
                st.write(
                    f"**Score difference:** "
                    f"{float(score_margin):.2f} percentage points"
                )

        escalation = detail.get("escalation_policy") or {}
        st.info(
            f"**Escalation policy:** "
            f"{escalation.get('trigger', 'Configured ambiguity policy')}"
        )
        st.write(
            "**Action:** "
            f"{escalation.get('action', 'HUMAN_REVIEW')}"
        )

        review_id = detail.get("review_id")
        review_record = None

        if not review_id:
            batch_id = detail.get("batch_id")
            reviews = []

            try:
                if batch_id:
                    review_response = requests.get(
                        f"{API_BASE_URL}/reconciliation/{batch_id}/reviews",
                        timeout=10,
                    )
                    review_response.raise_for_status()
                    review_payload = review_response.json()

                    if isinstance(review_payload, list):
                        reviews = review_payload
                    elif isinstance(review_payload, dict):
                        reviews = (
                            review_payload.get("reviews")
                            or review_payload.get("data")
                            or review_payload.get("items")
                            or []
                        )
            except requests.RequestException as exc:
                st.warning(f"Could not load human review details: {exc}")

            for review in reviews:
                if not isinstance(review, dict):
                    continue
                if (
                    review.get("result_id") == selected_result_id
                    or (
                        review.get("order_id") == detail.get("order_id")
                        and review.get("payment_id") == detail.get("payment_id")
                        and review.get("settlement_id") == detail.get("settlement_id")
                    )
                ):
                    review_id = review.get("review_id")
                    review_record = review
                    break

        if review_id:
            st.markdown("### Human Review")

            if review_record is None:
                try:
                    review_response = requests.get(
                        f"{API_BASE_URL}/reconciliation/"
                        f"{detail.get('batch_id')}/reviews/{review_id}",
                        timeout=10,
                    )
                    review_response.raise_for_status()
                    review_payload = review_response.json()
                    if isinstance(review_payload, dict):
                        review_record = review_payload.get("review") or review_payload
                except requests.RequestException as exc:
                    st.warning(f"Could not load human review status: {exc}")

            final_decision = (
                review_record.get("final_decision")
                if isinstance(review_record, dict)
                else None
            )

            if final_decision:
                reviewer_name = (
                    review_record.get("reviewer")
                    or "—"
                )
                review_reason = (
                    review_record.get("reason")
                    or "No review reason available."
                )
                reviewed_at = (
                    review_record.get("reviewed_at")
                    or "—"
                )

                if final_decision == "APPROVE":
                    st.success("**Human Review — APPROVED**")
                elif final_decision == "REJECT":
                    st.error("**Human Review — REJECTED**")
                else:
                    st.info(
                        f"**Human Review — {final_decision}**"
                    )

                st.write(f"**Reviewer:** {reviewer_name}")
                st.write(f"**Review reason:** {review_reason}")
                st.write(f"**Reviewed at:** {reviewed_at}")
            else:
                reviewer = st.text_input(
                    "Reviewer",
                    key=f"reviewer_{selected_result_id}",
                    placeholder="Enter reviewer name",
                )

                reason = st.text_area(
                    "Review reason",
                    key=f"review_reason_{selected_result_id}",
                    placeholder="Explain why you approve or reject this transaction.",
                )

                action_col1, action_col2 = st.columns(2)

                def resolve_human_review(decision):
                    if not reviewer.strip():
                        st.error("Reviewer is required.")
                        return

                    if not reason.strip():
                        st.error("Review reason is required.")
                        return

                    endpoint = (
                        f"{API_BASE_URL}/reconciliation/"
                        f"{detail.get('batch_id')}/reviews/"
                        f"{review_id}/{decision}"
                    )

                    try:
                        response = requests.post(
                            endpoint,
                            json={
                                "reviewer": reviewer.strip(),
                                "reason": reason.strip(),
                            },
                            timeout=10,
                        )
                        response.raise_for_status()
                    except requests.ConnectionError:
                        st.error(
                            "Could not connect to the LedgerPilot backend. "
                            "Make sure FastAPI is running."
                        )
                        return
                    except requests.RequestException as exc:
                        try:
                            error_detail = response.json().get("detail")
                        except (AttributeError, ValueError):
                            error_detail = None

                        st.error(
                            error_detail
                            or f"Failed to resolve human review: {exc}"
                        )
                        return

                    st.success(
                        f"Review {decision.upper()}D successfully."
                    )
                    st.rerun()

                with action_col1:
                    if st.button(
                        "Approve",
                        type="primary",
                        use_container_width=True,
                        key=f"approve_{selected_result_id}",
                    ):
                        resolve_human_review("approve")

                with action_col2:
                    if st.button(
                        "Reject",
                        use_container_width=True,
                        key=f"reject_{selected_result_id}",
                    ):
                        resolve_human_review("reject")

        else:
            st.warning(
                "No human review record is available for this transaction."
            )
    else:
        st.info(
            f"**{status}** — {explanation_text}"
        )



SCREENS = {
    "Upload": upload_screen,
    "Dashboard": dashboard_screen,
    "Exceptions": exceptions_screen,
    "Transaction Detail": transaction_detail_screen,
}


st.sidebar.title("LedgerPilot")
screen = st.sidebar.radio("Navigate", list(SCREENS.keys()))

SCREENS[screen]()
