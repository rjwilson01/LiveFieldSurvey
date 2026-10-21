import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares
import os

# Set up mobile-friendly page config
st.set_page_config(page_title="Field Surveyor Network", layout="centered")
st.title("🌳 Live Tree Map (With Edit Tools)")

# Define a local file path on the Streamlit server
DATA_FILE = "survey_data.csv"

# 1. LOAD PERSISTENT DATA FROM FILE
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        f.write("tree_a,tree_b,distance\n")
        f.write("1,2,1.50\n") # Seed baseline

measurements = []
with open(DATA_FILE, "r") as f:
    next(f) # Skip header
    for line in f:
        if line.strip():
            u, v, d = line.strip().split(",")
            measurements.append((int(u), int(v), float(d)))

st.session_state.num_trees = 60
num_trees = st.session_state.num_trees

# ==========================================
# SIDEBAR: DATA INPUT 
# ==========================================
st.sidebar.header("📥 New Field Measurement")
with st.sidebar.form(key='measurement_form', clear_on_submit=True):
    tree_a = st.number_input("From Tree #", min_value=1, max_value=num_trees, step=1, value=1)
    tree_b = st.number_input("To Tree #", min_value=1, max_value=num_trees, step=1, value=2)
    distance = st.number_input("Tape Distance (meters)", min_value=0.01, max_value=30.0, step=0.01, value=1.00)
    
    submit_button = st.form_submit_button("Add to Network")

if submit_button:
    if tree_a == tree_b:
        st.sidebar.error("Error: Can't measure a tree to itself!")
    else:
        with open(DATA_FILE, "a") as f:
            f.write(f"{int(tree_a)},{int(tree_b)},{float(distance)}\n")
        st.rerun()

# ==========================================
# SIDEBAR: EDIT / DELETE EXISTING ENTRIES
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("✏️ Edit / Delete Entries")

if len(measurements) > 0:
    # Create clean display labels for the dropdown list box
    options_list = [f"[{idx}] Tree {u} ↔ Tree {v} ({d:.2f}m)" for idx, (u, v, d) in enumerate(measurements)]
    selected_option = st.sidebar.selectbox("Select entry to modify:", options_list)
    
    # Extract the numerical entry index from the selection string
    target_idx = int(selected_option.split("]")[0].replace("[", ""))
    t_u, t_v, t_d = measurements[target_idx]
    
    # Side-by-side editing fields
    col1, col2 = st.sidebar.columns(2)
    with col1:
        new_dist = st.number_input("New Dist (m):", min_value=0.01, max_value=30.0, value=t_d, step=0.01, key=f"edit_{target_idx}")
        update_clicked = st.button("💾 Update")
    with col2:
        st.markdown("<br>", unsafe_allow_code=True) # visual spacer
        delete_clicked = st.button("🗑️ Delete Entry", type="primary")
        
    if update_clicked:
        measurements[target_idx] = (t_u, t_v, new_dist)
        # Rewrite the underlying CSV file completely with adjustments
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
# ALGORITHM: LEAST SQUARES NET ADJUSTMENT
# ==========================================
np.random.seed(42)
initial_coordinates = np.zeros(num_trees * 2)
for i in range(num_trees):
    initial_coordinates[2*i]     = np.random.uniform(0, 10)
    initial_coordinates[2*i + 1] = np.random.uniform(0, 5)

initial_coordinates[0] = 0.0
initial_coordinates[1] = 0.0

def error_function(coords):
    residuals = []
    residuals.append(coords[0] * 2000)
    residuals.append(coords[1] * 2000)
    
    for u, v, d_measured in measurements:
        idx_u, idx_v = (u - 1) * 2, (v - 1) * 2
        x_u, y_u = coords[idx_u], coords[idx_u+1]
        x_v, y_v = coords[idx_v], coords[idx_v+1]
        
        d_calculated = np.sqrt((x_u - x_v)**2 + (y_u - y_v)**2)
        residuals.append(d_calculated - d_measured)
    return np.array(residuals)

with st.spinner("Calculating optimal layout..."):
    result = least_squares(error_function, initial_coordinates, method='trf')
    final_coords = result.x

x_coords = final_coords[0::2]
y_coords = final_coords[1::2]

# ==========================================
# DISPLAY: VISUALIZATION CHART
# ==========================================
fig, ax = plt.subplots(figsize=(10, 5))
for u, v, _ in measurements:
    idx_u, idx_v = u - 1, v - 1
    ax.plot([x_coords[idx_u], x_coords[idx_v]], [y_coords[idx_u], y_coords[idx_v]], 
            color='gainsboro', linestyle='-', linewidth=1.5, zorder=1)

ax.scatter(x_coords, y_coords, color='forestgreen', s=100, edgecolors='black', zorder=2)

for i in range(num_trees):
    ax.text(x_coords[i] + 0.1, y_coords[i] + 0.1, str(i+1), fontsize=8, weight='bold', zorder=3)

ax.set_aspect('equal')
ax.grid(True, linestyle=':', alpha=0.5)
ax.set_title(f"Live Optimised Map ({len(measurements)} Saved Measurements)")
st.pyplot(fig)

# ==========================================
# QUALITY CONTROL: TRACK BOTCHED DATA
# ==========================================
st.subheader("⚠️ Data Integrity Check")
bad_measurements_found = False
for u, v, d_measured in measurements:
    idx_u, idx_v = (u - 1) * 2, (v - 1) * 2
    dist_geo = np.sqrt((x_coords[idx_u] - x_coords[idx_v])**2 + (y_coords[idx_u] - y_coords[idx_v])**2)
    error = abs(dist_geo - d_measured)
    if error > 0.08:
        st.warning(f"Remeasure Alert! Tree **{u}** to **{v}**: Tape says **{d_measured:.2f}m**, Map forced **{dist_geo:.2f}m** (Error: {error*100:.1f} cm).")
        bad_measurements_found = True

if not bad_measurements_found and len(measurements) > 5:
    st.success("✅ All data perfectly synchronized and structurally sound.")

# ==========================================
# EXPORT SURVIVAL FILES
# ==========================================
st.subheader("💾 Export Survey Files")

with open(DATA_FILE, "r") as f:
    csv_data = f.read()
st.download_button(label="Download 1. Raw Field Measurements Ledger (.csv)", data=csv_data, file_name="field_measurements.csv", mime="text/csv")

initial_xy_output = "Tree,Initial_X,Initial_Y\n"
for i in range(num_trees):
    initial_xy_output += f"{i+1},{initial_coordinates[2*i]:.3f},{initial_coordinates[2*i+1]:.3f}\n"
st.download_button(label="Download 2. Initial Guess Layout (.csv)", data=initial_xy_output, file_name="initial_guess_coordinates.csv", mime="text/csv")

xy_output = "Tree,X_meters,Y_meters\n"
for i in range(num_trees):
    xy_output += f"{i+1},{x_coords[i]:.3f},{y_coords[i]:.3f}\n"
st.download_button(label="Download 3. Final Optimized (X,Y) Tree Coordinates (.csv)", data=xy_output, file_name="optimized_coordinates.csv", mime="text/csv")
