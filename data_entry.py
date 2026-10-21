import streamlit as st
import pandas as pd

# ==========================================
# RUNTIME MEMORY STATE TRACKER
# ==========================================
# Initialize tracking memory if it's the very first boot cycle
if "last_entered_distance" not in st.session_state:
    st.session_state["last_entered_distance"] = 1000  # Starts at your 1m default

# Define your standard recurring field dimensions here (in mm)
VALID_PRESETS = [1000, 1500, 2000, 2500, 3000]

# --- FORM B: ADD TAPE MEASUREMENT DISTANCES ---
with st.sidebar.form("measurement_form", clear_on_submit=False):
    st.subheader("📏 2. Log Tape Measurement")
    from_node = st.number_input("From (Tree ID)", min_value=1, step=1, key="log_from")
    to_node = st.number_input("To (Tree ID)", min_value=1, step=1, key="log_to")
    
    # Generate the select list. If the last entered distance is a custom number, 
    # we dynamically add it to the view so the dropdown highlights it smoothly.
    dropdown_options = list(VALID_PRESETS)
    if st.session_state["last_entered_distance"] not in dropdown_options:
        dropdown_options.append(st.session_state["last_entered_distance"])
    dropdown_options.sort()
    dropdown_options.append("Custom Value...")

    # Determine what index to highlight by default based on what was typed last
    try:
        default_dropdown_idx = dropdown_options.index(st.session_state["last_entered_distance"])
    except ValueError:
        default_dropdown_idx = 0

    distance_selection = st.selectbox(
        "Select Distance Preset (mm)",
        options=dropdown_options,
        index=default_dropdown_idx,
        key="dist_preset"
    )

    # If they select "Custom Value...", reveal an overlay number entry field
    if distance_selection == "Custom Value...":
        final_distance = st.number_input(
            "Enter Custom Distance (mm)",
            min_value=1,
            value=int(st.session_state["last_entered_distance"]),
            step=1,
            format="%d",
            key="custom_dist_val"
        )
    else:
        final_distance = int(distance_selection)
    
    submit_meas = st.form_submit_button("Add Distance to Network")

if submit_meas:
    if from_node == to_node:
        st.sidebar.error("❌ 'From' and 'To' trees cannot be identical.")
    else:
        # Save the current valid entry to state memory so it stays for the next run
        st.session_state["last_entered_distance"] = final_distance
        
        new_entry = {
            "From": from_node, 
            "To": to_node, 
            "Distance_mm": final_distance
        }
        st.session_state["survey_ledger"].append(new_entry)
        
        st.sidebar.success(f"✅ Added: Tree {from_node} ➔ Tree {to_node} = {final_distance} mm")
        st.rerun()  # Forces a clean redraw to instantly push the updated default down
