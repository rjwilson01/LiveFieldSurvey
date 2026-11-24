import streamlit as st

import storage
from page_navigation import render_page_title_selector


storage.init_files()
dataset_info = storage.load_dataset_info()
active_spreadsheet_id = st.session_state["active_spreadsheet_id"]
datasets = storage.list_datasets()
active_dataset = next((item for item in datasets if item["spreadsheet_id"] == active_spreadsheet_id), None)

render_page_title_selector("Data management")
st.caption("Choose a survey spreadsheet in the sidebar. Tree and measurement edits are written to Google Sheets as you work.")

with st.expander("Active dataset", expanded=True):
    st.write(f"**Dataset:** {dataset_info['dataset_id']}")
    st.write(f"**Google spreadsheet:** {active_spreadsheet_id}")
    if active_dataset:
        st.link_button("Open this spreadsheet in Google Sheets", active_dataset["url"], width="content")

    with st.form(f"rename_dataset_{active_spreadsheet_id}"):
        new_name = st.text_input("Dataset name", value=dataset_info["name"])
        rename = st.form_submit_button("Rename dataset")
    if rename:
        storage.rename_dataset(new_name)
        st.rerun()

with st.expander("Start a new dataset", expanded=False):
    st.caption("Creates a new Google spreadsheet with Trees, Measurements, and Dataset tabs. Tree IDs start at 3 after the two anchor trees.")
    with st.form("new_google_sheets_dataset"):
        new_dataset_name = st.text_input("New dataset name", value="Field Survey")
        create = st.form_submit_button("Create new dataset", type="primary")
    if create:
        created = storage.create_dataset(new_dataset_name)
        st.session_state["_dataset_to_activate"] = created["spreadsheet_id"]
        st.rerun()
