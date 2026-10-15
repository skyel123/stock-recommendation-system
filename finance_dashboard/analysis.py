"""Portfolio return, volatility, and unsupervised risk-group analysis."""

from __future__ import annotations

import math

import pandas as pd
from finance_dashboard.models import Holding, Portfolio

from finance_dashboard.metrics import TRADING_DAYS_PER_YEAR


class PortfolioAnalysis:
    @staticmethod
    def aggregate_holdings(portfolios: list[Portfolio]) -> dict[str, Holding]:
        """Combine current holdings by ticker across portfolios."""
        combined: dict[str, Holding] = {}
        for portfolio in portfolios:
            for ticker, value in portfolio.holdings.items():
                holding = value if isinstance(value, Holding) else Holding(int(value))
                key = ticker.strip().upper()
                current = combined.get(key, Holding(0, 0.0))
                total_quantity = current.quantity + holding.quantity
                total_cost = current.quantity * current.purchase_price + holding.quantity * holding.purchase_price
                combined[key] = Holding(
                    total_quantity,
                    total_cost / total_quantity if total_quantity else 0.0,
                )
        return combined

    @classmethod
    def performance_series(cls, portfolios: list[Portfolio], prices: pd.DataFrame) -> pd.Series:
        """Historical valuation of current share quantities (no transaction history is stored)."""
        holdings = cls.aggregate_holdings(portfolios)
        tickers = [ticker for ticker in holdings if ticker in prices.columns]
        if not tickers:
            return pd.Series(dtype=float, name="Portfolio Value")
        return prices[tickers].mul({ticker: holdings[ticker].quantity for ticker in tickers}).sum(
            axis=1, min_count=1
        ).dropna().rename("Portfolio Value")

    def risk_distribution(
        self, holdings: dict[str, Holding], prices: pd.DataFrame
    ) -> tuple[pd.DataFrame, float]:
        """Allocate purchase capital by the existing volatility-ranked K-Means labels."""
        valid = {ticker: holding for ticker, holding in holdings.items() if ticker in prices.columns}
        investment = {}
        for ticker, holding in holdings.items():
            try:
                value = float(holding.quantity) * float(holding.purchase_price)
            except (TypeError, ValueError):
                value = 0.0
            investment[ticker] = value if math.isfinite(value) and value > 0 else 0.0
        classified = pd.DataFrame(columns=["ticker", "risk_group"])
        if len(valid) >= 4:
            classified = self.analyze_portfolio(prices[list(valid)])['risk_groups'][["ticker", "risk_group"]]
        assigned = dict(zip(classified.get("ticker", []), classified.get("risk_group", [])))
        rows = [
            {"risk_group": assigned.get(ticker, "Unclassified"), "investment_value": value}
            for ticker, value in investment.items()
        ]
        result = pd.DataFrame(rows)
        if result.empty:
            return pd.DataFrame(columns=["risk_group", "investment_value", "percentage"]), sum(investment.values())
        result = result.groupby("risk_group", as_index=False)["investment_value"].sum()
        result["investment_value"] = pd.to_numeric(result["investment_value"], errors="coerce").fillna(0.0)
        total_classified = result.loc[result.risk_group != "Unclassified", "investment_value"].sum()
        result["percentage"] = (
            result["investment_value"].div(total_classified).mul(100)
            if math.isfinite(float(total_classified)) and total_classified > 0
            else 0.0
        )
        result["percentage"] = result["percentage"].replace([float("inf"), -float("inf")], 0).fillna(0.0)
        return result, float(result.loc[result.risk_group == "Unclassified", "investment_value"].sum())

    def analyze_portfolio(
        self,
        prices: pd.DataFrame,
        window: int = 21,
    ) -> dict[str, pd.DataFrame | int | None]:
        """Build portfolio features and risk groups without any UI concerns."""
        if window < 2:
            raise ValueError("window must be at least 2.")

        if prices.empty or len(prices.columns) == 0:
            return {"metrics": pd.DataFrame(), "risk_groups": pd.DataFrame(), "cluster_count": None}

        daily = self.returns(prices)
        period_return = prices.apply(
            lambda series: series.dropna().iloc[-1] / series.dropna().iloc[0] - 1
            if len(series.dropna()) >= 2
            else 0.0
        )
        rolling_volatility = daily.rolling(window=window, min_periods=2).std().iloc[-1]
        metrics = pd.DataFrame(
            {
                "period_return": period_return,
                "period_volatility": rolling_volatility,
            }
        ).replace([float("inf"), -float("inf")], pd.NA).fillna(0.0)

        asset_count = len(metrics)
        if asset_count <= 3:
            return {
                "metrics": metrics.reset_index(names="ticker"),
                "risk_groups": pd.DataFrame(),
                "cluster_count": None,
            }

        cluster_count = min(2 if asset_count <= 5 else 3, asset_count)
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        features = metrics[["period_return", "period_volatility"]]
        scaled = StandardScaler().fit_transform(features)
        model = KMeans(n_clusters=cluster_count, n_init=10, random_state=42)
        labels = model.fit_predict(scaled)
        centroids = pd.DataFrame(
            features.assign(cluster=labels).groupby("cluster")["period_volatility"].mean()
        ).sort_values("period_volatility")
        risk_names = (
            ["Low Risk", "High Risk"]
            if cluster_count == 2
            else ["Low Risk", "Medium Risk", "High Risk"]
        )
        risk_by_cluster = {
            cluster: risk_names[index]
            for index, cluster in enumerate(centroids.index)
        }
        risk_groups = metrics.copy()
        risk_groups["cluster"] = labels
        risk_groups["risk_group"] = risk_groups["cluster"].map(risk_by_cluster)
        risk_groups = risk_groups.reset_index(names="ticker")
        return {
            "metrics": metrics.reset_index(names="ticker"),
            "risk_groups": risk_groups.sort_values("risk_group"),
            "cluster_count": cluster_count,
        }

    @staticmethod
    def returns(prices: pd.DataFrame, frequency: str = "daily") -> pd.DataFrame:
        if frequency == "daily":
            return prices.pct_change().dropna(how="all")
        if frequency == "monthly":
            return prices.resample("ME").last().pct_change().dropna(how="all")
        raise ValueError("frequency must be daily or monthly")

    def volatility(self, prices: pd.DataFrame, frequency: str = "annualized") -> pd.DataFrame:
        if frequency == "annualized":
            return self.returns(prices, "daily").std().to_frame("volatility") * TRADING_DAYS_PER_YEAR**0.5
        if frequency == "daily":
            return self.returns(prices, "daily").std().to_frame("volatility")
        if frequency == "monthly":
            return self.returns(prices, "monthly").std().to_frame("volatility")
        raise ValueError("frequency must be daily, monthly, or annualized")

    def risk_groups(self, prices: pd.DataFrame, method: str = "kmeans", groups: int = 3) -> pd.DataFrame:
        from sklearn.cluster import DBSCAN, KMeans
        from sklearn.preprocessing import StandardScaler

        daily = self.returns(prices)
        features = pd.DataFrame({"return": daily.mean(), "volatility": daily.std() * TRADING_DAYS_PER_YEAR**0.5})
        scaled = StandardScaler().fit_transform(features.fillna(0))
        if method.lower() == "kmeans":
            labels = KMeans(n_clusters=min(groups, len(features)), n_init=10, random_state=42).fit_predict(scaled)
        elif method.lower() == "dbscan":
            labels = DBSCAN().fit_predict(scaled)
        else:
            raise ValueError("method must be kmeans or dbscan")
        return pd.DataFrame({"ticker": features.index, "risk_group": labels})

    @staticmethod
    def recommendations(prices: pd.DataFrame, ticker: str, limit: int = 3) -> pd.DataFrame:
        if ticker not in prices.columns or len(prices.columns) < 2:
            raise ValueError("Select a stock with comparable stocks available.")
        correlation = PortfolioAnalysis().returns(prices).corr()[ticker].drop(ticker)
        return correlation.abs().sort_values(ascending=False).head(limit).to_frame("similarity")
