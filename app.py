"""Streamlit entry point for the Finance Dashboard."""

import streamlit as st

from finance_dashboard.dashboard_controller import DashboardController

st.set_page_config(
    page_title="Finance Dashboard",
    page_icon="📈",
    layout="wide",
)

controller = DashboardController()
controller.display_metrics()
