import streamlit as st
import pandas as pd

def export_raw_ledger(df_ledger):
    if df_ledger.empty:
        st.warning("No survey ledger data available to export.")
        return
        
    csv_data = df_ledger.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Download Raw CSV Data Ledger (mm)",
        data=csv_data,
        file_name="survey_data_backup_mm.csv",
        mime="text/csv",
        key="btn_export_raw"
    )

def export_calculated_coordinates(df_coords):
    if df_coords.empty:
        st.warning("No calculated coordinate data available to export.")
        return
        
    csv_data = df_coords.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Download Calculated (X,Y) Tree Coordinates (mm)",
        data=csv_data,
        file_name="calculated_tree_coordinates_mm.csv",
        mime="text/csv",
        key="btn_export_coords"
    )
