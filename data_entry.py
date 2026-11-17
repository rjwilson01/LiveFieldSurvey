import math

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

import exporter
import solver
import storage


st.title("🌳 Live Field Survey")
st.caption("Record tree-to-tree tape distances and adjust the map with least squares. Coordinates and tape distances are in millimetres.")

storage.init_files()
trees = storage.load_trees()
measurements = storage.load_measurements(trees)
directed_measurements = {}
for a, b, distance in measurements:
    directed_measurements[(a, b)] = distance
duplicate_measurements_collapsed = len(measurements) - len(directed_measurements)
if duplicate_measurements_collapsed:
    measurements = [(a, b, distance) for (a, b), distance in directed_measurements.items()]
    storage.save_measurements(measurements)
    storage.mark_dataset_dirty()
tree_ids = sorted(trees)

def persist_trees():
    storage.save_trees(trees)
    storage.mark_dataset_dirty()

def persist_measurements():
    storage.save_measurements(measurements)
    storage.mark_dataset_dirty()

def mark_dataset_downloaded():
    storage.mark_dataset_downloaded()


dataset_info = storage.load_dataset_info()
coords, solver_info = solver.run_network_adjustment(trees, measurements)


with st.sidebar:
    st.header("Dataset")
    st.write(f"**{dataset_info['dataset_id']}**")
    if dataset_info.get("not_downloaded", True):
        st.error("Not downloaded · changes need a backup")
    else:
        st.success("Download requested")
    st.download_button(
        "Download complete dataset (ZIP)",
        data=exporter.build_dataset_bundle(dataset_info, trees, measurements),
        file_name=f"{storage.safe_filename(dataset_info['name'])}-{int(dataset_info['serial']):03d}.zip",
        mime="application/zip",
        key="sidebar_dataset_backup_download",
        on_click=mark_dataset_downloaded,
        help="Backup for restoring this survey, including tree estimates and measurements.",
        width="stretch",
    )
    with st.form(f"dataset_name_form_{dataset_info['serial']}_{storage.safe_filename(dataset_info['name'])}"):
        dataset_name = st.text_input("Dataset name", value=dataset_info["name"])
        save_dataset_name = st.form_submit_button("Save name")
    if save_dataset_name:
        storage.rename_dataset(dataset_name)
        st.rerun()

    with st.expander("Start a new dataset"):
        st.caption("Creates a fresh survey with anchor Trees 1 and 2. The next tree ID will be 3.")
        with st.form(f"new_dataset_form_{dataset_info['serial']}"):
            new_dataset_name = st.text_input("New dataset name", value="Field Survey")
            confirm_new_dataset = st.checkbox("I understand this replaces the active survey")
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
    with st.expander("Upload a saved dataset"):
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
                st.warning(f"Uploading will replace **{dataset_info['dataset_id']}** ({current_status}) and all of its current trees and measurements. The uploaded dataset will be assigned a new serial number.")
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

    st.divider()
    st.header("Tree management")
    if "tree_editor_values" not in st.session_state:
        st.session_state["tree_editor_values"] = {"id": int(dataset_info.get("next_tree_id", max(tree_ids, default=0) + 1)), "x": 0, "y": 0}
    tree_form_revision = st.session_state.get("tree_form_revision", 0)
    editor_values = st.session_state["tree_editor_values"]
    next_tree_id = max(int(dataset_info.get("next_tree_id", 3)), max(tree_ids, default=2) + 1)
    valid_tree_choices = sorted(set(tree_ids) | {next_tree_id})
    selected_tree_id = int(editor_values["id"])
    if selected_tree_id not in valid_tree_choices:
        selected_tree_id = next_tree_id
    tree_id = int(st.selectbox("Tree ID", valid_tree_choices, index=valid_tree_choices.index(selected_tree_id), key=f"tree_id_{tree_form_revision}"))
    tree_exists = tree_id in trees
    editor_values = st.session_state.get("tree_editor_values", {})
    if int(editor_values.get("id", -1)) == tree_id and editor_values.get("pending_map_pick"):
        current_x, current_y = int(editor_values["x"]), int(editor_values["y"])
    else:
        current_x, current_y = trees.get(tree_id, (0, 0))
    st.session_state["tree_editor_values"] = {"id": tree_id, "x": int(current_x), "y": int(current_y)}
    tree_form_key = f"tree_management_{tree_form_revision}_{tree_id}"
    with st.form(tree_form_key):
        left, right = st.columns(2)
        with left:
            estimate_x = st.number_input("Initial X", min_value=0, value=int(current_x), step=100, disabled=tree_id in (1, 2), key=f"tree_x_{tree_form_revision}_{tree_id}")
        with right:
            estimate_y = st.number_input("Initial Y", min_value=0, value=int(current_y), step=100, disabled=tree_id == 1, key=f"tree_y_{tree_form_revision}_{tree_id}")
        add_col, delete_col = st.columns(2)
        with add_col:
            save_tree = st.form_submit_button("Update tree" if tree_exists else "Add tree", disabled=tree_id == 1, width="stretch")
        with delete_col:
            delete_tree = st.form_submit_button("Delete tree", disabled=not tree_exists or tree_id in (1, 2), width="stretch")

    if save_tree:
        if tree_exists:
            if tree_id == 1:
                st.error("Tree 1 is fixed at the origin.")
            else:
                trees[tree_id] = (0 if tree_id == 2 else int(estimate_x), int(estimate_y))
                persist_trees()
                st.session_state["tree_editor_values"] = {"id": tree_id, "x": int(trees[tree_id][0]), "y": int(trees[tree_id][1])}
                st.session_state["tree_form_revision"] = tree_form_revision + 1
                st.rerun()
        elif tree_id < next_tree_id:
            st.error(f"Tree IDs are not reused. The next available ID is {next_tree_id}.")
        else:
            trees[tree_id] = (int(estimate_x), int(estimate_y))
            storage.mark_tree_id_used(tree_id)
            persist_trees()
            st.session_state["tree_editor_values"] = {"id": tree_id, "x": int(estimate_x), "y": int(estimate_y)}
            st.session_state["tree_form_revision"] = tree_form_revision + 1
            st.rerun()
    if delete_tree:
        if tree_id in (1, 2):
            st.error("Tree 1 and Tree 2 are protected anchors.")
        elif tree_id not in trees:
            st.error(f"Tree {tree_id} does not exist.")
        else:
            del trees[int(tree_id)]
            measurements = [(a, b, d) for a, b, d in measurements if int(tree_id) not in (a, b)]
            persist_trees()
            persist_measurements()
            st.session_state["selected_measurement_index"] = None
            st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
            valid_tree_ids = sorted(trees)
            st.session_state["measurement_editor_values"] = {"from": valid_tree_ids[0], "to": valid_tree_ids[1], "distance": 1000}
            st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
            st.session_state["measurement_next_field"] = "from"
            st.session_state["tree_editor_values"] = {"id": next_tree_id, "x": 0, "y": 0}
            st.session_state["tree_form_revision"] = tree_form_revision + 1
            st.rerun()
    if tree_id in coords:
        adjusted_x, adjusted_y = coords[tree_id]
        location_label = "Calculated location" if solver_info and solver_info["success"] else "Adjusted location so far"
        st.text_input(location_label, value=f"X {int(round(adjusted_x))} · Y {int(round(adjusted_y))} mm", disabled=True, key=f"tree_location_{tree_form_revision}_{tree_id}")
    elif tree_exists:
        st.text_input("Calculated location", value="Not available yet", disabled=True, key=f"tree_location_{tree_form_revision}_{tree_id}")

    st.divider()
    st.header("Measurement")
    if "measurement_editor_values" not in st.session_state:
        first, second = (tree_ids[0], tree_ids[1]) if len(tree_ids) > 1 else (1, 2)
        st.session_state["measurement_editor_values"] = {"from": first, "to": second, "distance": 1000}
    if "measurement_next_field" not in st.session_state:
        st.session_state["measurement_next_field"] = "from"
    measurement_revision = st.session_state.get("measurement_form_revision", 0)
    selected_measurement_index = st.session_state.get("selected_measurement_index")
    if selected_measurement_index is not None and not 0 <= selected_measurement_index < len(measurements):
        selected_measurement_index = None
        st.session_state["selected_measurement_index"] = None
    measurement_values = st.session_state["measurement_editor_values"]
    from_default = measurement_values.get("from", tree_ids[0] if tree_ids else 1)
    if from_default not in tree_ids:
        from_default = tree_ids[0] if tree_ids else 1
    to_default = measurement_values.get("to", tree_ids[1] if len(tree_ids) > 1 else from_default)
    if to_default not in tree_ids or to_default == from_default:
        to_default = next((tree for tree in tree_ids if tree != from_default), from_default)
    if selected_measurement_index is not None:
        st.caption(f"Editing record #{selected_measurement_index + 1}. Use Cancel row edit to return to adding.")
    with st.form(f"measurement_editor_{measurement_revision}"):
        left, right = st.columns(2)
        with left:
            from_active = st.session_state["measurement_next_field"] == "from"
            with st.container(border=True, key="from-picker"):
                from_tree = st.selectbox("From tree", tree_ids, index=tree_ids.index(from_default), key=f"measurement_from_{measurement_revision}")
        with right:
            current_to_default = to_default if to_default != from_tree else next((tree for tree in tree_ids if tree != from_tree), from_tree)
            to_active = st.session_state["measurement_next_field"] == "to"
            with st.container(border=True, key="to-picker"):
                to_tree = st.selectbox("To tree", tree_ids, index=tree_ids.index(current_to_default), key=f"measurement_to_{measurement_revision}")
        distance = st.number_input("Distance (mm)", min_value=1, value=int(measurement_values.get("distance", 1000)), step=1, key=f"measurement_distance_{measurement_revision}")
        save_col, delete_col = st.columns(2)
        with save_col:
            save_measurement = st.form_submit_button("Update measurement" if selected_measurement_index is not None else "Add measurement", disabled=len(tree_ids) < 2, width="stretch")
        if selected_measurement_index is not None:
            with delete_col:
                delete_measurement = st.form_submit_button("Delete measurement", width="stretch")
            cancel_measurement_edit = st.form_submit_button("Cancel row edit")
        else:
            delete_measurement = False
            cancel_measurement_edit = False

    if save_measurement:
        if from_tree == to_tree:
            st.error("Choose two different trees.")
        else:
            if selected_measurement_index is None:
                duplicate = any(a == int(from_tree) and b == int(to_tree) for a, b, _ in measurements)
                if duplicate:
                    st.error(f"Tree {from_tree} → Tree {to_tree} already has a measurement. Select its row to update it.")
                else:
                    measurements.append((int(from_tree), int(to_tree), float(distance)))
                    persist_measurements()
            elif 0 <= selected_measurement_index < len(measurements):
                duplicate = any(index != selected_measurement_index and a == int(from_tree) and b == int(to_tree) for index, (a, b, _) in enumerate(measurements))
                if duplicate:
                    st.error(f"Tree {from_tree} → Tree {to_tree} already has a measurement. Choose another direction or pair.")
                else:
                    measurements[selected_measurement_index] = (int(from_tree), int(to_tree), float(distance))
                    persist_measurements()
            if not duplicate:
                st.session_state["measurement_editor_values"] = {"from": int(from_tree), "to": int(to_tree), "distance": int(distance)}
                st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
                st.session_state["measurement_form_revision"] = measurement_revision + 1
                st.rerun()
    if cancel_measurement_edit:
        st.session_state["selected_measurement_index"] = None
        st.session_state["measurement_form_revision"] = measurement_revision + 1
        st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
        st.rerun()
    if delete_measurement:
        if selected_measurement_index is not None and 0 <= selected_measurement_index < len(measurements):
            measurements.pop(selected_measurement_index)
            persist_measurements()
            st.session_state["selected_measurement_index"] = None
            st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
            st.session_state["measurement_form_revision"] = measurement_revision + 1
            st.rerun()

    st.divider()
    st.header("Deviation alerts")
    distance_tolerance = st.number_input("Moderate distance residual (mm)", min_value=0.0, value=50.0, step=10.0)
    estimate_tolerance = st.number_input("Large shift from estimate (mm)", min_value=0.0, value=1000.0, step=100.0)


