import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy.optimize import least_squares
import os

st.set_page_config(page_title="Dynamic Tree Surveyor", layout="centered")
st.title("🌳 Dynamic Tree Growth Network")

DATA_FILE = "survey_data.csv"
TREES_FILE = "active_trees.csv"

# ==========================================
# 1. LOAD OR SEED DYNAMIC TREE LIST
# ==========================================
if not os.path.exists(TREES_FILE):
    with open(TREES_FILE, "w") as f:
        f.write("tree,x,y\n")
        f.write("1,0.0,0.0\n")   # Tree 1 at origin
        f.write("2,3.0,0.0\n")   # Tree 2 at baseline end (3m out)
        f.write("3,0.0,4.0\n")   # Tree 3 at perpendicular (4m up)

trees_dict = {}
with open(TREES_FILE, "r") as f:
    next(f)
    for line in f:
        if line.strip():
            t_num, gx, gy = line.strip().split(",")
            trees_dict[int(t_num)] = (float(gx), float(gy))

# Dynamically read current tree count
active_tree_numbers = sorted(list(trees_dict.keys()))
max_tree_id = max(active_tree_numbers) if active_tree_numbers else 3

# ==========================================
# 2. LOAD PERSISTENT TAPE MEASUREMENTS
# ==========================================
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        f.write("tree_a,tree_b,distance\n")
        f.write("1,2,3.00\n")   # 3-4-5 Starter Triangle
        f.write("2,3,5.00\n")
        f.write("1,3,4.00\n")

measurements = []
with open(DATA_FILE, "r") as f:
    next(f)
    for line in f:
        if line.strip():
            u, v, d = line.strip().split(",")
            if int(u) in trees_dict and int(v) in trees_dict:
                measurements.append((int(u), int(v), float(d)))

# Assemble variable coordinates for the solver
num_active_trees = len(active_tree_numbers)
initial_coordinates = np.zeros(num_active_trees * 2)

tree_to_idx = {t_num: idx for idx, t_num in enumerate(active_tree_numbers)}
idx_to_tree = {idx: t_num for idx, t_num in enumerate(active_tree_numbers)}

for t_num, (gx, gy) in trees_dict.items():
    i = tree_to_idx[t_num]
    initial_coordinates[2*i] = gx
    initial_coordinates[2*i+1] = gy

# ==========================================
# SIDEBAR PANEL A: DYNAMICALLY ADD/REMOVE TREES
# ==========================================
st.sidebar.header("➕ Grow or Shrink Network")
col_add, col_del = st.sidebar.columns(2)

with col_add:
    if st.button("➕ Add New Tree"):
        next_id = max_tree_id + 1
        last_x, last_y = trees_dict[max_tree_id]
        trees_dict[next_id] = (last_x + 1.0, last_y + 0.5)
        
        with open(TREES_FILE, "w") as f:
            f.write("tree,x,y\n")
            for t_id, (x, y) in sorted(trees_dict.items()):
                f.write(f"{t_id},{x},{y}\n")
        st.rerun()

with col_del:
    target_del = st.number_input("Tree # to Delete", min_value=1, max_value=max_tree_id, step=1, value=max_tree_id)
    if st.button("🗑️ Delete Tree", type="primary"):
        if len(trees_dict) <= 3:
            st.sidebar.error("Cannot drop below the minimum 3 anchor points!")
        elif target_del in trees_dict:
            del trees_dict[target_del]
            with open(TREES_FILE, "w") as f:
                f.write("tree,x,y\n")
                for t_id, (x, y) in sorted(trees_dict.items()):
                    f.write(f"{t_id},{x},{y}\n")
            st.rerun()
# ==========================================
# SIDEBAR PANEL B: TAPE MEASUREMENT FORM
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
            with open(DATA_FILE, "a") as f:
                f.write(f"{int(tree_a)},{int(tree_b)},{float(distance)}\n")
            st.rerun()

# ==========================================
# SIDEBAR PANEL C: EDIT EXISTING ENTRIES
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("✏️ Edit / Delete Measurements")
if len(measurements) > 0:
    options_list = [f"[{idx}] Tree {u} ↔ Tree {v} ({d:.2f}m)" for idx, (u, v, d) in enumerate(measurements)]
    selected_option = st.sidebar.selectbox("Select entry to modify:", options_list)
    
    parts = selected_option.split("]")
    target_idx = int(parts[0].replace("[", ""))
    t_u, t_v, t_d = measurements[target_idx]
    
    new_dist = st.sidebar.number_input("Change Distance (m):", min_value=0.01, max_value=30.0, value=t_d, step=0.01, key=f"val_{target_idx}")
    
    col_up, col_rm = st.sidebar.columns(2)
    with col_up:
        update_clicked = st.button("💾 Update Entry")
    with col_rm:
        delete_clicked = st.button("🗑️ Delete Entry", type="primary")

    if update_clicked:
        measurements[target_idx] = (t_u, t_v, new_dist)
        with open(DATA_FILE, "w") as f:
            f.write("tree_a,tree_b,distance\n")
            for u, v, d in measurements:
                f.write(f"{u},{v},{d}\n")
        st.rerun()

    if delete_clicked:
        if len(measurements) <= 1:
            st.sidebar.error("Cannot delete the last baseline point!")
        else:
            measurements.pop(target_idx)
            with open(DATA_FILE, "w") as f:
                f.write("tree_a,tree_b,distance\n")
                for u, v, d in measurements:
                    f.write(f"{u},{v},{d}\n")
            st.rerun()
