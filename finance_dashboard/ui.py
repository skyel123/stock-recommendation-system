"""Streamlit chart rendering."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


class UI:
    """Render metric outputs in Streamlit."""

    @classmethod
    def show(cls, data, type_of_graph: str, title: str = "Financial Metric") -> None:
        if data is None:
            st.warning("No data to display.")
            return

        if isinstance(data, dict) and type_of_graph == "line":
            for subtitle, series_data in data.items():
                cls._show_line(series_data, f"{title} — {subtitle.replace('_', ' ').title()}")
            return

        if type_of_graph == "heatmap":
            cls._show_heatmap(data, title)
        elif type_of_graph == "line":
            cls._show_line(data, title)
        else:
            st.error(f"Unsupported graph type: {type_of_graph}")

    @staticmethod
    def _show_line(data, title: str) -> None:
        if isinstance(data, pd.Series):
            frame = data.reset_index()
            frame.columns = ["Date", "Value"]
            fig = px.line(frame, x="Date", y="Value", title=title)
        else:
            frame = data.reset_index()
            fig = px.line(frame, x=frame.columns[0], y=list(data.columns), title=title)
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def _show_heatmap(data: pd.DataFrame, title: str) -> None:
        fig = go.Figure(
            data=go.Heatmap(
                z=data.values,
                x=list(data.columns),
                y=list(data.index),
                colorscale="RdBu",
                zmid=0,
                text=data.round(2).values,
                texttemplate="%{text}",
            )
        )
        fig.update_layout(title=title, xaxis_title="Stock", yaxis_title="Stock")
        st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def show_risk_groups(risk_groups: pd.DataFrame, title: str = "Portfolio Risk Groups") -> None:
        if risk_groups.empty:
            st.warning("No risk groups to display.")
            return

        fig = px.scatter(
            risk_groups,
            x="period_volatility",
            y="period_return",
            color="risk_group",
            text="ticker",
            hover_name="ticker",
            hover_data={
                "period_return": ":.2%",
                "period_volatility": ":.2%",
                "cluster": True,
                "risk_group": True,
            },
            category_orders={
                "risk_group": ["Low Risk", "Medium Risk", "High Risk"],
            },
            color_discrete_map={
                "Low Risk": "#15803d",
                "Medium Risk": "#d97706",
                "High Risk": "#b91c1c",
            },
            title=title,
        )
        fig.update_traces(textposition="top center", marker={"size": 12})
        fig.update_layout(
            xaxis_title="Volatility for selected period",
            yaxis_title="Return for selected period",
            legend_title="Risk group",
        )
        st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def show_summary_table(prices: pd.DataFrame) -> None:
        summary = prices.describe().T[["mean", "std", "min", "max"]]
        summary.columns = ["Mean", "Std Dev", "Min", "Max"]
        st.dataframe(summary, use_container_width=True)

    @staticmethod
    def show_raw_data(prices: pd.DataFrame) -> None:
        st.dataframe(prices, use_container_width=True)

    @staticmethod
    def show_overview_cards(prices: pd.DataFrame, tickers: list[str]) -> None:
        cols = st.columns(min(len(tickers), 4) or 1)
        for idx, ticker in enumerate(tickers):
            if ticker not in prices.columns:
                continue
            series = prices[ticker].dropna()
            if series.empty:
                continue
            with cols[idx % len(cols)]:
                latest = series.iloc[-1]
                first = series.iloc[0]
                change = ((latest / first) - 1) * 100
                st.metric(label=ticker, value=f"${latest:,.2f}", delta=f"{change:+.2f}%")
