import faulthandler

faulthandler.enable()

import streamlit as st
import storage
from page_navigation import PAGE_TITLES, render_page_title_selector


st.set_page_config(
    page_title="Live Field Survey Network",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    is_logged_in = st.user.is_logged_in
except AttributeError:
    st.error("Google sign-in is not configured. Follow the OAuth setup in README.md and add it to Streamlit Secrets.")
    st.stop()

if not is_logged_in:
    st.title("🌳 Live Field Survey")
    st.write("Sign in with your Google account to access the survey app.")
    st.button("Sign in with Google", on_click=st.login, type="primary")
    st.stop()

try:
    allowed_email = str(st.secrets["app"]["allowed_email"]).strip().lower()
except (KeyError, FileNotFoundError):
    st.error("Set app.allowed_email in Streamlit Secrets to the Google account allowed to use this survey.")
    st.stop()

if str(st.user.get("email", "")).strip().lower() != allowed_email:
    st.error("This app is restricted to the Google account configured in app.allowed_email.")
    st.button("Sign out", on_click=st.logout)
    st.stop()


pages = [
    st.Page("map_page.py", title="Map", icon="🗺️"),
    st.Page("tablet_data_entry.py", title="Data Entry", icon="📝"),
    st.Page("data_entry.py", title="Data Entry & Mapping", icon="📍", default=True),
    st.Page("help_page.py", title="Help", icon="❔"),
    st.Page("data_management.py", title="Data management", icon="🗂️"),
]
pages_by_title = {page.title: page for page in pages}
pg = st.navigation(pages, position="hidden")
tablet_page = pg.title in ("Map", "Data Entry")

st.markdown("""
<style>
[data-testid="stHeader"] { position: sticky; top: 0; z-index: 1000; }
[data-testid="stSidebar"] > div:first-child { overflow-y: auto; }
section.main .block-container { padding-top: 1rem; padding-bottom: 1rem; gap: 0.7rem; }
section.main [data-testid="stVerticalBlock"] { gap: 0.7rem; }
</style>
""", unsafe_allow_html=True)
if tablet_page:
    st.markdown("""
    <style>
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    section.main { margin-left: 0 !important; }
    </style>
    """, unsafe_allow_html=True)

try:
    datasets = storage.list_datasets()
except Exception as exc:
    st.error("Neon PostgreSQL storage could not be reached.")
    st.info("Check DATABASE_URL in Streamlit Secrets and the Neon project status.")
    st.exception(exc)
    st.stop()

dataset_by_id = {dataset["dataset_pk"]: dataset for dataset in datasets}
pending_dataset = st.session_state.pop("_dataset_to_activate", None)
if pending_dataset in dataset_by_id:
    st.session_state["active_dataset_pk"] = pending_dataset

if not datasets:
    render_page_title_selector(pg.title)
    st.title("Connect a survey dataset")
    st.caption("Create a dataset in Neon to begin recording trees and measurements.")
    name = st.text_input("First dataset name", value="Field Survey", key="first_dataset_name")
    if st.button("Create first dataset", type="primary"):
        created = storage.create_dataset(name)
        st.session_state["active_dataset_pk"] = created["dataset_pk"]
        st.rerun()
    st.stop()

dataset_ids = list(dataset_by_id)
active_id = st.session_state.get("active_dataset_pk")
if active_id not in dataset_by_id:
    active_id = dataset_ids[0]
    st.session_state["active_dataset_pk"] = active_id
if st.session_state.get("dataset_selector") not in dataset_by_id or pending_dataset in dataset_by_id:
    st.session_state["dataset_selector"] = active_id


def select_active_dataset():
    st.session_state["active_dataset_pk"] = st.session_state["dataset_selector"]


def navigate_to_selected_page():
    selected_title = st.session_state["app_page_selector"]
    st.session_state["page_title_selector"] = selected_title
    st.switch_page(pages_by_title[selected_title])


if not tablet_page:
    with st.sidebar:
        st.title("🌳 Live Field Survey")
        st.button("Sign out", on_click=st.logout)
        st.selectbox(
            "Survey dataset",
            options=dataset_ids,
            format_func=lambda dataset_pk: dataset_by_id[dataset_pk]["dataset_id"],
            key="dataset_selector",
            on_change=select_active_dataset,
        )
        st.caption("Changes save directly to Neon PostgreSQL.")
        st.caption(f"Active: {dataset_by_id[st.session_state['active_dataset_pk']]['dataset_id']}")
        st.divider()
        st.selectbox(
            "Page",
            options=PAGE_TITLES,
            index=PAGE_TITLES.index(pg.title),
            key="app_page_selector",
            on_change=navigate_to_selected_page,
        )

storage.sync_anchor_baseline(st.session_state["active_dataset_pk"])
active_dataset = storage.load_dataset_info(st.session_state["active_dataset_pk"])
st.session_state["map_axis_layout"] = active_dataset.get("map_axis_layout", storage.DEFAULT_MAP_ORIENTATION["map_axis_layout"])
st.session_state["mirror_map_x"] = bool(active_dataset.get("mirror_map_x", False))
st.session_state["mirror_map_y"] = bool(active_dataset.get("mirror_map_y", False))
st.session_state.setdefault("show_initial_estimates_setting", False)
st.session_state.setdefault("show_starting_targets_setting", True)
st.session_state.setdefault("show_initial_estimates", st.session_state["show_initial_estimates_setting"])
st.session_state.setdefault("show_starting_targets", st.session_state["show_starting_targets_setting"])
st.session_state.setdefault("survey_ledger", [])
st.session_state.setdefault("tree_estimates", {})

pg.run()