st.subheader("Live map")
if not solver_info or not solver_info["baseline_measured"]:
    st.caption("Baseline guidance is on the Help page.")
show_estimates = st.checkbox("Show initial estimates", value=st.session_state.get("show_initial_estimates", False), key="show_initial_estimates")

degree = {t: 0 for t in tree_ids}
adjacency = {t: set() for t in tree_ids}
for a, b, _ in measurements:
    if a in degree and b in degree:
        degree[a] += 1
        degree[b] += 1
        adjacency[a].add(b)
        adjacency[b].add(a)
reachable = set()
stack = [1] if 1 in adjacency else []
while stack:
    current = stack.pop()
    if current not in reachable:
        reachable.add(current)
        stack.extend(adjacency[current] - reachable)
underconstrained = {t for t in tree_ids if t not in (1, 2) and (t not in reachable or degree[t] < 3)}

fig = go.Figure()
if coords:
    # Faint grid targets make a tap on the map a quick approximate placement
    # gesture on touch screens. Numeric estimate fields remain available too.
    extent_points = list(trees.values()) + list(coords.values())
    max_x = max(1000, max(p[0] for p in extent_points) + 1000)
    max_y = max(1000, max(p[1] for p in extent_points) + 1000)
    x_padding = max(100, int(max_x * 0.03))
    y_padding = max(100, int(max_y * 0.03))
    grid_x = np.linspace(0, max_x, 25)
    grid_y = np.linspace(0, max_y, 25)
    tap_points = [(float(x), float(y)) for x in grid_x for y in grid_y]
    fig.add_trace(go.Scatter(x=[p[0] for p in tap_points], y=[p[1] for p in tap_points], customdata=tap_points, mode="markers", marker={"size": 18, "color": "rgba(100,116,139,0.20)"}, hovertemplate="Tap to set starting estimate<br>X %{x:.0f} mm<br>Y %{y:.0f} mm<extra></extra>", showlegend=False, name="Tap to place estimate"))
    for measurement_index, (a, b, d) in enumerate(measurements):
        if a in coords and b in coords:
            xa, ya = coords[a]
            xb, yb = coords[b]
            midpoint_x, midpoint_y = (xa + xb) / 2, (ya + yb) / 2
            line_color = "#f97316" if st.session_state.get("highlight_pair") == tuple(sorted((a, b))) else "#9aa4b2"
            fig.add_trace(go.Scatter(x=[xa, midpoint_x, xb], y=[ya, midpoint_y, yb], mode="lines+markers", line={"color": line_color, "width": 3 if line_color == "#f97316" else 2}, marker={"size": [1, 18, 1], "color": [line_color, "rgba(100,116,139,0.015)", line_color]}, customdata=[[measurement_index, a, b]] * 3, hovertemplate=f"{a} → {b}: {d:.0f} mm<extra></extra>", showlegend=False))

    # Optional estimates are hidden by default so they cannot obscure tree taps.
    fig.add_trace(go.Scatter(x=[trees[t][0] for t in tree_ids], y=[trees[t][1] for t in tree_ids], mode="markers", name="Initial estimates", visible=show_estimates, showlegend=False, marker={"symbol": "circle-open", "size": 12, "color": "#64748b", "line": {"width": 2}}, text=[str(t) for t in tree_ids], hovertemplate="Initial estimate · Tree %{text}<br>X %{x:.0f} mm<br>Y %{y:.0f} mm<extra></extra>"))
    colors = ["#f59e0b" if t in underconstrained else ("#2563eb" if t in (1, 2) else "#15803d") for t in tree_ids]
    fig.add_trace(go.Scatter(x=[coords[t][0] for t in tree_ids], y=[coords[t][1] for t in tree_ids], mode="markers+text", name="Adjusted positions", text=[str(t) for t in tree_ids], textposition="top center", marker={"size": 15, "color": colors, "line": {"color": "white", "width": 1}}, customdata=[[degree[t], t in underconstrained, t] for t in tree_ids], hovertemplate="Tree %{text}<br>X %{x:.0f} mm<br>Y %{y:.0f} mm<br>Links: %{customdata[0]}<extra></extra>"))
