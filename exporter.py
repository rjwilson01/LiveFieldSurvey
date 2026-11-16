import streamlit as st


def export_survey(df_trees, df_measurements):
    st.download_button(
        "Download trees and measurements CSV",
        data=df_trees.to_csv(index=False).encode("utf-8-sig"),
        file_name="tree_survey.csv",
        mime="text/csv",
        key="download_tree_survey",
        help="Tree estimates, least-squares adjusted positions, link counts, and measured distances with adjusted residuals.",
    )
    st.download_button(
        "Download measurements only CSV",
        data=df_measurements.to_csv(index=False).encode("utf-8-sig"),
        file_name="tree_measurements.csv",
        mime="text/csv",
        key="download_tree_measurements",
    )
