import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy.optimize import least_squares
import os

st.set_page_config(page_title="Interactive Tree Surveyor", layout="centered")
st.title("🌳 Touch-Interactive Tree Map")

DATA_FILE = "survey_data.csv"
GUESS_FILE = "initial_guesses.csv"
num_trees = 60

# ==========================================
# 1. BASELINE DATA PERSISTENCE
# ==========================================
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        f.write("tree_a,tree_b,distance\n")
        f.write("1,2,1.50\n")

measurements = []
with open(DATA_FILE, "r") as f:
    next(f)
    for line in f:
        if line.strip():
            u, v, d = line.strip().split(",")
            measurements.append((int(u), int(v), float(d)))

# ==========================================
# 2. SEED OR LOAD INITIAL GUESS COORDINATES
# ==========================================
if not os.path.exists(GUESS_FILE):
    # Default: Arrange them roughly across a clean 5x10m plot grid
    with open(GUESS_FILE, "w") as f:
        f.write("tree,x,y\n")
        idx = 1
        for row in range(6):
            for col in range(10):
                f.write(f"{idx},{col * 1.0},{row * 0.8}\n")
                idx += 1

guesses_dict = {}
with open(GUESS_FILE, "r") as f:
    next(f)
    for line in f:
        if line.strip():
            t_num, gx, gy = line.strip().split(",")
            guesses_dict[int(t_num)] = (float(gx), float(gy))

# Assemble flat array for solver input
initial_coordinates = np.zeros(num_trees * 2)
for t_id, (gx, gy) in guesses_dict.items():
    initial_coordinates[(t_id-1)*2] = gx
    initial_coordinates[(t_id-1)*2+1] = gy

# Hard anchor baseline starts
initial_coordinates[0] = 0.0
initial_coordinates[1] = 0.0

# ==========================================
# 3. INTERACTIVE EDIT GUESS PANEL
# ==========================================
st.sidebar.header("📍 Edit Tree Initial Guess")
target_guess_tree = st.sidebar.number_input("Tree # to reposition:", min_value=1, max_value=num_trees, step=1, value=3)
curr_gx, curr_gy = guesses_dict[target_guess_tree]

new_gx = st.sidebar.slider(f"Tree {target_guess_tree} X (m):", 0.0, 12.0, curr_gx, 0.05)
new_gy = st.sidebar.slider(f"Tree {target_guess_tree} Y (m):", 0.0, 6.0, curr_gy, 0.05)

if st.sidebar.button("💾 Save Position Guess"):
    guesses_dict[target_guess_tree] = (new_gx, new_gy)
    with open(GUESS_FILE, "w") as f:
        f.write("tree,x,y\n")
        for t_id, (x, y) in guesses_dict.items():
            f.write(f"{t_id},{x},{y}\n")
    st.rerun()

# ==========================================
# 4. FIELD MEASUREMENT FORM INPUT
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("📥 New Tape Measurement")
with st.sidebar.form(key='measurement_form', clear_on_submit=True):
    tree_a = st.number_input("From Tree #", min_value=1, max_value=num_trees, step=1, value=1)
    tree_b = st.number_input("To Tree #", min_value=1, max_value=num_trees, step=1, value=2)
    distance = st.number_input("Tape Distance (m)", min_value=0.01, max_value=30.0, step=0.01, value=1.00)
    submit_button = st.form_submit_button("Add to Network")

if submit_button:
    if tree_a != tree_b:
        with open(DATA_FILE, "a") as f:
            f.write(f"{int(tree_a)},{int(tree_b)},{float(distance)}\n")
        st.rerun()

# ==========================================
# 5. MATHEMATICAL NET ADJUSTMENT SOLVER
# ==========================================
def error_function(coords):
    residuals = []
    # Concrete anchor values
    residuals.append(coords[0] * 2000)
    residuals.append(coords[1] * 2000)
    
    for u, v, d_measured in measurements:
        idx_u, idx_v = (u - 1) * 2, (v - 1) * 2
        x_u, y_u = coords[idx_u], coords[idx_u+1]
        x_v, y_v = coords[idx_v], coords[idx_v+1]
        
        d_calculated = np.sqrt((x_u - x_v)**2 + (y_u - y_v)**2)
        residuals.append(d_calculated - d_measured)
    return np.array(residuals)

result = least_squares(error_function, initial_coordinates, method='trf')
final_coords = result.x
x_coords = final_coords[0::2]
y_coords = final_coords[1::2]

# ==========================================
# 6. TOUCH RESPONSIVE PLOTLY LAYOUT
# ==========================================
fig = go.Figure()

# Plot measurement lines
for u, v, _ in measurements:
    fig.add_trace(go.Scatter(
        x=[x_coords[u-1], x_coords[v-1]], 
        y=[y_coords[u-1], y_coords[v-1]],
        mode='lines', line=dict(color='lightgray', width=1.5), showlegend=False
    ))

# Plot interactive stakes
fig.add_trace(go.Scatter(
    x=x_coords, y=y_coords, mode='markers+text',
    text=[str(i+1) for i in range(num_trees)],
    textposition="top center",
    marker=dict(color='forestgreen', size=12, line=dict(color='black', width=1.5)),
    hovertemplate="Tree %{text}<br>X: %{x:.2f}m<br>Y: %{y:.2f}m<extra></extra>",
    showlegend=False
))

fig.update_layout(
    title=f"Interactive Plotly Map ({len(measurements)} Records Loaded)",
    xaxis=dict(range=[-1, 11], constraintoward='center', scaleratio=1),
    yaxis=dict(range=[-1, 6], scaleanchor="x", scaleratio=1),
    width=750, height=450, margin=dict(l=20, r=20, t=40, b=20),
    clickmode='event+select'
)

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 7. LEDGER LOG AUDIT TRAIL WARNINGS
# ==========================================
st.subheader("⚠️ Data Integrity Check")
bad_runs = False
for u, v, d_measured in measurements:
    idx_u, idx_v = (u - 1) * 2, (v - 1) * 2
    dist_geo = np.sqrt((x_coords[idx_u] - x_coords[idx_v])**2 + (y_coords[idx_u] - y_coords[idx_v])**2)
    error = abs(dist_geo - d_measured)
    if error > 0.08:
        st.warning(f"Remeasure Target! Tree {u} ↔ {v}: Form entry: {d_measured:.2f}m, Calculated: {dist_geo:.2f}m (Gap: {error*100:.1f} cm)")
        bad_runs = True

if not bad_runs and len(measurements) > 2:
    st.success("✅ Network structures matching tape values cleanly.")