fig.update_layout(height=620, margin={"l": 10, "r": 10, "t": 20, "b": 10}, xaxis={"title": "X (mm)", "range": [-x_padding if coords else -100, max_x if coords else 1000], "zeroline": True, "scaleanchor": "y", "scaleratio": 1, "constrain": "domain", "constraintoward": "left"}, yaxis={"title": "Y (mm)", "range": [-y_padding if coords else -100, max_y if coords else 1000], "zeroline": True, "constrain": "domain", "constraintoward": "bottom"}, legend={"orientation": "h", "y": 1.02})
map_revision = st.session_state.get("map_revision", 0)
fig.update_layout(autosize=True, uirevision="survey-map-view")
active_picker = "from-picker" if st.session_state["measurement_next_field"] == "from" else "to-picker"
st.markdown(f"<style>.st-key-{active_picker} [data-testid='stVerticalBlockBorderWrapper'] {{ border: 3px solid #16a34a !important; border-radius: 0.75rem; }}</style>", unsafe_allow_html=True)
map_event = st.plotly_chart(fig, key=f"survey_map_{map_revision}", on_select="rerun", selection_mode="points", config={"responsive": True, "scrollZoom": False})
try:
    selected_points = map_event.selection.points
except (AttributeError, TypeError):
    selected_points = []
