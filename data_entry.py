import math

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

import solver
import storage
from page_navigation import render_page_title_selector


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


def sync_tree2_to_baseline():
    baseline_readings = [distance for a, b, distance in measurements if {a, b} == {1, 2}]
    if not baseline_readings or 2 not in trees:
        return False
    old_x, old_y = trees[2]
    anchor_axis = 0 if old_x > old_y else 1
    baseline_distance = max(0, int(round(sum(baseline_readings) / len(baseline_readings))))
    baseline_position = (baseline_distance, 0) if anchor_axis == 0 else (0, baseline_distance)
    if trees[2] == baseline_position:
        return False
    trees[2] = baseline_position
    storage.save_trees(trees)
    storage.mark_dataset_dirty()
    return True


sync_tree2_to_baseline()
tree_ids = sorted(trees)

def persist_trees():
    storage.save_trees(trees)
    storage.mark_dataset_dirty()

def persist_measurements():
    storage.save_measurements(measurements)
    # The solver constrains Tree 2 to the mean baseline on its selected axis.
    sync_tree2_to_baseline()
    storage.mark_dataset_dirty()

dataset_info = storage.load_dataset_info()
coords, solver_info = solver.run_network_adjustment(trees, measurements)
swap_map_axes = st.session_state.get("map_axis_layout", "X horizontal, Y vertical") == "Y horizontal, X vertical"
mirror_map_x = bool(st.session_state.get("mirror_map_x", False))
mirror_map_y = bool(st.session_state.get("mirror_map_y", False))


def survey_to_map(x, y):
    signed_x = -x if mirror_map_x else x
    signed_y = -y if mirror_map_y else y
    return (signed_y, signed_x) if swap_map_axes else (signed_x, signed_y)


def map_to_survey(map_x, map_y):
    signed_x, signed_y = (map_y, map_x) if swap_map_axes else (map_x, map_y)
    return (-signed_x if mirror_map_x else signed_x, -signed_y if mirror_map_y else signed_y)


def calculatable_tree_ids():
    if not solver_info or not solver_info.get("success") or not solver_info.get("baseline_measured"):
        return set()
    links = {tree: 0 for tree in tree_ids}
    neighbors = {tree: set() for tree in tree_ids}
    for a, b, _ in measurements:
        if a in links and b in links:
            links[a] += 1
            links[b] += 1
            neighbors[a].add(b)
            neighbors[b].add(a)
    reachable = set()
    pending = [1]
    while pending:
        tree = pending.pop()
        if tree not in reachable:
            reachable.add(tree)
            pending.extend(neighbors[tree] - reachable)
    return {tree for tree in tree_ids if tree in (1, 2) or (tree in reachable and links[tree] >= 3)}


def suggested_measurement_distance(from_tree, to_tree):
    if int(from_tree) == int(to_tree):
        return 1
    recorded = next((d for a, b, d in measurements if a == int(from_tree) and b == int(to_tree)), None)
    if recorded is not None:
        return max(1, int(round(recorded)))
    calculatable = calculatable_tree_ids()
    from_position = coords[int(from_tree)] if int(from_tree) in calculatable else trees[int(from_tree)]
    to_position = coords[int(to_tree)] if int(to_tree) in calculatable else trees[int(to_tree)]
    return max(1, int(round(math.dist(from_position, to_position))))


