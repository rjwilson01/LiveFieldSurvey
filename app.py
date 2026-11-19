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

storage.init_files()
active_dataset = storage.load_dataset_info()
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
with st.sidebar:
    st.title("🌳 Live Field Survey")
    if active_dataset.get("not_downloaded", True):
        st.warning(f"Dataset: {active_dataset['dataset_id']} · backup needed")
    else:
        st.caption(active_dataset["dataset_id"])
    st.divider()

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