for point in sorted(selected_points, key=lambda selected: selected.get("curve_number") == 0):
    curve_number = point.get("curve_number")
    if curve_number == 0:
        tap_x, tap_y = point.get("customdata", (point.get("x"), point.get("y")))
        selected_estimate_tree = int(st.session_state["tree_editor_values"]["id"])
        if selected_estimate_tree != 1:
            tap_x, tap_y = int(round(tap_x)), int(round(tap_y))
            if selected_estimate_tree == 2:
                tap_x = 0
            st.session_state["tree_editor_values"] = {"id": selected_estimate_tree, "x": tap_x, "y": tap_y, "pending_map_pick": True}
            st.session_state["tree_form_revision"] = st.session_state.get("tree_form_revision", 0) + 1
            st.session_state["map_revision"] = map_revision + 1
            st.rerun()
    line_start, line_end = 1, 1 + len(measurements)
    if curve_number is not None and line_start <= curve_number < line_end:
        _, a, b = point.get("customdata", (None, None, None))
        st.session_state["highlight_pair"] = tuple(sorted((int(a), int(b))))
        st.session_state["map_revision"] = map_revision + 1
        st.rerun()
    tree_curve = line_end + 1
    if curve_number == tree_curve and point.get("customdata"):
        tree = int(point["customdata"][2])
        initial_x, initial_y = trees[tree]
        if tree == 1:
            initial_x, initial_y = 0, 0
        elif tree == 2:
            initial_x = 0
        st.session_state["tree_editor_values"] = {"id": tree, "x": int(round(initial_x)), "y": int(round(initial_y))}
        st.session_state["tree_form_revision"] = st.session_state.get("tree_form_revision", 0) + 1
        measurement_values = st.session_state.get("measurement_editor_values", {"from": tree_ids[0], "to": tree_ids[1], "distance": 1000})
        from_selected = int(measurement_values.get("from", tree_ids[0]))
        to_selected = int(measurement_values.get("to", tree_ids[1]))
        next_field = st.session_state.get("measurement_next_field", "from")
        if tree == from_selected:
            next_field = "to"
        elif tree == to_selected:
            next_field = "from"
        elif next_field == "from":
            from_selected = tree
            next_field = "to"
        else:
            to_selected = tree
            next_field = "from"
        st.session_state["measurement_editor_values"] = {
            "from": from_selected,
            "to": to_selected,
            "distance": measurement_values.get("distance", 1000),
        }
        st.session_state["measurement_next_field"] = next_field
        st.session_state["selected_measurement_index"] = None
        st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
        st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
        st.session_state["map_revision"] = map_revision + 1
        st.rerun()
