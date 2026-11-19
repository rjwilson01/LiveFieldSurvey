import streamlit as st


PAGE_PATHS = {
    "Data Entry & Mapping": "data_entry.py",
    "Help": "help_page.py",
    "Data management": "data_management.py",
}
PAGE_TITLES = tuple(PAGE_PATHS)


def _switch_from_page_title():
    selected_title = st.session_state["page_title_selector"]
    st.session_state["app_page_selector"] = selected_title
    st.switch_page(PAGE_PATHS[selected_title])


def render_page_title_selector(current_title):
    # Reset the shared widget to match the page selected by either dropdown.
    st.session_state["page_title_selector"] = current_title
    # A segmented control has no editable/searchable text field, so password
    # managers such as RoboForm do not treat the page title as a form input.
    st.segmented_control(
        "Page",
        options=PAGE_TITLES,
        key="page_title_selector",
        on_change=_switch_from_page_title,
        label_visibility="collapsed",
        selection_mode="single",
        width="content",
    )
