"""Tablet data-entry page with independent pair selection and no sidebar."""

import math

import pandas as pd
import streamlit as st

import solver
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


def _copy_calculated_to_initial(dataset_pk, tree, initial_x_key, initial_y_key):
    positions = st.session_state.get(f"tablet_calculated_positions_{dataset_pk}", {})
    if tree in positions:
        st.session_state[initial_x_key] = int(round(positions[tree][0]))
        st.session_state[initial_y_key] = int(round(positions[tree][1]))


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

pair = (int(st.session_state[tree_a_key]), int(st.session_state[tree_b_key]))
last_pair_key = f"{prefix}_last_pair"
if st.session_state.get(last_pair_key) != pair:
    coords, _ = solver.run_network_adjustment(trees, measurements)
    st.session_state[f"{prefix}_distance_ab"] = _distance_suggestion(trees, measurements, coords, *pair)
    st.session_state[f"{prefix}_distance_ba"] = _distance_suggestion(trees, measurements, coords, pair[1], pair[0])
    st.session_state[last_pair_key] = pair

coords, solver_info = solver.run_network_adjustment(trees, measurements)
st.session_state[f"tablet_calculated_positions_{dataset_pk}"] = coords
underconstrained = solver.underconstrained_tree_ids(trees, measurements, coords)
tree2_has_baseline = any({a, b} == {1, 2} for a, b, _ in measurements)
tree2_axis = "X" if trees.get(2, (0, 1))[0] > trees.get(2, (0, 1))[1] else "Y"

selector_a, selector_b = st.columns(2)
with selector_a:
    tree_a = int(st.selectbox("Tree A", tree_ids, key=tree_a_key))
with selector_b:
    options_b = [tree for tree in tree_ids if tree != tree_a]
    if st.session_state[tree_b_key] == tree_a:
        st.session_state[tree_b_key] = options_b[0]
    tree_b = int(st.selectbox("Tree B", options_b, key=tree_b_key))

if pair != (tree_a, tree_b):
    # A pair change initializes the two tape fields from the current network,
    # while leaving them editable on subsequent Streamlit reruns.
    st.session_state[f"{prefix}_last_pair"] = pair
    st.rerun()

measurement_by_pair = {(a, b): int(round(distance)) for a, b, distance in measurements}
endpoint_columns = st.columns(2)
initial_changes = {}
for column, label, tree in zip(endpoint_columns, ("Tree A", "Tree B"), (tree_a, tree_b)):
    x, y = trees[tree]
    calc_x, calc_y = coords.get(tree, (None, None))
    key_x, key_y = f"{prefix}_initial_x_{tree}", f"{prefix}_initial_y_{tree}"
    if st.session_state.get(f"{prefix}_shown_tree_{label}") != tree:
        st.session_state[key_x], st.session_state[key_y] = int(x), int(y)
        st.session_state[f"{prefix}_shown_tree_{label}"] = tree
    with column:
        with st.container(border=True):
            st.markdown(f"### {label} · Tree {tree}")
            calc_col, copy_col = st.columns([1.2, 1])
            with calc_col:
                st.text_input("Calculated X", value="—" if calc_x is None else f"{int(round(calc_x))} mm", disabled=True, key=f"{prefix}_calc_x_{label}")
                st.text_input("Calculated Y", value="—" if calc_y is None else f"{int(round(calc_y))} mm", disabled=True, key=f"{prefix}_calc_y_{label}")
            with copy_col:
                st.write("")
                st.write("")
                st.button(
                    "↓ Copy calculated to initial",
                    key=f"{prefix}_copy_calc_{label}",
                    disabled=calc_x is None or tree == 1 or (tree == 2 and tree2_has_baseline),
                    on_click=_copy_calculated_to_initial,
                    args=(dataset_pk, tree, key_x, key_y),
                    width="stretch",
                )
            init_x_col, init_y_col = st.columns(2)
            with init_x_col:
                initial_x = st.number_input("Initial X", min_value=1 if tree == 2 and tree2_axis == "X" else 0, value=int(x), step=100, key=key_x, disabled=tree == 1 or (tree == 2 and (tree2_axis != "X" or tree2_has_baseline)))
            with init_y_col:
                initial_y = st.number_input("Initial Y", min_value=1 if tree == 2 and tree2_axis == "Y" else 0, value=int(y), step=100, key=key_y, disabled=tree == 1 or (tree == 2 and (tree2_axis != "Y" or tree2_has_baseline)))
            initial_changes[tree] = (int(initial_x), int(initial_y))

if st.button("Update initial positions", type="primary", width="stretch", key=f"{prefix}_save_initial"):
    updated_trees = dict(trees)
    for tree, position in initial_changes.items():
        if tree != 1 and (tree != 2 or not tree2_has_baseline):
            updated_trees[tree] = position
    storage.save_trees(updated_trees)
    st.rerun()

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
