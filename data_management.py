import streamlit as st

import storage
from page_navigation import render_page_title_selector


storage.init_files()
dataset_info = storage.load_dataset_info()
active_dataset_pk = st.session_state["active_dataset_pk"]

render_page_title_selector("Data management")
st.caption("Choose a survey dataset in the sidebar. Tree and measurement edits are saved directly to Neon PostgreSQL.")

with st.expander("Active dataset", expanded=True):
    st.write(f"**Dataset:** {dataset_info['dataset_id']}")
    st.write("**Storage:** Neon PostgreSQL")

    with st.form(f"rename_dataset_{active_dataset_pk}"):
        new_name = st.text_input("Dataset name", value=dataset_info["name"])
        rename = st.form_submit_button("Rename dataset")
    if rename:
        storage.rename_dataset(new_name)
        st.rerun()

with st.expander("Start a new dataset", expanded=False):
    st.caption("Creates a new Neon dataset. Tree IDs start at 3 after the two anchor trees.")
    with st.form("new_neon_dataset"):
        new_dataset_name = st.text_input("New dataset name", value="Field Survey")
        create = st.form_submit_button("Create new dataset", type="primary")
    if create:
        created = storage.create_dataset(new_dataset_name)
        st.session_state["_dataset_to_activate"] = created["dataset_pk"]
        st.rerun()
