"""Tablet data-entry page with independent pair selection and no sidebar."""

import math

import pandas as pd
import streamlit as st

import field_survey_solver as solver
import storage
from page_navigation import render_page_title_selector


def _distance_suggestion(trees, measurements, coords, a, b):
    existing = next((distance for from_id, to_id, distance in measurements if from_id == a and to_id == b), None)
    if existing is not None:
        return int(round(existing))
    underconstrained = solver.underconstrained_tree_ids(trees, measurements, coords)
    position_a = coords[a] if a in coords and a not in underconstrained else trees[a]
    position_b = coords[b] if b in coords and b not in underconstrained else trees[b]
    return max(1, int(round(math.dist(position_a, position_b))))


render_page_title_selector("Data Entry")
state = storage.load_dataset_state()
dataset_pk = state["dataset_pk"]
dataset_id = state["info"]["dataset_id"]
trees = state["trees"]
measurements = state["measurements"]
tree_ids = sorted(trees)
st.caption(f"Active dataset: {dataset_id}")

if len(tree_ids) < 2:
    st.info("Add the anchor trees before entering measurements.")
    st.stop()

prefix = f"tablet_{dataset_pk}"
pending_pair = st.session_state.pop(f"{prefix}_pending_pair", None)
if pending_pair:
    st.session_state[f"{prefix}_tree_a"] = int(pending_pair[0])
    st.session_state[f"{prefix}_tree_b"] = int(pending_pair[1])

tree_a_key, tree_b_key = f"{prefix}_tree_a", f"{prefix}_tree_b"
st.session_state.setdefault(tree_a_key, tree_ids[0])
st.session_state.setdefault(tree_b_key, tree_ids[1])
if st.session_state[tree_a_key] not in tree_ids:
    st.session_state[tree_a_key] = tree_ids[0]
if st.session_state[tree_b_key] not in tree_ids or st.session_state[tree_b_key] == st.session_state[tree_a_key]:
    st.session_state[tree_b_key] = next(tree for tree in tree_ids if tree != st.session_state[tree_a_key])

last_pair_key = f"{prefix}_last_pair"
refresh_draft_key = f"{prefix}_refresh_draft_distances"
refresh_drafts = bool(st.session_state.pop(refresh_draft_key, False))
previous_pair = st.session_state.get(last_pair_key)

coords, solver_info = solver.run_network_adjustment(trees, measurements)
tree2_has_baseline = any({a, b} == {1, 2} for a, b, _ in measurements)
tree2_axis = "X" if trees.get(2, (0, 1))[0] > trees.get(2, (0, 1))[1] else "Y"

measurement_by_pair = {(a, b): int(round(distance)) for a, b, distance in measurements}
endpoint_columns = st.columns(2)
initial_changes = {}
tree_selection = {}
update_tree = None
for column, label, selector_key in zip(endpoint_columns, ("Tree A", "Tree B"), (tree_a_key, tree_b_key)):
    with column:
        with st.container(border=True):
            if label == "Tree A":
                options = tree_ids
            else:
                options = [item for item in tree_ids if item != tree_selection["Tree A"]]
                if st.session_state[selector_key] not in options:
                    st.session_state[selector_key] = options[0]
            selector_col, update_col, copy_col = st.columns([2.2, 0.8, 0.8], vertical_alignment="bottom")
            with selector_col:
                tree = int(st.selectbox(
                    label,
                    options,
                    key=selector_key,
                    format_func=lambda value: "\u00a0" * max(0, 4 - len(str(value))) + str(value),
                ))
            tree_selection[label] = tree
            x, y = trees[tree]
            calc_x, calc_y = coords.get(tree, (None, None))
            key_x, key_y = f"{prefix}_initial_x_{tree}", f"{prefix}_initial_y_{tree}"
            shown_tree_key = f"{prefix}_shown_tree_{label}"
            if st.session_state.get(shown_tree_key) != tree:
                st.session_state[key_x], st.session_state[key_y] = int(x), int(y)
                st.session_state[shown_tree_key] = tree
            with update_col:
                update_clicked = st.button(
                    "Update",
                    key=f"{prefix}_update_{label}_{tree}",
                    disabled=tree == 1 or (tree == 2 and tree2_has_baseline),
                    width="stretch",
                    help=f"Save Tree {tree}'s initial position.",
                )
            with copy_col:
                copy_clicked = st.button(
                    "Copy calc",
                    key=f"{prefix}_copy_{label}_{tree}",
                    disabled=calc_x is None or tree == 1 or (tree == 2 and tree2_has_baseline),
                    width="stretch",
                    help="Copy the calculated X/Y into the initial fields; press Update to save them.",
                )
            if copy_clicked and calc_x is not None and calc_y is not None and tree != 1:
                st.session_state[key_x] = int(round(calc_x))
                st.session_state[key_y] = int(round(calc_y))

            x_col, y_col = st.columns(2)
            with x_col:
                st.text_input("Calc X", value="—" if calc_x is None else f"{int(round(calc_x))} mm", disabled=True, key=f"{prefix}_calc_x_{label}_{tree}")
                initial_x = st.number_input(
                    "Init X", min_value=1 if tree == 2 and tree2_axis == "X" else 0,
                    value=int(x), step=100, key=key_x,
                    disabled=tree == 1 or (tree == 2 and (tree2_axis != "X" or tree2_has_baseline)),
                )
            with y_col:
                st.text_input("Calc Y", value="—" if calc_y is None else f"{int(round(calc_y))} mm", disabled=True, key=f"{prefix}_calc_y_{label}_{tree}")
                initial_y = st.number_input(
                    "Init Y", min_value=1 if tree == 2 and tree2_axis == "Y" else 0,
                    value=int(y), step=100, key=key_y,
                    disabled=tree == 1 or (tree == 2 and (tree2_axis != "Y" or tree2_has_baseline)),
                )
            initial_changes[tree] = (int(initial_x), int(initial_y))
            if update_clicked:
                update_tree = tree