st.caption("Gray lines show measurements; amber trees need more links or a connection to the anchored network.")

if solver_info and solver_info["success"]:
    moved = []
    residual_rows = []
    for t in tree_ids:
        shift = math.dist(trees[t], coords[t])
        if t not in (1, 2) and shift > estimate_tolerance:
            moved.append((t, shift))
    for a, b, d in measurements:
        predicted = math.dist(coords[a], coords[b])
        residual = predicted - d
        residual_rows.append({"From": a, "To": b, "Meas": int(round(d)), "Adj": int(round(predicted)), "Δ": int(round(residual))})
    for t, shift in moved:
        st.warning(f"Tree {t} moved {shift:.0f} mm from its saved initial estimate. Review the estimate or add/check measurements.")
    high_residual_count = sum(abs(row["Δ"]) > distance_tolerance for row in residual_rows)
    if high_residual_count:
        st.warning(f"{high_residual_count} measurement(s) exceed the residual threshold; they are highlighted in the table below.")
elif measurements:
    st.warning(solver_info["message"] if solver_info else "The network needs Trees 1 and 2 to calculate positions.")

st.subheader("Measurement records")
if duplicate_measurements_collapsed:
    st.warning(f"Found {duplicate_measurements_collapsed} duplicate directed record(s); kept the last saved value for each From → To pair.")