with st.sidebar:
    with st.expander("Tree management", expanded=False):
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
        elif tree_id in trees:
            current_x, current_y = trees[tree_id]
        elif int(editor_values.get("id", -1)) != tree_id:
            # Moving the editor to the next unused ID should carry the current
            # rough estimate forward instead of resetting it to the origin.
            current_x, current_y = int(editor_values.get("x", 0)), int(editor_values.get("y", 0))
        else:
            current_x, current_y = 0, 0
        st.session_state["tree_editor_values"] = {"id": tree_id, "x": int(current_x), "y": int(current_y)}
        tree_form_key = f"tree_management_{tree_form_revision}_{tree_id}"
        tree2_has_baseline = any({a, b} == {1, 2} for a, b, _ in measurements)
        with st.form(tree_form_key):
            tree2_axis = "X" if tree_id == 2 and current_x > current_y else "Y"
            if tree_id == 2:
                tree2_axis = st.selectbox(
                    "Tree 2 reference axis",
                    ("Y", "X"),
                    index=0 if tree2_axis == "Y" else 1,
                    help="Tree 2 stays on one positive axis. A 1 ↔ 2 measurement sets its distance along this axis.",
                    key=f"tree2_axis_{tree_form_revision}",
                )
            left, right = st.columns(2)
            with left:
                estimate_x = st.number_input("Initial X", min_value=0, value=int(current_x), step=100, disabled=tree_id == 1 or (tree_id == 2 and tree2_has_baseline), key=f"tree_x_{tree_form_revision}_{tree_id}")
            with right:
                estimate_y = st.number_input("Initial Y", min_value=0, value=int(current_y), step=100, disabled=tree_id == 1 or (tree_id == 2 and tree2_has_baseline), key=f"tree_y_{tree_form_revision}_{tree_id}")
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
                    if tree_id == 2:
                        baseline_readings = [d for a, b, d in measurements if {a, b} == {1, 2}]
                        estimated_distance = int(estimate_x) if tree2_axis == "X" else int(estimate_y)
                        anchor_distance = int(round(sum(baseline_readings) / len(baseline_readings))) if baseline_readings else estimated_distance
                        anchor_distance = max(0, anchor_distance)
                        trees[tree_id] = (anchor_distance, 0) if tree2_axis == "X" else (0, anchor_distance)
                        if not baseline_readings and anchor_distance > 0:
                            measurements.append((1, 2, float(anchor_distance)))
                            persist_measurements()
                        else:
                            persist_trees()
                    else:
                        trees[tree_id] = (int(estimate_x), int(estimate_y))
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


    with st.expander("Measurement", expanded=True):
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
        from_key = f"measurement_from_{measurement_revision}"
        to_key = f"measurement_to_{measurement_revision}"
        distance_key = f"measurement_distance_{measurement_revision}"
        st.session_state.setdefault(from_key, int(from_default))
        st.session_state.setdefault(to_key, int(to_default))
        st.session_state.setdefault(distance_key, max(1, int(measurement_values.get("distance", 1000))))

        def refresh_suggested_distance():
            picked_from = int(st.session_state[from_key])
            picked_to = int(st.session_state[to_key])
            existing_index = next((index for index, (a, b, _) in enumerate(measurements) if a == picked_from and b == picked_to), None)
            if existing_index is not None:
                picked_distance = max(1, int(round(measurements[existing_index][2])))
                st.session_state["selected_measurement_index"] = existing_index
            else:
                picked_distance = suggested_measurement_distance(picked_from, picked_to)
                st.session_state["selected_measurement_index"] = None
            st.session_state["highlight_pair"] = tuple(sorted((picked_from, picked_to))) if picked_from != picked_to else None
            st.session_state[distance_key] = picked_distance
            st.session_state["measurement_editor_values"] = {"from": picked_from, "to": picked_to, "distance": picked_distance}
            st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1

        left, right = st.columns(2)
        with left:
            with st.container(border=True, key="from-picker"):
                from_tree = st.selectbox("From tree", tree_ids, index=tree_ids.index(from_default), key=from_key, on_change=refresh_suggested_distance)
        with right:
            current_to_default = to_default if to_default != from_tree else next((tree for tree in tree_ids if tree != from_tree), from_tree)
            with st.container(border=True, key="to-picker"):
                to_tree = st.selectbox("To tree", tree_ids, index=tree_ids.index(current_to_default), key=to_key, on_change=refresh_suggested_distance)
        distance = st.number_input("Distance (mm)", min_value=1, step=1, key=distance_key)
        st.session_state["measurement_editor_values"] = {"from": int(from_tree), "to": int(to_tree), "distance": int(distance)}
        if selected_measurement_index is not None:
            save_col, delete_col = st.columns(2)
            with save_col:
                save_measurement = st.button("Update measurement", disabled=len(tree_ids) < 2, width="stretch", key=f"measurement_save_{measurement_revision}")
            with delete_col:
                delete_measurement = st.button("Delete measurement", width="stretch", key=f"measurement_delete_{measurement_revision}")
            cancel_measurement_edit = st.button("Cancel row edit", key=f"measurement_cancel_{measurement_revision}")
        else:
            save_measurement = st.button("Add measurement", disabled=len(tree_ids) < 2, width="stretch", key=f"measurement_save_{measurement_revision}")
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

        if selected_measurement_index is not None and 0 <= selected_measurement_index < len(measurements):
            selected_from, selected_to, _ = measurements[selected_measurement_index]
            position_revision = f"{measurement_revision}_{selected_measurement_index}_{tree_form_revision}"
            with st.expander("Selected measurement trees", expanded=False):
                with st.form(f"selected_tree_positions_{position_revision}"):
                    endpoint_columns = st.columns(2)
                    edited_positions = {}
                    for column, endpoint, tree in zip(endpoint_columns, ("From", "To"), (selected_from, selected_to)):
                        x, y = trees[tree]
                        calc_x, calc_y = coords.get(tree, (None, None))
                        with column:
                            st.markdown(f"**{endpoint} ID {tree}**")
                            init_x_col, init_y_col = st.columns(2)
                            with init_x_col:
                                edited_x = st.number_input(f"Init X · {endpoint}", min_value=0, value=int(x), step=100, disabled=tree in (1, 2), key=f"selected_init_x_{position_revision}_{endpoint}")
                            with init_y_col:
                                edited_y = st.number_input(f"Init Y · {endpoint}", min_value=0, value=int(y), step=100, disabled=tree == 1, key=f"selected_init_y_{position_revision}_{endpoint}")
                            calc_x_text = "—" if calc_x is None else f"{int(round(calc_x))} mm"
                            calc_y_text = "—" if calc_y is None else f"{int(round(calc_y))} mm"
                            calc_x_col, calc_y_col = st.columns(2)
                            with calc_x_col:
                                st.text_input(f"Calc X · {endpoint}", value=calc_x_text, disabled=True, key=f"selected_calc_x_{position_revision}_{endpoint}")
                            with calc_y_col:
                                st.text_input(f"Calc Y · {endpoint}", value=calc_y_text, disabled=True, key=f"selected_calc_y_{position_revision}_{endpoint}")
                            edited_positions[tree] = (edited_x, edited_y)
                    update_positions = st.form_submit_button("Update starting estimates", width="stretch")
                if update_positions:
                    for tree, (x, y) in edited_positions.items():
                        trees[tree] = (0 if tree in (1, 2) else int(x), 0 if tree == 1 else int(y))
                    persist_trees()
                    st.session_state["tree_form_revision"] = tree_form_revision + 1
                    st.session_state["map_revision"] = st.session_state.get("map_revision", 0) + 1
                    st.rerun()

    distance_tolerance = float(st.session_state.get("distance_tolerance", 50.0))
    estimate_tolerance = float(st.session_state.get("estimate_tolerance", 1000.0))
