import streamlit as st
import pandas as pd
import numpy as np

# Core sub-modules
import solver
import storage
import exporter 

st.title("🌳 Tree Planting Map & Survey Network Solver")
st.write("Real-time field-optimised Surveying Network Adjustment Tool (All coordinates/distances in mm).")

# Initialize complex session states if they aren't in app.py yet
if "tree_estimates" not in st.session_state:
    st.session_state["tree_estimates"] = {}  # Format: {tree_id: (x_guess, y_guess)}

if "survey_ledger" not in st.session_state:
    st.session_state["survey_ledger"] = []  # Format: list of dicts

# ==========================================
# SIDEBAR: INDEPENDENT DATA FORMS
# ==========================================
st.sidebar.header("🛠️ Field Operations")

# --- FORM A: ADD A NEW TREE WITH ESTIMATES ---
with st.sidebar.form("tree_estimate_form", clear_on_submit=True):
    st.subheader("📍 1. Register Tree & Set Estimate")
    new_tree_id = st.number_input("Tree ID to Add/Estimate", min_value=1, step=1, key="est_id")
    
    col_x, col_y = st.columns(2)
    with col_x:
        # Step increment set to 100mm (0.1m) for layout flexibility
        x_guess = st.number_input("Estimated X (mm)", format="%d", step=100, key="est_x")
    with col_y:
        y_guess = st.number_input("Estimated Y (mm)", format="%d", step=100, key="est_y")
        
    submit_tree = st.form_submit_button("Save Tree Estimate")

if submit_tree:
    # Save the initial coordinate guess in millimeters
    st.session_state["tree_estimates"][new_tree_id] = (x_guess, y_guess)
    st.sidebar.success(f"✅ Tree {new_tree_id} initial guess set to ({x_guess} mm, {y_guess} mm)")


# --- FORM B: ADD TAPE MEASUREMENT DISTANCES ---
with st.sidebar.form("measurement_form", clear_on_submit=True):
    st.subheader("📏 2. Log Tape Measurement")
    from_node = st.number_input("From (Tree ID)", min_value=1, step=1, key="log_from")
    to_node = st.number_input("To (Tree ID)", min_value=1, step=1, key="log_to")
    
    # Value defaulted to 1000mm (1m), minimum restriction lowered to 1mm 
    distance = st.number_input("Distance (mm)", min_value=1, value=1000, step=1, format="%d", key="log_dist")
    
    submit_meas = st.form_submit_button("Add Distance to Network")

if submit_meas:
    if from_node == to_node:
        st.sidebar.error("❌ 'From' and 'To' trees cannot be identical.")
    else:
        new_entry = {"From": from_node, "To": to_node, "Distance_mm": distance}
        st.session_state["survey_ledger"].append(new_entry)
        st.sidebar.success(f"✅ Added: Tree {from_node} ➔ Tree {to_node} = {distance} mm")

# ==========================================
# MAIN CONTENT LAYOUT
# ==========================================
tabs = st.tabs(["🗺️ Live Map & Data Tables", "📊 Current Network Calculations"])

with tabs[0]:
    col_tables_1, col_tables_2 = st.columns(2)
    
    with col_tables_1:
        st.subheader("📋 Registered Estimates / Anchors")
        if st.session_state["tree_estimates"]:
            est_df = pd.DataFrame([
                {"Tree ID": k, "Estimated X (mm)": v[0], "Estimated Y (mm)": v[1]}
                for k, v in st.session_state["tree_estimates"].items()
            ])
            st.dataframe(est_df, use_container_width=True)
        else:
            st.info("No initial coordinate guesses mapped yet.")
            
    with col_tables_2:
        st.subheader("📉 Logged Tape Measurements")
        if st.session_state["survey_ledger"]:
            ledger_df = pd.DataFrame(st.session_state["survey_ledger"])
            st.dataframe(ledger_df, use_container_width=True)
        else:
            st.info("No distance ledger entries typed yet.")

with tabs[1]:
    st.subheader("🤖 Levenberg-Marquardt Solver Status")
    
    # Simple guard block protecting the solver loop execution
    if len(st.session_state["survey_ledger"]) < 3:
        st.warning("⚠️ The network needs a minimum of 3 recorded tape links to execute calculation adjustments.")
    else:
        st.spinner("Recalculating network optimization paths...")
        # (This is where your solver.py hooks back into the UI state data arrays)
        st.success("Solver tracking engine online.")

# ==========================================
# FOOTER DATA EXPORTS
# ==========================================
st.markdown("---")
st.subheader("💾 Export Survey Files")
col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    exporter.export_raw_ledger(pd.DataFrame(st.session_state["survey_ledger"]))
    
with col_exp2:
    if st.session_state["tree_estimates"]:
        exporter.export_calculated_coordinates(pd.DataFrame([
            {"Tree": k, "X_mm": v[0], "Y_mm": v[1]} 
            for k, v in st.session_state["tree_estimates"].items()
        ]))