if measurements:
    table_rows = []
    for record_id, (a, b, d) in enumerate(measurements):
        residual_row = residual_rows[record_id] if solver_info and solver_info["success"] else {}
        table_rows.append({
            "#": record_id + 1,
            "Pair": f"{min(a, b)} ↔ {max(a, b)}",
            "From": a,
            "To": b,
            "Meas": int(round(d)),
            "Adj": residual_row.get("Adj"),
            "Δ": residual_row.get("Δ"),
            "_record_id": record_id,
            "_pair": tuple(sorted((a, b))),
        })
    table_df = pd.DataFrame(table_rows).sort_values(["_pair", "_record_id"], kind="stable").reset_index(drop=True)
    visible_df = table_df.drop(columns=["_record_id", "_pair"])
    selected_measurement = st.session_state.get("selected_measurement_index")
    highlighted_pair = st.session_state.get("highlight_pair")

    def row_style(row):
        source = table_df.iloc[row.name]
        if source["_pair"] == highlighted_pair:
            return ["background-color: #ffedd5"] * len(row)
        residual = source["Δ"]
        if pd.notna(residual) and abs(residual) > distance_tolerance:
            return ["background-color: #fee2e2"] * len(row)
        return [""] * len(row)

    table_event = st.dataframe(
        visible_df.style.apply(row_style, axis=1),
        width="stretch",
        hide_index=True,
        key=f"measurement_table_{st.session_state.get('measurement_table_revision', 0)}",
        on_select="rerun",
        selection_mode="single-row",
    )
    try:
        selected_rows = table_event.selection.rows
    except (AttributeError, TypeError):
        selected_rows = []
    if selected_rows:
        row_num = selected_rows[0]
        selected_measurement = int(table_df.iloc[row_num]["_record_id"])
        selected_record = measurements[selected_measurement]
        selection_changed = selected_measurement != st.session_state.get("selected_measurement_index")
        editor_values_changed = st.session_state.get("measurement_editor_values") != {
            "from": selected_record[0], "to": selected_record[1], "distance": int(round(selected_record[2]))
        }
        st.session_state["selected_measurement_index"] = selected_measurement
        selected_pair = table_df.iloc[row_num]["_pair"]
        pair_changed = st.session_state.get("highlight_pair") != selected_pair
        if pair_changed:
            st.session_state["highlight_pair"] = selected_pair
        if selection_changed or editor_values_changed:
            st.session_state["measurement_editor_values"] = {
                "from": selected_record[0], "to": selected_record[1], "distance": int(round(selected_record[2]))
            }
            st.session_state["measurement_next_field"] = "from"
            st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
        if pair_changed or selection_changed or editor_values_changed:
            st.rerun()

else:
    st.caption("No tape measurements recorded yet.")

st.caption("Notes: Tree 1 is at the lower-left origin and Tree 2 is above it on the Y axis. Tap a grid point to set the selected tree's starting estimate; then Add or Update in the sidebar. Tree marker taps fill From and To. Tap a measurement line to highlight records for that tree pair.")
st.caption("Measurements are grouped by tree pair; each From → To reading remains a separate record. Δ = adjusted minus measured, rounded to whole millimetres. Click a row to load it into the Measurement editor in the sidebar.")

st.subheader("Export survey")
exporter.export_survey(
    pd.DataFrame([{"Tree": t, "Initial_X_mm": trees[t][0], "Initial_Y_mm": trees[t][1], "Adjusted_X_mm": coords.get(t, (float("nan"), float("nan")))[0], "Adjusted_Y_mm": coords.get(t, (float("nan"), float("nan")))[1], "Links": degree[t], "Needs_more_measurements": t in underconstrained} for t in tree_ids]),
    pd.DataFrame(residual_rows if solver_info and solver_info["success"] else [{"From": a, "To": b, "Measured_mm": d} for a, b, d in measurements]),
    dataset_info,
    trees,
    measurements,
    on_download=mark_dataset_downloaded,
)
