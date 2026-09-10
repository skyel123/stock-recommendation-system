"""Orchestrates user input, data loading, metrics, and display."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from finance_dashboard.finance_data import FinanceData
from finance_dashboard.analysis import PortfolioAnalysis
from finance_dashboard.auth import AuthService
from finance_dashboard.metric_registry import MetricDefinition, MetricRegistry
from finance_dashboard.metrics import Metrics
from finance_dashboard.portfolio_repository import InMemoryPortfolioRepository, InMemoryUserRepository, MongoRepositories
from finance_dashboard.portfolio_service import PortfolioService
from finance_dashboard.ui import UI


DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL"]
SESSION_PRICES = "cached_prices"
SESSION_TICKERS = "cached_tickers"
SESSION_SOURCE = "data_source"
SESSION_USER_INPUT = "current_user_input"
SESSION_USER = "current_user"
LOCAL_USER_REPOSITORY = InMemoryUserRepository()
LOCAL_PORTFOLIO_REPOSITORY = InMemoryPortfolioRepository()


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
        try:
            repositories = MongoRepositories()
        except Exception:
            repositories = None
        self.auth = AuthService(repositories or LOCAL_USER_REPOSITORY)
        self.portfolios = PortfolioService(repositories or LOCAL_PORTFOLIO_REPOSITORY)
        self.analysis = PortfolioAnalysis()
        self._ensure_session_state()

    def _authenticate(self) -> bool:
        if SESSION_USER in st.session_state:
            st.write(f"Signed in as **{st.session_state[SESSION_USER].email}**")
            if st.button("Log out", use_container_width=False):
                del st.session_state[SESSION_USER]
                st.rerun()
            return True
        st.title("Welcome to Finance Dashboard")
        login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
        with login_tab:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Log in", type="primary", key="login_submit"):
                self._submit_auth("login", email, password)
        with signup_tab:
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            if st.button("Sign up", type="primary", key="signup_submit"):
                self._submit_auth("signup", email, password)
        return False

    def _submit_auth(self, action: str, email: str, password: str) -> None:
        try:
            user = self.auth.login(email, password) if action == "login" else self.auth.signup(email, password)
            st.session_state[SESSION_USER] = user
            st.rerun()
        except Exception as exc:
            st.error(f"Unable to {action}: {exc}")

    def _render_portfolio_manager(self, user_id: str) -> None:
        st.title("Portfolio Management")
        st.caption("Create portfolios and manage their holdings.")
        st.markdown("<style>button[kind='primary'] { background: #15803d; border-color: #15803d; }</style>", unsafe_allow_html=True)
        portfolios = self.portfolios.list_portfolios(user_id)
        if st.button("+ Create new portfolio", type="primary", key="create_portfolio_button"):
            st.session_state["creating_portfolio"] = True
        if st.session_state.get("creating_portfolio"):
            with st.form("create_portfolio_form"):
                name = st.text_input("Portfolio name")
                submitted = st.form_submit_button("Save portfolio", type="primary")
            if submitted:
                try:
                    self.portfolios.create_portfolio(user_id, name)
                    st.session_state["creating_portfolio"] = False
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if not portfolios:
            st.info("You have no saved portfolios yet.")
            return
        names = [portfolio.name for portfolio in portfolios]
        selected_name = st.selectbox("Portfolio", names)
        portfolio = portfolios[names.index(selected_name)]
        for ticker, quantity in portfolio.holdings.items():
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(ticker)
            new_quantity = col2.number_input("Quantity", min_value=0.01, value=float(quantity), key=f"quantity_{portfolio.id}_{ticker}")
            if col3.button("Remove", key=f"remove_{portfolio.id}_{ticker}"):
                self.portfolios.remove_holding(portfolio.id, ticker)
                st.rerun()
            if new_quantity != quantity:
                self.portfolios.edit_holding(portfolio.id, ticker, new_quantity)
        ticker = st.text_input("Add stock ticker", key=f"add_ticker_{portfolio.id}")
        quantity = st.number_input("Shares", min_value=0.01, value=1.0, key=f"add_quantity_{portfolio.id}")
        if st.button("Add stock"):
            try:
                self.portfolios.add_holding(portfolio.id, ticker, quantity)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if portfolio.holdings and st.button("Analyze this portfolio"):
            st.session_state["tickers_list"] = list(portfolio.holdings)

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

        with st.expander("Risk groups and recommendations"):
            method = st.selectbox("Clustering method", ["kmeans", "dbscan"])
            frequency = st.selectbox("Volatility frequency", ["annualized", "daily", "monthly"])
            st.dataframe(self.analysis.volatility(prices, frequency), use_container_width=True)
            if len(prices.columns) >= 2:
                st.dataframe(self.analysis.risk_groups(prices, method=method), use_container_width=True)
                target = st.selectbox("Find similar stocks", list(prices.columns))
                st.dataframe(self.analysis.recommendations(prices, target), use_container_width=True)

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

    def _run_portfolio_page(self) -> None:
        user = st.session_state[SESSION_USER]
        self._render_portfolio_manager(user.id)

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
        if not self._authenticate():
            return
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
        pages.append(
            st.Page(
                self._run_portfolio_page,
                title="Portfolio Management",
                icon="💼",
                url_path="portfolio-management",
            )
        )

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
