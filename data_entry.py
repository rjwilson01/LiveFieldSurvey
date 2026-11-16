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
tree_ids = sorted(trees)

def persist_trees():
    storage.save_trees(trees)

def persist_measurements():
    storage.save_measurements(measurements)


with st.sidebar:
    st.header("Trees")
    with st.form("add_tree"):
        new_id = st.number_input("New tree ID", min_value=1, step=1, value=max(tree_ids, default=0) + 1)
        x_guess = st.number_input("Initial X (mm)", value=0, step=500)
        y_guess = st.number_input("Initial Y (mm)", value=0, step=500)
        add_tree = st.form_submit_button("Add tree")
    if add_tree:
        if int(new_id) in trees:
            st.error(f"Tree {int(new_id)} already exists.")
        else:
            trees[int(new_id)] = (float(x_guess), float(y_guess))
            persist_trees()
            st.rerun()

    if tree_ids:
        deletable = [t for t in tree_ids if t not in (1, 2)]
        if deletable:
            with st.form("delete_tree"):
                delete_id = st.selectbox("Tree to delete", deletable)
                delete_tree = st.form_submit_button("Delete tree")
            if delete_tree:
                del trees[int(delete_id)]
                measurements = [(a, b, d) for a, b, d in measurements if int(delete_id) not in (a, b)]
                persist_trees()
                persist_measurements()
                st.rerun()
        st.caption("Trees 1 and 2 define the origin and positive Y axis and are kept as anchors.")

    st.divider()
    st.header("Initial estimates")
    if tree_ids:
        edit_id = st.selectbox("Tree to position", tree_ids, key="edit_estimate_tree")
        gx, gy = trees[edit_id]
        with st.form("edit_estimate"):
            edit_x = st.number_input("Estimated X (mm)", value=float(gx), step=100.0, key=f"estimate_x_{edit_id}")
            edit_y = st.number_input("Estimated Y (mm)", value=float(gy), step=100.0, key=f"estimate_y_{edit_id}")
            save_estimate = st.form_submit_button("Save estimate")
        if save_estimate:
            trees[edit_id] = (float(edit_x), float(edit_y))
            persist_trees()
            st.rerun()

    st.divider()
    st.header("Tape measurement")
    if len(tree_ids) >= 2:
        with st.form("measurement_form", clear_on_submit=True):
            left, right = st.columns(2)
            with left:
                from_tree = st.selectbox("From tree", tree_ids)
            with right:
                to_tree = st.selectbox("To tree", tree_ids, index=1)
            distance = st.number_input("Distance (mm)", min_value=1, value=1000, step=10)
            add_measurement = st.form_submit_button("Add measurement")
        if add_measurement:
            if from_tree == to_tree:
                st.error("Choose two different trees.")
            else:
                measurements.append((int(from_tree), int(to_tree), float(distance)))
                persist_measurements()
                st.rerun()

    st.divider()
    st.header("Deviation alerts")
    distance_tolerance = st.number_input("Moderate distance residual (mm)", min_value=0.0, value=50.0, step=10.0)
    estimate_tolerance = st.number_input("Large shift from estimate (mm)", min_value=0.0, value=1000.0, step=100.0)


st.subheader("Live map")
coords, solver_info = solver.run_network_adjustment(trees, measurements)
if not solver_info or not solver_info["baseline_measured"]:
    st.info("Measure between Tree 1 and Tree 2 to set the scale and lock Tree 2 onto the positive Y axis. Tree 1 is fixed at (0, 0).")

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
    min_x = min(p[0] for p in extent_points) - 1000
    max_x = max(p[0] for p in extent_points) + 1000
    min_y = min(p[1] for p in extent_points) - 1000
    max_y = max(p[1] for p in extent_points) + 1000
    grid_x = np.linspace(min_x, max_x, 31)
    grid_y = np.linspace(min_y, max_y, 31)
    tap_points = [(float(x), float(y)) for x in grid_x for y in grid_y]
    fig.add_trace(go.Scatter(x=[p[0] for p in tap_points], y=[p[1] for p in tap_points], customdata=tap_points, mode="markers", marker={"size": 16, "color": "rgba(100,116,139,0.025)"}, hoverinfo="skip", showlegend=False, name="Tap to place estimate"))
    for a, b, d in measurements:
        if a in coords and b in coords:
            xa, ya = coords[a]
            xb, yb = coords[b]
            fig.add_trace(go.Scatter(x=[xa, xb], y=[ya, yb], mode="lines", line={"color": "#9aa4b2", "width": 2}, hovertemplate=f"{a} ↔ {b}: {d:.0f} mm<extra></extra>", showlegend=False))

    # Keep original estimates visible as small open circles; calculated positions
    # are the filled markers and are the ones connected by tape measurements.
    fig.add_trace(go.Scatter(x=[trees[t][0] for t in tree_ids], y=[trees[t][1] for t in tree_ids], mode="markers", name="Initial estimates", marker={"symbol": "circle-open", "size": 14, "color": "#64748b", "line": {"width": 2}}, text=[str(t) for t in tree_ids], hovertemplate="Initial estimate · Tree %{text}<br>X %{x:.0f} mm<br>Y %{y:.0f} mm<extra></extra>"))
    colors = ["#f59e0b" if t in underconstrained else ("#2563eb" if t in (1, 2) else "#15803d") for t in tree_ids]
    fig.add_trace(go.Scatter(x=[coords[t][0] for t in tree_ids], y=[coords[t][1] for t in tree_ids], mode="markers+text", name="Adjusted positions", text=[str(t) for t in tree_ids], textposition="top center", marker={"size": 15, "color": colors, "line": {"color": "white", "width": 1}}, customdata=[[degree[t], t in underconstrained] for t in tree_ids], hovertemplate="Tree %{text}<br>X %{x:.0f} mm<br>Y %{y:.0f} mm<br>Links: %{customdata[0]}<extra></extra>"))