render_page_title_selector("Data Entry & Mapping")


def remember_map_display_preference(session_key, setting_key):
    st.session_state[setting_key] = bool(st.session_state[session_key])


estimate_toggle, target_toggle = st.columns(2)
with estimate_toggle:
    show_estimates = st.checkbox(
        "Show initial estimates",
        key="show_initial_estimates",
        on_change=remember_map_display_preference,
        args=("show_initial_estimates", "show_initial_estimates_setting"),
    )
with target_toggle:
    show_starting_targets = st.checkbox(
        "Show placement targets",
        key="show_starting_targets",
        on_change=remember_map_display_preference,
        args=("show_starting_targets", "show_starting_targets_setting"),
        help="Hide the faint grid dots when they make it hard to tap measurement lines.",
    )

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
horizontal_sign = -1 if (mirror_map_y if swap_map_axes else mirror_map_x) else 1
vertical_sign = -1 if (mirror_map_x if swap_map_axes else mirror_map_y) else 1
if coords:
    # Faint grid targets make a tap on the map a quick approximate placement
    # gesture on touch screens. Numeric estimate fields remain available too.
    extent_points = [survey_to_map(*point) for point in list(trees.values()) + list(coords.values())]
    max_x = max(1000, max(abs(point[0]) for point in extent_points) + 1000)
    max_y = max(1000, max(abs(point[1]) for point in extent_points) + 1000)
    x_padding = max(100, int(max_x * 0.03))
    y_padding = max(100, int(max_y * 0.03))
    fig.add_shape(
        type="rect",
        x0=0 if horizontal_sign > 0 else -max_x,
        x1=max_x if horizontal_sign > 0 else 0,
        y0=0 if vertical_sign > 0 else -max_y,
        y1=max_y if vertical_sign > 0 else 0,
        fillcolor="rgba(34,197,94,0.045)",
        line={"width": 0},
        layer="below",
    )
    grid_x = np.linspace(0, max_x, 25) * horizontal_sign
    grid_y = np.linspace(0, max_y, 25) * vertical_sign
    grid_display_points = [(float(x), float(y)) for x in grid_x for y in grid_y]
    tap_points = [map_to_survey(x, y) for x, y in grid_display_points]
    fig.add_trace(go.Scatter(x=[p[0] for p in grid_display_points], y=[p[1] for p in grid_display_points], customdata=tap_points, mode="markers", marker={"size": 18, "color": "rgba(100,116,139,0.20)"}, hovertemplate="Tap to set starting estimate<br>Survey X %{customdata[0]:.0f} mm<br>Survey Y %{customdata[1]:.0f} mm<extra></extra>", showlegend=False, visible=show_starting_targets, name="Starting estimate targets"))
    for measurement_index, (a, b, d) in enumerate(measurements):
        if a in coords and b in coords:
            xa, ya = survey_to_map(*coords[a])
            xb, yb = survey_to_map(*coords[b])
            midpoint_x, midpoint_y = (xa + xb) / 2, (ya + yb) / 2
            line_color = "#f97316" if st.session_state.get("highlight_pair") == tuple(sorted((a, b))) else "#9aa4b2"
            fig.add_trace(go.Scatter(x=[xa, midpoint_x, xb], y=[ya, midpoint_y, yb], mode="lines+markers", line={"color": line_color, "width": 3 if line_color == "#f97316" else 2}, marker={"size": [1, 18, 1], "color": [line_color, "rgba(100,116,139,0.015)", line_color]}, customdata=[[measurement_index, a, b]] * 3, hovertemplate=f"{a} → {b}: {d:.0f} mm<extra></extra>", showlegend=False))

    # Optional estimates are hidden by default so they cannot obscure tree taps.
    estimate_points = [survey_to_map(*trees[t]) for t in tree_ids]
    fig.add_trace(go.Scatter(x=[point[0] for point in estimate_points], y=[point[1] for point in estimate_points], customdata=[[trees[t][0], trees[t][1]] for t in tree_ids], mode="markers", name="Initial estimates", visible=show_estimates, showlegend=False, marker={"symbol": "circle-open", "size": 12, "color": "#64748b", "line": {"width": 2}}, text=[str(t) for t in tree_ids], hovertemplate="Initial estimate · Tree %{text}<br>Survey X %{customdata[0]:.0f} mm<br>Survey Y %{customdata[1]:.0f} mm<extra></extra>"))
    colors = ["#f59e0b" if t in underconstrained else ("#2563eb" if t in (1, 2) else "#15803d") for t in tree_ids]
    adjusted_points = [survey_to_map(*coords[t]) for t in tree_ids]
    fig.add_trace(go.Scatter(x=[point[0] for point in adjusted_points], y=[point[1] for point in adjusted_points], mode="markers+text", name="Adjusted positions", showlegend=False, text=[str(t) for t in tree_ids], textposition="top center", marker={"size": 15, "color": colors, "line": {"color": "white", "width": 1}}, customdata=[[degree[t], t in underconstrained, t, coords[t][0], coords[t][1]] for t in tree_ids], hovertemplate="Tree %{text}<br>Survey X %{customdata[3]:.0f} mm<br>Survey Y %{customdata[4]:.0f} mm<br>Links: %{customdata[0]}<extra></extra>"))
