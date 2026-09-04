import streamlit as st


st.set_page_config(
    page_title="LedgerPilot",
    page_icon="💳",
    layout="wide",
)


def upload_screen():
    st.title("Upload")
    st.write("Upload reconciliation source files here.")


def dashboard_screen():
    st.title("Dashboard")
    st.write("Reconciliation summary and evaluation metrics will appear here.")


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
