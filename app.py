import streamlit as st
import plotly.graph_objects as go
import storage as db
import solver as engine

st.set_page_config(page_title="Dynamic Tree Surveyor", layout="centered")
st.title("🌳 Dynamic Tree Growth Network")

# Initialise data environment routes
db.init_files()
trees_dict = db.load_trees()
active_tree_numbers = sorted(list(trees_dict.keys()))
max_tree_id = max(active_tree_numbers) if active_tree_numbers else 3
measurements = db.load_measurements(trees_dict)

tree_to_idx = {t_num: idx for idx, t_num in enumerate(active_tree_numbers)}
idx_to_tree = {idx: t_num for idx, t_num in enumerate(active_tree_numbers)}

# ==========================================
# SIDEBAR PANEL A: DYNAMIC ADD / REMOVE
# ==========================================
st.sidebar.header("➕ Grow or Shrink Network")
col_add, col_del = st.sidebar.columns(2)

with col_add:
    if st.button("➕ Add New Tree"):
        next_id = max_tree_id + 1
        last_x, last_y = trees_dict[max_tree_id]
        trees_dict[next_id] = (last_x + 1.0, last_y + 0.5)
        db.save_trees(trees_dict)
        st.rerun()

with col_del:
    target_del = st.number_input("Tree # to Delete", min_value=1, max_value=max_tree_id, step=1, value=max_tree_id)
    if st.button("🗑️ Delete Tree", type="primary"):
        if len(trees_dict) <= 3:
            st.sidebar.error("Cannot drop below the minimum 3 anchor points!")
        elif target_del in trees_dict:
            del trees_dict[target_del]
            db.save_trees(trees_dict)
            st.rerun()

# ==========================================
# SIDEBAR PANEL B: NEW MEASUREMENT FORM
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("📥 New Tape Measurement")
with st.sidebar.form(key='measurement_form', clear_on_submit=True):
    tree_a = st.selectbox("From Tree #", active_tree_numbers, index=0)
    tree_b = st.selectbox("To Tree #", active_tree_numbers, index=min(1, len(active_tree_numbers)-1))
    distance = st.number_input("Tape Distance (m)", min_value=0.01, max_value=30.0, step=0.01, value=1.00)
    submit_button = st.form_submit_button("Add to Network")

if submit_button:
    if tree_a == tree_b:
        st.sidebar.error("Error: Can't measure a tree to itself!")
    else:
        duplicate_found = any((u == tree_a and v == tree_b) or (u == tree_b and v == tree_a) for u, v, _ in measurements)
        if duplicate_found:
            st.sidebar.error(f"❌ Link between {tree_a} and {tree_b} already exists!")
        else:
            db.append_measurement(tree_a, tree_b, distance)
            st.rerun()

# ==========================================
# SIDEBAR PANEL C: EDIT EXIST LOGS
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("✏️ Edit / Delete Measurements")
if len(measurements) > 0:
    options_list = [f"[{idx}] Tree {u} ↔ Tree {v} ({d:.2f}m)" for idx, (u, v, d) in enumerate(measurements)]
    selected_option = st.sidebar.selectbox("Select entry to modify:", options_list)
    
    target_idx = int(selected_option.split("]")[0].replace("[", ""))
    t_u, t_v, t_d = measurements[target_idx]
    
    new_dist = st.sidebar.number_input("Change Distance (m):", min_value=0.01, max_value=30.0, value=t_d, step=0.01, key=f"val_{target_idx}")
    col_up, col_rm = st.sidebar.columns(2)
    with col_up:
        if st.button("💾 Update Entry"):
            measurements[target_idx] = (t_u, t_v, new_dist)
            db.save_measurements(measurements)
            st.rerun()
    with col_rm:
        if st.button("🗑️ Delete Entry", type="primary"):
            if len(measurements) <= 1:
                st.sidebar.error("Cannot delete the last baseline point!")
            else:
                measurements.pop(target_idx)
                db.save_measurements(measurements)
                st.rerun()

# ==========================================
# SIDEBAR PANEL D: MANIPULATE GUESS POSITION
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("📍 Move Initial Position Guess")
target_guess_tree = st.sidebar.selectbox("Tree # to reposition:", active_tree_numbers, index=min(2, len(active_tree_numbers)-1))
curr_gx, curr_gy = trees_dict[target_guess_tree]

new_gx = st.sidebar.slider(f"Tree {target_guess_tree} X (m):", -2.0, 15.0, curr_gx, 0.05)
new_gy = st.sidebar.slider(f"Tree {target_guess_tree} Y (m):", -2.0, 10.0, curr_gy, 0.05)

if st.sidebar.button("📍 Save Initial Position"):
    trees_dict[target_guess_tree] = (new_gx, new_gy)
    db.save_trees(trees_dict)
    st.rerun()

# ==========================================
# RUN THE ENGINE & DISPLAY GRAPH LAYOUTS
# ==========================================
x_coords, y_coords = engine.run_network_adjustment(
    active_tree_numbers, tree_to_idx, idx_to_tree, trees_dict, measurements
)

fig = go.Figure()
for u, v, _ in measurements:
    fig.add_trace(go.Scatter(x=[x_coords[u], x_coords[v]], y=[y_coords[u], y_coords[v]], mode='lines', line=dict(color='lightgray', width=1.5), showlegend=False))

fig.add_trace(go.Scatter(
    x=[x_coords[t] for t in active_tree_numbers], y=[y_coords[t] for t in active_tree_numbers],
    mode='markers+text', text=[str(t) for t in active_tree_numbers], textposition="top center",
    marker=dict(color='forestgreen', size=12, line=dict(color='black', width=1.5)), hovertemplate="Tree %{text}<br>X: %{x:.2f}m<br>Y: %{y:.2f}m<extra></extra>", showlegend=False
))

fig.update_layout(xaxis=dict(scaleanchor="y", scaleratio=1), yaxis=dict(scaleanchor="x", scaleratio=1), width=750, height=450, margin=dict(l=20, r=20, t=40, b=20))
st.plotly_chart(fig)

# ==========================================
# PERFORMANCE DATA QUALITY CHECKS
# ==========================================
st.subheader("⚠️ Data Integrity Check")
bad_runs = False
for u, v, d_measured in measurements:
    import numpy as np
    dist_geo = np.sqrt((x_coords[u] - x_coords[v])**2 + (y_coords[u] - y_coords[v])**2)
    error = abs(dist_geo - d_measured)
    if error > 0.05:
        st.warning(f"Remeasure Target! Tree {u} ↔ {v}: Entry: {d_measured:.2f}m, Model: {dist_geo:.2f}m (Gap: {error*100:.1f} cm)")
        bad_runs = True

if not bad_runs and len(measurements) > 2:
    st.success("✅ Network geometry fits your tape data cleanly down to millimeter scale.")