else:
    max_x = max_y = 1000
    x_padding = y_padding = 100
horizontal_axis_name = "Y" if swap_map_axes else "X"
vertical_axis_name = "X" if swap_map_axes else "Y"
x_range = [-x_padding, max_x] if horizontal_sign > 0 else [-max_x, x_padding]
y_range = [-y_padding, max_y] if vertical_sign > 0 else [-max_y, y_padding]
fig.update_layout(height=620, margin={"l": 10, "r": 10, "t": 20, "b": 10}, xaxis={"title": f"{horizontal_axis_name} (mm)", "range": x_range, "zeroline": True, "scaleanchor": "y", "scaleratio": 1, "constrain": "domain", "constraintoward": "left"}, yaxis={"title": f"{vertical_axis_name} (mm)", "range": y_range, "zeroline": True, "constrain": "domain", "constraintoward": "bottom"}, showlegend=False)
map_revision = st.session_state.get("map_revision", 0)
fig.update_layout(autosize=True, uirevision=f"survey-map-{swap_map_axes}-{mirror_map_x}-{mirror_map_y}")
active_picker = "from-picker" if st.session_state["measurement_next_field"] == "from" else "to-picker"
st.markdown(f"<style>.st-key-{active_picker} [data-testid='stVerticalBlockBorderWrapper'] {{ border: 3px solid #16a34a !important; border-radius: 0.75rem; }}</style>", unsafe_allow_html=True)
map_event = st.plotly_chart(fig, key=f"survey_map_{map_revision}", on_select="rerun", selection_mode="points", config={"responsive": True, "scrollZoom": False})
try:
    selected_points = map_event.selection.points