tree_a, tree_b = tree_selection["Tree A"], tree_selection["Tree B"]
current_pair = (tree_a, tree_b)
if update_tree is not None:
    updated_trees = dict(trees)
    if update_tree != 2 or not tree2_has_baseline:
        updated_trees[update_tree] = initial_changes[update_tree]
    storage.save_trees(updated_trees)
    st.session_state[refresh_draft_key] = True
    st.rerun()

if previous_pair != current_pair or refresh_drafts:
    latest_trees = storage.load_trees()
    latest_measurements = storage.load_measurements(latest_trees)
    latest_coords, _ = solver.run_network_adjustment(latest_trees, latest_measurements)
    st.session_state[f"{prefix}_distance_ab"] = _distance_suggestion(latest_trees, latest_measurements, latest_coords, tree_a, tree_b)
    st.session_state[f"{prefix}_distance_ba"] = _distance_suggestion(latest_trees, latest_measurements, latest_coords, tree_b, tree_a)
    st.session_state[last_pair_key] = current_pair

st.subheader("Measurements for this pair")
direction_cols = st.columns(2)
for column, label, a, b, distance_key in (
    (direction_cols[0], "A → B", tree_a, tree_b, f"{prefix}_distance_ab"),
    (direction_cols[1], "B → A", tree_b, tree_a, f"{prefix}_distance_ba"),
):
    saved = (a, b) in measurement_by_pair
    with column:
        with st.container(border=True):
            st.markdown(f"**{label} · {a} → {b}**")
            if distance_key not in st.session_state:
                st.session_state[distance_key] = measurement_by_pair.get((a, b), _distance_suggestion(trees, measurements, coords, a, b))
            distance = int(st.number_input("Meas", min_value=1, step=1, key=distance_key))
            save_col, delete_col = st.columns(2)
            with save_col:
                save = st.button("Update measurement" if saved else "Add measurement", key=f"{prefix}_save_{a}_{b}", type="primary" if saved else "secondary", width="stretch")
            with delete_col:
                delete = st.button("Delete measurement", key=f"{prefix}_delete_{a}_{b}", disabled=not saved, width="stretch")
            if save:
                changed = [(from_id, to_id, value) for from_id, to_id, value in measurements if (from_id, to_id) != (a, b)]
                changed.append((a, b, distance))
                storage.save_measurements(changed)
                st.rerun()
            if delete:
                storage.save_measurements([(from_id, to_id, value) for from_id, to_id, value in measurements if (from_id, to_id) != (a, b)])
                st.rerun()

st.subheader("Measurement records")
distance_tolerance = float(st.session_state.get("distance_tolerance", 50.0))
estimate_tolerance = float(st.session_state.get("estimate_tolerance", 1000.0))
rows = []
for index, (a, b, measured) in enumerate(measurements, 1):
    adjusted = math.dist(coords[a], coords[b]) if a in coords and b in coords else None
    delta = int(round(adjusted - measured)) if solver_info and solver_info.get("success") and adjusted is not None else None
    rows.append({"#": index, "Pair": f"{min(a,b)} ↔ {max(a,b)}", "From": a, "To": b, "Meas": int(round(measured)), "Adj": None if adjusted is None or not solver_info or not solver_info.get("success") else int(round(adjusted)), "Δ": delta})

if rows:
    high_residuals = [row for row in rows if row["Δ"] is not None and abs(row["Δ"]) > distance_tolerance]
    moved_trees = [
        (tree, math.dist(trees[tree], coords[tree]))
        for tree in tree_ids
        if tree not in (1, 2) and tree in coords and math.dist(trees[tree], coords[tree]) > estimate_tolerance
    ]
    if high_residuals:
        st.warning(f"{len(high_residuals)} measurement(s) exceed the residual threshold of {distance_tolerance:.0f} mm.")
    for tree, shift in moved_trees:
        st.warning(f"Tree {tree} moved {shift:.0f} mm from its saved starting estimate.")

    def highlight_large_residual(row):
        delta = row["Δ"]
        if pd.notna(delta) and abs(delta) > distance_tolerance:
            return ["background-color: #fee2e2"] * len(row)
        return [""] * len(row)

    display_rows = pd.DataFrame(rows).style.apply(highlight_large_residual, axis=1)
    table_key = f"{prefix}_measurement_table"
    table_event = st.dataframe(
        display_rows,
        key=table_key,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        width="stretch",
    )
    selected_rows = table_event.selection.rows
    if selected_rows:
        selected_index = int(selected_rows[0])
        selected = measurements[selected_index]
        selected_pair = (selected[0], selected[1])
        if selected_pair != (tree_a, tree_b):
            st.session_state[f"{prefix}_pending_pair"] = selected_pair
            st.rerun()
else:
    st.caption("No tape measurements recorded yet.")
