import streamlit as st
import storage
from page_navigation import PAGE_TITLES

st.set_page_config(
    page_title="Live Field Survey Network",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* Keep the app header, including the sidebar toggle, reachable on long pages. */
[data-testid="stHeader"] { position: sticky; top: 0; z-index: 1000; }
[data-testid="stSidebar"] > div:first-child { overflow-y: auto; }
section.main .block-container { padding-top: 1rem; padding-bottom: 1rem; gap: 0.7rem; }
section.main [data-testid="stVerticalBlock"] { gap: 0.7rem; }
</style>
""", unsafe_allow_html=True)

try:
    is_logged_in = st.user.is_logged_in
except AttributeError:
    st.error("Google sign-in is not configured. Follow the OAuth setup in README.md and add it to Streamlit Secrets.")
    st.stop()

if not is_logged_in:
    st.title("🌳 Live Field Survey")
    st.write("Sign in with your Google account to access the survey spreadsheets in your configured Drive folder.")
    st.button("Sign in with Google", on_click=st.login, type="primary")
    st.stop()

try:
    allowed_email = str(st.secrets["google_sheets"]["allowed_email"]).strip().lower()
except (KeyError, FileNotFoundError):
    st.error("Set google_sheets.allowed_email in Streamlit Secrets to the Google account that owns the survey folder.")
    st.stop()

if str(st.user.get("email", "")).strip().lower() != allowed_email:
    st.error("This app is restricted to the Google account configured for the survey folder.")
    st.button("Sign out", on_click=st.logout)
    st.stop()

def select_active_dataset():
    st.session_state["active_spreadsheet_id"] = st.session_state["dataset_selector"]


try:
    datasets = storage.list_datasets()
except Exception as exc:
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status == 401:
        st.error("Your Google API access token has expired. Sign out and sign in again to reconnect.")
        st.button("Sign out and reconnect", on_click=st.logout)
    else:
        st.error("Google Sheets storage could not be reached.")
        st.info("Check the Google OAuth settings, requested scopes, and configured Drive folder in README.md.")
    st.exception(exc)
    st.stop()

dataset_by_id = {dataset["spreadsheet_id"]: dataset for dataset in datasets}
pending_dataset = st.session_state.pop("_dataset_to_activate", None)
if pending_dataset in dataset_by_id:
    st.session_state["active_spreadsheet_id"] = pending_dataset

if not datasets:
    with st.sidebar:
        st.title("🌳 Live Field Survey")
        st.info("No survey spreadsheets found in the configured Drive folder.")
        first_dataset_name = st.text_input("First dataset name", value="Field Survey", key="first_dataset_name")
        if st.button("Create first dataset", type="primary", width="stretch"):
            created = storage.create_dataset(first_dataset_name)
            st.session_state["active_spreadsheet_id"] = created["spreadsheet_id"]
            st.rerun()
    st.title("Connect a survey spreadsheet")
    st.caption("Create the first survey dataset in Google Sheets to begin recording trees and measurements.")
    st.stop()

dataset_ids = list(dataset_by_id)
active_id = st.session_state.get("active_spreadsheet_id")
if active_id not in dataset_by_id:
    active_id = dataset_ids[0]
    st.session_state["active_spreadsheet_id"] = active_id
if st.session_state.get("dataset_selector") not in dataset_by_id or pending_dataset in dataset_by_id:
    st.session_state["dataset_selector"] = active_id

with st.sidebar:
    st.title("🌳 Live Field Survey")
    st.button("Sign out", on_click=st.logout)
    st.selectbox(
        "Dataset spreadsheet",
        options=dataset_ids,
        format_func=lambda spreadsheet_id: dataset_by_id[spreadsheet_id]["dataset_id"],
        key="dataset_selector",
        on_change=select_active_dataset,
    )
    st.caption("Changes save directly to Google Sheets.")
    st.divider()

active_id = st.session_state["active_spreadsheet_id"]
active_dataset = storage.load_dataset_info(active_id)
with st.sidebar:
    st.caption(f"Active: {active_dataset['dataset_id']}")
# These values are also used by widgets on the Help page. Reload them on each
# app run because Streamlit may discard widget state when navigating away from
# the page containing those widgets.
st.session_state["map_axis_layout"] = active_dataset.get("map_axis_layout", storage.DEFAULT_MAP_ORIENTATION["map_axis_layout"])
st.session_state["mirror_map_x"] = bool(active_dataset.get("mirror_map_x", False))
st.session_state["mirror_map_y"] = bool(active_dataset.get("mirror_map_y", False))
st.session_state.setdefault("show_initial_estimates_setting", False)
st.session_state.setdefault("show_starting_targets_setting", True)
st.session_state["show_initial_estimates"] = st.session_state["show_initial_estimates_setting"]
st.session_state["show_starting_targets"] = st.session_state["show_starting_targets_setting"]
# Ensure data arrays survive page-swaps in global context memory
if "survey_ledger" not in st.session_state:
    st.session_state["survey_ledger"] = []

if "tree_estimates" not in st.session_state:
    st.session_state["tree_estimates"] = {}

# Set up routing mapping
data_entry_page = st.Page(
    page="data_entry.py", 
    title="Data Entry & Mapping", 
    icon="📝", 
    default=True
)

help_page = st.Page(page="help_page.py", title="Help", icon="❔")
data_management_page = st.Page(page="data_management.py", title="Data management", icon="🗂️")

pages = [data_entry_page, help_page, data_management_page]
pages_by_title = {page.title: page for page in pages}
pg = st.navigation(pages, position="hidden")


def navigate_to_selected_page():
    selected_title = st.session_state["app_page_selector"]
    st.session_state["page_title_selector"] = selected_title
    target_page = pages_by_title[selected_title]
    st.switch_page(target_page)


st.sidebar.selectbox(
    "Page",
    options=PAGE_TITLES,
    index=PAGE_TITLES.index(pg.title),
    key="app_page_selector",
    on_change=navigate_to_selected_page,
)
pg.run()
