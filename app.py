import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares
import os

# Set up mobile-friendly page config
st.set_page_config(page_title="Field Surveyor Network", layout="centered")
st.title("🌳 Live Tree Map (Auto-Saving)")

# Define a local file path on the Streamlit server
DATA_FILE = "survey_data.csv"

# 1. LOAD PERSISTENT DATA FROM FILE
# If the file doesn't exist yet, start with a baseline between Tree 1 and 2
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        f.write("tree_a,tree_b,distance\n")
        f.write("1,2,1.50\n")

# Read all saved measurements from the file
measurements = []
with open(DATA_FILE, "r") as f:
    next(f) # Skip header row
    for line in f:
        if line.strip():
            u, v, d = line.strip().split(",")
            measurements.append((int(u), int(v), float(d)))

st.session_state.num_trees = 60

# ==========================================
# SIDEBAR: DATA INPUT & HARD FILE WRITING
# ==========================================
st.sidebar.header("📥 New Field Measurement")
with st.sidebar.form(key='measurement_form', clear_on_submit=True):
    tree_a = st.number_input("From Tree #", min_value=1, max_value=st.session_state.num_trees, step=1, value=1)
    tree_b = st.number_input("To Tree #", min_value=1, max_value=st.session_state.num_trees, step=1, value=2)
    distance = st.number_input("Tape Distance (meters)", min_value=0.01, max_value=30.0, step=0.01, value=1.00)
    
    submit_button = st.form_submit_button("Add to Network")
    
if submit_button:
    if tree_a == tree_b:
        st.sidebar.error("Error: Can't measure a tree to itself!")
    else:
        # IMMEDIATELY WRITE TO DISK
        with open(DATA_FILE, "a") as f:
            f.write(f"{int(tree_a)},{int(tree_b)},{float(distance)}\n")
        
        # Force Streamlit to immediately reread the file and update the UI
        st.rerun()

# ==========================================
# ALGORITHM: LIVE LEAST SQUARES SOLVER
# ==========================================
num_trees = st.session_state.num_trees

np.random.seed(42)
initial_coordinates = np.zeros(num_trees * 2)
for i in range(num_trees):
    initial_coordinates[2*i]     = np.random.uniform(0, 10)
    initial_coordinates[2*i + 1] = np.random.uniform(0, 5)

initial_coordinates = 0.0
initial_coordinates = 0.0

def error_function(coords):
    residuals = []
    residuals.append(coords * 2000)
    residuals.append(coords * 2000)
    
    for u, v, d_measured in measurements:
        idx_u, idx_v = (u - 1) * 2, (v - 1) * 2
        x_u, y_u = coords[idx_u], coords[idx_u+1]
        x_v, y_v = coords[idx_v], coords[idx_v+1]
        
        d_calculated = np.sqrt((x_u - x_v)**2 + (y_u - y_v)**2)
        residuals.append(d_calculated - d_measured)
    return np.array(residuals)

with st.spinner("Calculating optimal layout..."):
    result = least_squares(error_function, initial_coordinates, method='lm')
    final_coords = result.x

x_coords = final_coords[0::2]
y_coords = final_coords[1::2]

# ==========================================
# DISPLAY: LIVE PLOTTING & WARNING SYSTEM
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
# QUALITY CONTROL: TRACK BOTCHED MEASUREMENTS
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
# DOWNLOAD BUTTONS FOR RAW RESULTS
# ==========================================
st.subheader("💾 Export Survey Files")

# 1. Download Raw Measurements List
with open(DATA_FILE, "r") as f:
    csv_data = f.read()
st.download_button(label="Download Raw CSV Data Ledger", data=csv_data, file_name="field_measurements.csv", mime="text/csv")

# 2. Download Calculated final XY Coordinates for CAD/Excel/Tablet apps
xy_output = "Tree,X_meters,Y_meters\n"
for i in range(num_trees):
    xy_output += f"{i+1},{x_coords[i]:.3f},{y_coords[i]:.3f}\n"
st.download_button(label="Download Calculated (X,Y) Tree Coordinates", data=xy_output, file_name="optimized_coordinates.csv", mime="text/csv")