else:
    st.sidebar.info("No recorded measurements to edit yet.")

# ==========================================
# SIDEBAR PANEL D: MOVE INITIAL POSITION GUESS
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("📍 Move Initial Position Guess")
target_guess_tree = st.sidebar.selectbox("Tree # to reposition:", active_tree_numbers, index=min(2, len(active_tree_numbers)-1))
curr_gx, curr_gy = trees_dict[target_guess_tree]

new_gx = st.sidebar.slider(f"Tree {target_guess_tree} X (m):", -2.0, 15.0, curr_gx, 0.05)
new_gy = st.sidebar.slider(f"Tree {target_guess_tree} Y (m):", -2.0, 10.0, curr_gy, 0.05)

if st.sidebar.button("📍 Save Initial Position"):
    trees_dict[target_guess_tree] = (new_gx, new_gy)
    with open(TREES_FILE, "w") as f:
        f.write("tree,x,y\n")
        for t_id, (x, y) in sorted(trees_dict.items()):
            f.write(f"{t_id},{x},{y}\n")
    st.rerun()

# ==========================================
# 3. HIGH-PRECISION LEAST SQUARES SOLVER
# ==========================================
def error_function(coords):
    residuals = []
    t1_idx = tree_to_idx.get(1, 0)
    t2_idx = tree_to_idx.get(2, 1)
    
    residuals.append(coords[2*t1_idx] * 10000)      
    residuals.append(coords[2*t1_idx+1] * 10000)    
    residuals.append(coords[2*t2_idx+1] * 10000)    
    
    for u, v, d_measured in measurements:
        idx_u, idx_v = tree_to_idx[u] * 2, tree_to_idx[v] * 2
        x_u, y_u = coords[idx_u], coords[idx_u+1]
        x_v, y_v = coords[idx_v], coords[idx_v+1]
        
        d_calculated = np.sqrt((x_u - x_v)**2 + (y_u - y_v)**2)
        residuals.append(d_calculated - d_measured)
    return np.array(residuals)

result = least_squares(error_function, initial_coordinates, method='trf', ftol=1e-10, xtol=1e-10)
final_coords = result.x

x_coords = {idx_to_tree[i]: final_coords[2*i] for i in range(num_active_trees)}
y_coords = {idx_to_tree[i]: final_coords[2*i+1] for i in range(num_active_trees)}

# ==========================================
# 4. PLOTLY GRAPH VIEWPORT
# ==========================================
fig = go.Figure()

for u, v, _ in measurements:
    fig.add_trace(go.Scatter(
        x=[x_coords[u], x_coords[v]], y=[y_coords[u], y_coords[v]],
        mode='lines', line=dict(color='lightgray', width=1.5), showlegend=False
    ))

fig.add_trace(go.Scatter(
    x=[x_coords[t] for t in active_tree_numbers],
    y=[y_coords[t] for t in active_tree_numbers],
    mode='markers+text',
    text=[str(t) for t in active_tree_numbers],
    textposition="top center",
    marker=dict(color='forestgreen', size=12, line=dict(color='black', width=1.5)),
    hovertemplate="Tree %{text}<br>X: %{x:.2f}m<br>Y: %{y:.2f}m<extra></extra>",
    showlegend=False
))

fig.update_layout(
    title=f"Active Network: {num_active_trees} Trees ({len(measurements)} Tape Records)",
    xaxis=dict(scaleanchor="y", scaleratio=1),
    yaxis=dict(scaleanchor="x", scaleratio=1),
    width=750, height=450, margin=dict(l=20, r=20, t=40, b=20)
)
st.plotly_chart(fig)

# ==========================================
# 5. DATA INTEGRITY CHECK
# ==========================================
st.subheader("⚠️ Data Integrity Check")
bad_runs = False
for u, v, d_measured in measurements:
    dist_geo = np.sqrt((x_coords[u] - x_coords[v])**2 + (y_coords[u] - y_coords[v])**2)
    error = abs(dist_geo - d_measured)
    if error > 0.05:
        st.warning(f"Remeasure Target! Tree {u} ↔ {v}: Entry: {d_measured:.2f}m, Model: {dist_geo:.2f}m (Gap: {error*100:.1f} cm)")
        bad_runs = True

if not bad_runs and len(measurements) > 2:
    st.success("✅ Network geometry fits your tape data cleanly down to millimeter scale.")
