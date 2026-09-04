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
    st.write("Reconciliation exceptions will appear here.")


def transaction_detail_screen():
    st.title("Transaction Detail")
    st.write("Transaction evidence and decision explanation will appear here.")


SCREENS = {
    "Upload": upload_screen,
    "Dashboard": dashboard_screen,
    "Exceptions": exceptions_screen,
    "Transaction Detail": transaction_detail_screen,
}


st.sidebar.title("LedgerPilot")
screen = st.sidebar.radio("Navigate", list(SCREENS.keys()))

SCREENS[screen]()
