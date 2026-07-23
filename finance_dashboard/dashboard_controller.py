"""Orchestrates user input, data loading, metrics, and display."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from finance_dashboard.finance_data import FinanceData
from finance_dashboard.metric_registry import MetricDefinition, MetricRegistry
from finance_dashboard.metrics import Metrics
from finance_dashboard.ui import UI


DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL"]
SESSION_PRICES = "cached_prices"
SESSION_TICKERS = "cached_tickers"
SESSION_SOURCE = "data_source"
SESSION_USER_INPUT = "current_user_input"


def _metric_url_path(metric_name: str) -> str:
    return metric_name.lower().replace(" ", "_")


@dataclass
class UserInput:
    tickers: list[str]
    start_date: date
    end_date: date
    window: int
    comparison_mode: str
    enabled_optional_metrics: list[str]
    volatility_ticker: str | None = None
    correlation_ticker_a: str | None = None
    correlation_ticker_b: str | None = None
    sort_ascending: bool = True
    refresh_data: bool = False


class DashboardController:
    """Main controller for the finance dashboard."""

    def __init__(self) -> None:
        self.finance_data = FinanceData()
        self.metrics = Metrics()
        self.ui = UI()
        self.registry = MetricRegistry()
        self._ensure_session_state()

    def _ensure_session_state(self) -> None:
        if SESSION_PRICES not in st.session_state:
            st.session_state[SESSION_PRICES] = pd.DataFrame()
        if SESSION_TICKERS not in st.session_state:
            st.session_state[SESSION_TICKERS] = []
        if SESSION_SOURCE not in st.session_state:
            st.session_state[SESSION_SOURCE] = "none"

    def accept_user_input(self, default_tickers: list[str] | None = None) -> UserInput:
        if "tickers_list" not in st.session_state:
            st.session_state["tickers_list"] = default_tickers or DEFAULT_TICKERS

        with st.expander("⚙️ Dashboard Settings & Data Upload", expanded=True):
            col1, col2, col3 = st.columns([1.2, 1.0, 1.0])
            
            with col1:
                st.subheader("Tickers & Features")
                ticker_text = st.text_area(
                    "Stock tickers (comma-separated)",
                    value=", ".join(st.session_state["tickers_list"]),
                    help="Add any Yahoo Finance ticker symbols, e.g. AAPL, TSLA, NVDA",
                    height=100
                )
                tickers = [t.strip().upper() for t in ticker_text.split(",") if t.strip()]
                st.session_state["tickers_list"] = tickers

                optional = self.registry.optional_metrics()
                enabled_optional = st.multiselect(
                    "Enable optional metrics",
                    options=optional,
                    default=st.session_state.get("enabled_optional_metrics", []),
                    help="Selected metrics appear as additional pages in the sidebar.",
                )
                st.session_state["enabled_optional_metrics"] = enabled_optional

            with col2:
                st.subheader("Timeframe")
                default_end = date.today()
                default_start = default_end - timedelta(days=30)
                start_date = st.date_input("Start date", value=default_start)
                end_date = st.date_input("End date", value=default_end)
                window = st.slider("Rolling window (days)", min_value=5, max_value=90, value=21)

            with col3:
                st.subheader("Preferences & Actions")
                comparison_mode = st.radio(
                    "Comparison display",
                    options=["normalized", "raw", "both"],
                    format_func=lambda value: {
                        "normalized": "Normalized (base 100)",
                        "raw": "Raw prices",
                        "both": "Both charts",
                    }[value],
                )
                sort_ascending = (
                    st.radio("Sort raw data by date", ["Oldest first", "Newest first"])
                    == "Oldest first"
                )
                refresh_data = st.button("Refresh market data", use_container_width=True)

        return UserInput(
            tickers=st.session_state["tickers_list"],
            start_date=start_date,
            end_date=end_date,
            window=window,
            comparison_mode=comparison_mode,
            enabled_optional_metrics=enabled_optional,
            sort_ascending=sort_ascending,
            refresh_data=refresh_data,
        )

    def download_data(
        self,
        list_of_stocks: list[str],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        prices = self.finance_data.download(
            list_of_stocks,
            start=start,
            end=end,
        )
        st.session_state[SESSION_PRICES] = prices.copy()
        st.session_state[SESSION_TICKERS] = list(prices.columns)
        st.session_state[SESSION_SOURCE] = "yfinance"
        return prices

    def _resolve_prices(self, user_input: UserInput) -> pd.DataFrame:
        needs_download = (
            user_input.refresh_data
            or st.session_state[SESSION_PRICES].empty
            or set(user_input.tickers) != set(st.session_state[SESSION_TICKERS])
        )

        if needs_download:
            if not user_input.tickers:
                raise ValueError("Enter at least one ticker.")
            prices = self.download_data(
                user_input.tickers,
                start=user_input.start_date,
                end=user_input.end_date,
            )
        else:
            prices = st.session_state[SESSION_PRICES].copy()

        successful_tickers = list(prices.columns)
        if successful_tickers and successful_tickers != user_input.tickers:
            st.session_state["tickers_list"] = successful_tickers
            user_input.tickers = successful_tickers

        return Metrics.filter_by_date_range(
            prices,
            pd.Timestamp(user_input.start_date),
            pd.Timestamp(user_input.end_date),
        )

    def _metric_specific_inputs(
        self,
        definition: MetricDefinition,
        tickers: list[str],
    ) -> dict[str, str | None]:
        params: dict[str, str | None] = {
            "ticker_a": None,
            "ticker_b": None,
        }

        if definition.requires_single_ticker and tickers:
            params["ticker_a"] = st.sidebar.selectbox(
                f"Stock for {definition.name}",
                tickers,
                key=f"ticker_a_{definition.name}",
            )

        if definition.requires_two_tickers and len(tickers) >= 2:
            params["ticker_a"] = st.sidebar.selectbox(
                "Stock A",
                tickers,
                key=f"ticker_a_{definition.name}",
            )
            remaining = [t for t in tickers if t != params["ticker_a"]]
            params["ticker_b"] = st.sidebar.selectbox(
                "Stock B",
                remaining,
                key=f"ticker_b_{definition.name}",
            )

        return params

    def _render_metric_page(self, definition: MetricDefinition, user_input: UserInput) -> None:
        st.title(definition.name)
        st.caption(definition.description)

        tickers = user_input.tickers or list(st.session_state[SESSION_TICKERS])
        if len(tickers) < definition.min_tickers:
            st.warning(f"This metric requires at least {definition.min_tickers} tickers.")
            return

        params = self._metric_specific_inputs(definition, tickers)

        try:
            prices = self._resolve_prices(user_input)
        except ValueError as exc:
            st.error(str(exc))
            return

        if prices.empty:
            st.warning("No data in the selected date range.")
            return

        try:
            result = self.metrics.calculate(
                metric_type=definition.name,
                prices=prices,
                window=user_input.window,
                ticker_a=params["ticker_a"],
                ticker_b=params["ticker_b"],
                comparison_mode=user_input.comparison_mode,
            )
        except ValueError as exc:
            st.error(str(exc))
            return

        graph_type = self.registry.graph_type(definition.name)
        self.ui.show(result, graph_type, title=definition.name)

        with st.expander("Summary statistics"):
            self.ui.show_summary_table(prices)

        with st.expander("Raw price data"):
            sorted_prices = prices.sort_index(ascending=user_input.sort_ascending)
            self.ui.show_raw_data(sorted_prices)

    def _render_overview_page(self, user_input: UserInput) -> None:
        st.title("Overview")
        st.caption("Snapshot of loaded tickers and quick navigation to detailed metrics.")

        tickers = user_input.tickers or list(st.session_state[SESSION_TICKERS])
        if not tickers:
            st.info("Enter tickers in the sidebar to begin.")
            return

        try:
            prices = self._resolve_prices(user_input)
        except ValueError as exc:
            st.error(str(exc))
            return

        if prices.empty:
            st.warning("No data in the selected date range.")
            return

        source = st.session_state[SESSION_SOURCE]
        st.write(f"**Data source:** {source} · **Tickers:** {', '.join(prices.columns)}")

        self.ui.show_overview_cards(prices, list(prices.columns))

        st.subheader("Latest prices")
        latest = prices.tail(10).sort_index(ascending=False)
        self.ui.show_raw_data(latest)

        active = self.registry.active_metrics(user_input.enabled_optional_metrics)
        st.subheader("Available metrics")
        for metric in active:
            st.markdown(f"- **{metric.name}** — {metric.description}")

    def _run_overview_page(self) -> None:
        user_input = st.session_state[SESSION_USER_INPUT]
        self._render_overview_page(user_input)

    def _make_metric_page_runner(self, metric_name: str):
        def run_metric_page() -> None:
            user_input = st.session_state[SESSION_USER_INPUT]
            definition = self.registry.get_definition(metric_name)
            self._render_metric_page(definition, user_input)

        slug = _metric_url_path(metric_name)
        run_metric_page.__name__ = f"metric_{slug}"
        run_metric_page.__qualname__ = run_metric_page.__name__
        return run_metric_page

    def display_metrics(self) -> None:
        user_input = self.accept_user_input()
        st.session_state[SESSION_USER_INPUT] = user_input
        active_metrics = self.registry.active_metrics(user_input.enabled_optional_metrics)

        pages = [
            st.Page(
                self._run_overview_page,
                title="Overview",
                icon="📊",
                default=True,
            )
        ]

        icons = {
            "Rolling Volatility": "📉",
            "Stock Comparison": "⚖️",
            "Correlation Matrix": "🔥",
            "Rolling Correlation": "🔗",
            "Sharpe Ratio": "📐",
            "Cumulative Returns": "📈",
        }

        for definition in active_metrics:
            pages.append(
                st.Page(
                    self._make_metric_page_runner(definition.name),
                    title=definition.name,
                    icon=icons.get(definition.name, "📋"),
                    url_path=_metric_url_path(definition.name),
                )
            )

        navigation = st.navigation(pages, position="sidebar")
        navigation.run()
