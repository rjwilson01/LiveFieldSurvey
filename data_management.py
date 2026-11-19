import math

import pandas as pd
import streamlit as st

import exporter
import solver
import storage
from page_navigation import render_page_title_selector


storage.init_files()
trees = storage.load_trees()
measurements = storage.load_measurements(trees)
dataset_info = storage.load_dataset_info()
coords, solver_info = solver.run_network_adjustment(trees, measurements)

render_page_title_selector("Data management")
st.caption("Name, back up, transfer, or export a survey dataset.")

with st.expander("Dataset", expanded=True):
    st.write(f"**Active dataset:** {dataset_info['dataset_id']}")
    if dataset_info.get("not_downloaded", True):
        st.warning("Not downloaded · changes need a backup")
    else:
        st.success("Download requested")

    with st.form(f"dataset_name_form_{dataset_info['serial']}_{storage.safe_filename(dataset_info['name'])}"):
        dataset_name = st.text_input("Dataset name", value=dataset_info["name"])
        save_dataset_name = st.form_submit_button("Save name")
    if save_dataset_name:
        storage.rename_dataset(dataset_name)
        st.rerun()

    st.download_button(
        "Download complete dataset (ZIP)",
        data=exporter.build_dataset_bundle(dataset_info, trees, measurements),
        file_name=f"{storage.safe_filename(dataset_info['name'])}-{int(dataset_info['serial']):03d}.zip",
        mime="application/zip",
        key="management_dataset_backup_download",
        on_click=storage.mark_dataset_downloaded,
        help="Backup for restoring this survey, including its identity and retired Tree ID sequence.",
    )

    with st.container(border=True):
        st.subheader("Start a new dataset")
        st.caption("Creates fresh anchor Trees 1 and 2. The next Tree ID will be 3.")
        confirm_new_dataset = st.checkbox("I understand this replaces the active survey", key=f"confirm_new_dataset_{dataset_info['serial']}")
        with st.form(f"new_dataset_form_{dataset_info['serial']}"):
            new_dataset_name = st.text_input("New dataset name", value="Field Survey")
            start_new_dataset = st.form_submit_button("Start new dataset", type="primary", disabled=not confirm_new_dataset)
        if start_new_dataset:
            storage.replace_dataset(new_dataset_name, {1: (0, 0), 2: (0, 1)}, [], next_tree_id=3)
            st.session_state["tree_editor_values"] = {"id": 3, "x": 0, "y": 0}
            st.session_state["tree_form_revision"] = st.session_state.get("tree_form_revision", 0) + 1
            st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
            st.session_state["selected_measurement_index"] = None
            st.session_state["measurement_editor_values"] = {"from": 1, "to": 2, "distance": 1000}
            st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
            st.session_state["measurement_next_field"] = "from"
            st.session_state["highlight_pair"] = None
            st.session_state["map_revision"] = st.session_state.get("map_revision", 0) + 1
            st.rerun()

    upload_revision = st.session_state.get("dataset_upload_revision", 0)
    with st.container(border=True):
        st.subheader("Upload a saved dataset")
        uploaded_file = st.file_uploader("Dataset ZIP", type=["zip"], key=f"dataset_upload_{upload_revision}")
        if uploaded_file is not None:
            import hashlib

            upload_bytes = uploaded_file.getvalue()
            try:
                pending_upload = exporter.parse_dataset_bundle(upload_bytes)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.caption(f"File contains {pending_upload['source_id']} · {len(pending_upload['trees'])} trees · {len(pending_upload['measurements'])} measurements.")
                current_status = "has un-downloaded changes" if dataset_info.get("not_downloaded", True) else "has a requested backup"
                st.warning(f"Uploading will replace **{dataset_info['dataset_id']}** ({current_status}) and all its current trees and measurements. The uploaded dataset will receive a new serial number.")
                upload_token = hashlib.sha256(upload_bytes).hexdigest()[:12]
                confirmed = st.checkbox("I understand this replaces the active dataset", key=f"confirm_upload_{upload_token}")
                if st.button("Replace active dataset", type="primary", disabled=not confirmed, key=f"replace_dataset_{upload_token}"):
                    source_serial = pending_upload["source_serial"]
                    minimum_serial = source_serial + 1 if source_serial is not None else None
                    storage.replace_dataset(pending_upload["name"], pending_upload["trees"], pending_upload["measurements"], minimum_serial=minimum_serial, next_tree_id=pending_upload["next_tree_id"])
                    st.session_state["tree_editor_values"] = {"id": pending_upload["next_tree_id"], "x": 0, "y": 0}
                    st.session_state["tree_form_revision"] = st.session_state.get("tree_form_revision", 0) + 1
                    st.session_state["dataset_upload_revision"] = upload_revision + 1
                    st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
                    st.session_state["selected_measurement_index"] = None
                    st.session_state["measurement_editor_values"] = {"from": 1, "to": 2, "distance": 1000}
                    st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
                    st.session_state["measurement_next_field"] = "from"
                    st.session_state["map_revision"] = st.session_state.get("map_revision", 0) + 1
                    st.rerun()

with st.expander("Export survey", expanded=True):
    degree = {tree: 0 for tree in trees}
    adjacency = {tree: set() for tree in trees}
    for a, b, _ in measurements:
        if a in degree and b in degree:
            degree[a] += 1
            degree[b] += 1
            adjacency[a].add(b)
            adjacency[b].add(a)
    reachable = set()
    pending = [1] if 1 in adjacency else []
    while pending:
        current = pending.pop()
        if current not in reachable:
            reachable.add(current)
            pending.extend(adjacency[current] - reachable)
    underconstrained = {tree for tree in trees if tree not in (1, 2) and (tree not in reachable or degree[tree] < 3)}

    tree_rows = [{
        "Tree": tree,
        "Initial_X_mm": trees[tree][0],
        "Initial_Y_mm": trees[tree][1],
        "Adjusted_X_mm": coords.get(tree, (float("nan"), float("nan")))[0],
        "Adjusted_Y_mm": coords.get(tree, (float("nan"), float("nan")))[1],
        "Links": degree[tree],
        "Needs_more_measurements": tree in underconstrained,
    } for tree in sorted(trees)]

    if solver_info and solver_info["success"]:
        measurement_rows = []
        for a, b, measured in measurements:
            adjusted = math.dist(coords[a], coords[b])
            measurement_rows.append({"From": a, "To": b, "Meas": int(round(measured)), "Adj": int(round(adjusted)), "Δ": int(round(adjusted - measured))})
    else:
        measurement_rows = [{"From": a, "To": b, "Measured_mm": measured} for a, b, measured in measurements]

    exporter.export_survey(pd.DataFrame(tree_rows), pd.DataFrame(measurement_rows), dataset_info, trees, measurements)
