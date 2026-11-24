import streamlit as st

import storage
from page_navigation import render_page_title_selector


storage.init_files()
dataset_info = storage.load_dataset_info()
active_dataset_pk = st.session_state["active_spreadsheet_id"]
datasets = storage.list_datasets()
active_dataset = next((item for item in datasets if item["spreadsheet_id"] == active_dataset_pk), None)

render_page_title_selector("Data management")
st.caption("Choose a survey dataset in the sidebar. Tree and measurement edits are saved directly to Neon PostgreSQL.")

import_result = st.session_state.pop("_google_import_result", None)
if import_result:
    st.success(f"Copied {len(import_result['imported'])} dataset(s) into Neon.")
    if import_result["skipped"]:
        st.info(f"Already copied: {', '.join(import_result['skipped'])}")
    if import_result["failures"]:
        st.warning("Some datasets could not be copied: " + "; ".join(import_result["failures"]))

with st.expander("Active dataset", expanded=True):
    st.write(f"**Dataset:** {dataset_info['dataset_id']}")
    st.write("**Storage:** Neon PostgreSQL")
    if active_dataset and active_dataset.get("source_spreadsheet_id"):
        st.write("This dataset was copied from Google Sheets; the source spreadsheet is unchanged.")
        st.link_button("Open this spreadsheet in Google Sheets", active_dataset["url"], width="content")

    with st.form(f"rename_dataset_{active_dataset_pk}"):
        new_name = st.text_input("Dataset name", value=dataset_info["name"])
        rename = st.form_submit_button("Rename dataset")
    if rename:
        storage.rename_dataset(new_name)
        st.rerun()

with st.expander("Start a new dataset", expanded=False):
    st.caption("Creates a new Neon dataset. Tree IDs start at 3 after the two anchor trees.")
    with st.form("new_google_sheets_dataset"):
        new_dataset_name = st.text_input("New dataset name", value="Field Survey")
        create = st.form_submit_button("Create new dataset", type="primary")
    if create:
        created = storage.create_dataset(new_dataset_name)
        st.session_state["_dataset_to_activate"] = created["spreadsheet_id"]
        st.rerun()

if storage.google_sheets_migration_available():
    with st.expander("Copy existing datasets from Google Sheets", expanded=False):
        st.caption("Copies datasets from your configured Surveys folder into Neon. It does not modify or delete the original spreadsheets.")
        if st.button("Copy datasets into Neon", key="copy_sheets_to_neon"):
            try:
                result = storage.import_google_sheets_datasets()
                st.session_state["_google_import_result"] = result
                st.rerun()
            except Exception as exc:
                st.error("Could not copy the Google Sheets datasets into Neon.")
                st.exception(exc)