fig.update_layout(height=620, margin={"l": 10, "r": 10, "t": 20, "b": 10}, xaxis={"title": "X (mm)", "zeroline": True, "scaleanchor": "y", "scaleratio": 1}, yaxis={"title": "Y (mm)", "zeroline": True}, legend={"orientation": "h", "y": 1.02})
map_revision = st.session_state.get("map_revision", 0)
map_event = st.plotly_chart(fig, use_container_width=True, key=f"survey_map_{map_revision}", on_select="rerun", selection_mode="points")
try:
    selected_points = map_event.selection.points
except (AttributeError, TypeError):
    selected_points = []
for point in selected_points:
    if point.get("curve_number") == 0 and tree_ids:
        tap_x, tap_y = point.get("customdata", (point.get("x"), point.get("y")))
        trees[int(st.session_state.get("edit_estimate_tree", tree_ids[0]))] = (float(tap_x), float(tap_y))
        persist_trees()
        st.session_state["map_revision"] = map_revision + 1
        st.rerun()
st.caption("Gray lines show recorded measurements. Green trees are connected and have at least three measured links; amber trees need more links or a connection to the anchored network. Open circles show saved starting estimates.")
st.caption("Tap a point on the map to place the tree selected under Initial estimates in the sidebar; the grid gives a rough position that you can fine-tune numerically.")

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
        residual_rows.append({"From": a, "To": b, "Measured (mm)": d, "Adjusted (mm)": predicted, "Residual (mm)": residual})
        if abs(residual) > distance_tolerance:
            st.warning(f"Moderate distance deviation: Tree {a} ↔ {b} differs by {residual:+.1f} mm. Check the measurement or adjust its value below.")
    for t, shift in moved:
        st.warning(f"Tree {t} moved {shift:.0f} mm from its saved initial estimate. Review the estimate or add/check measurements.")
    if residual_rows:
        st.dataframe(pd.DataFrame(residual_rows), use_container_width=True, hide_index=True)
elif measurements:
    st.warning(solver_info["message"] if solver_info else "The network needs Trees 1 and 2 to calculate positions.")

st.subheader("Edit or remove a measurement")
if measurements:
    options = [f"{i + 1}. Tree {a} ↔ Tree {b} — {d:g} mm" for i, (a, b, d) in enumerate(measurements)]
    selected = st.selectbox("Measurement", range(len(options)), format_func=lambda i: options[i])
    a, b, old_distance = measurements[selected]
    with st.form("edit_measurement"):
        edited_distance = st.number_input("Measured distance (mm)", min_value=1.0, value=float(old_distance), step=10.0)
        col_save, col_remove = st.columns(2)
        with col_save:
            update_measurement = st.form_submit_button("Save distance")
        with col_remove:
            remove_measurement = st.form_submit_button("Delete measurement")
    if update_measurement:
        measurements[selected] = (a, b, float(edited_distance))
        persist_measurements()
        st.rerun()
    if remove_measurement:
        measurements.pop(selected)
        persist_measurements()
        st.rerun()
else:
    st.caption("No tape measurements recorded yet.")

st.subheader("Export survey")
exporter.export_survey(pd.DataFrame([{"Tree": t, "Initial_X_mm": trees[t][0], "Initial_Y_mm": trees[t][1], "Adjusted_X_mm": coords.get(t, (float("nan"), float("nan")))[0], "Adjusted_Y_mm": coords.get(t, (float("nan"), float("nan")))[1], "Links": degree[t], "Needs_more_measurements": t in underconstrained} for t in tree_ids]), pd.DataFrame(residual_rows if solver_info and solver_info["success"] else [{"From": a, "To": b, "Measured_mm": d} for a, b, d in measurements]))