except (AttributeError, TypeError):
    selected_points = []
for point in sorted(selected_points, key=lambda selected: selected.get("curve_number") == 0):
    curve_number = point.get("curve_number")
    if curve_number == 0 and show_starting_targets:
        tap_x, tap_y = point.get("customdata", (point.get("x"), point.get("y")))
        selected_estimate_tree = int(st.session_state["tree_editor_values"]["id"])
        if selected_estimate_tree != 1:
            tap_x, tap_y = int(round(tap_x)), int(round(tap_y))
            if selected_estimate_tree == 2:
                tap_x, tap_y = (tap_x, 0) if abs(tap_x) > abs(tap_y) else (0, tap_y)
            st.session_state["tree_editor_values"] = {"id": selected_estimate_tree, "x": tap_x, "y": tap_y, "pending_map_pick": True}
            st.session_state["tree_form_revision"] = st.session_state.get("tree_form_revision", 0) + 1
            st.session_state["map_revision"] = map_revision + 1
            st.rerun()
    line_start, line_end = 1, 1 + len(measurements)
    if curve_number is not None and line_start <= curve_number < line_end:
        record_id, a, b = point.get("customdata", (None, None, None))
        record_id, a, b = int(record_id), int(a), int(b)
        st.session_state["highlight_pair"] = tuple(sorted((int(a), int(b))))
        st.session_state["selected_measurement_index"] = record_id
        st.session_state["measurement_editor_values"] = {
            "from": a,
            "to": b,
            "distance": int(round(measurements[record_id][2])),
        }
        st.session_state["measurement_next_field"] = "from"
        st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
        st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
        st.session_state["map_revision"] = map_revision + 1
        st.rerun()
    tree_curve = line_end + 1
    if curve_number == tree_curve and point.get("customdata"):
        tree = int(point["customdata"][2])
        initial_x, initial_y = trees[tree]
        if tree == 1:
            initial_x, initial_y = 0, 0
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
        suggested_distance = suggested_measurement_distance(from_selected, to_selected)
        st.session_state["measurement_editor_values"] = {
            "from": from_selected,
            "to": to_selected,
            "distance": suggested_distance,
        }
        st.session_state["measurement_next_field"] = next_field
        st.session_state["selected_measurement_index"] = None
        st.session_state["measurement_table_revision"] = st.session_state.get("measurement_table_revision", 0) + 1
        st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
        st.session_state["map_revision"] = map_revision + 1
        st.rerun()
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

    editor_df = visible_df.copy()
    editor_df.insert(0, "Select", [int(record_id) == selected_measurement for record_id in table_df["_record_id"]])
    table_revision = st.session_state.get("measurement_table_revision", 0)
    edited_table = st.data_editor(
        editor_df.style.apply(row_style, axis=1),
        width="stretch",
        hide_index=True,
        key=f"measurement_table_{table_revision}",
        disabled=["#", "Pair", "From", "To", "Adj", "Δ"],
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Select a record to edit or inspect its trees."),
            "Meas": st.column_config.NumberColumn("Meas", min_value=1, step=1, format="%d"),
        },
        num_rows="fixed",
    )
    old_selected_measurement = st.session_state.get("selected_measurement_index")
    selected_rows = [row for row, selected in enumerate(edited_table["Select"]) if bool(selected)]
    table_key = f"measurement_table_{table_revision}"
    table_widget_state = st.session_state.get(table_key, {})
    edited_cells = table_widget_state.get("edited_rows", {}) if hasattr(table_widget_state, "get") else {}
    select_was_changed = any("Select" in cells for cells in edited_cells.values())
    if len(selected_rows) > 1 and old_selected_measurement is not None:
        newly_selected_rows = [row for row in selected_rows if int(table_df.iloc[row]["_record_id"]) != old_selected_measurement]
        selected_rows = newly_selected_rows or selected_rows
    if selected_rows:
        new_selected_measurement = int(table_df.iloc[selected_rows[-1]]["_record_id"])
    elif select_was_changed:
        new_selected_measurement = None
    else:
        # Pair selection in the sidebar is another way to choose the active
        # record; an untouched table must not erase that selection.
        new_selected_measurement = old_selected_measurement
    multiple_selected = len([selected for selected in edited_table["Select"] if bool(selected)]) > 1
    selection_changed = new_selected_measurement != old_selected_measurement
    st.session_state["selected_measurement_index"] = new_selected_measurement
    if new_selected_measurement is not None:
        selected_record = measurements[new_selected_measurement]
        selected_pair = tuple(sorted(selected_record[:2]))
        editor_values_changed = st.session_state.get("measurement_editor_values") != {
            "from": selected_record[0], "to": selected_record[1], "distance": int(round(selected_record[2]))
        }
        pair_changed = st.session_state.get("highlight_pair") != selected_pair
        st.session_state["highlight_pair"] = selected_pair
        if selection_changed or editor_values_changed:
            st.session_state["measurement_editor_values"] = {
                "from": selected_record[0], "to": selected_record[1], "distance": int(round(selected_record[2]))
            }
            st.session_state["measurement_next_field"] = "from"
            st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
    else:
        pair_changed = False

    measurements_changed = False
    for row_num, edited_row in edited_table.iterrows():
        record_id = int(table_df.iloc[row_num]["_record_id"])
        if pd.isna(edited_row["Meas"]):
            continue
        edited_distance = int(round(float(edited_row["Meas"])))
        a, b, old_distance = measurements[record_id]
        if edited_distance > 0 and edited_distance != int(round(old_distance)):
            measurements[record_id] = (a, b, float(edited_distance))
            measurements_changed = True
    if measurements_changed:
        persist_measurements()
        st.session_state["measurement_table_revision"] = table_revision + 1
        st.session_state["measurement_form_revision"] = st.session_state.get("measurement_form_revision", 0) + 1
        st.session_state["map_revision"] = st.session_state.get("map_revision", 0) + 1
        if new_selected_measurement is not None:
            a, b, distance = measurements[new_selected_measurement]
            st.session_state["measurement_editor_values"] = {"from": a, "to": b, "distance": int(round(distance))}
        st.rerun()
    if selection_changed or pair_changed or multiple_selected:
        st.session_state["measurement_table_revision"] = table_revision + 1
        st.rerun()

else:
    st.caption("No tape measurements recorded yet.")
