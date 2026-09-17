"""Portfolio return, volatility, and unsupervised risk-group analysis."""

from __future__ import annotations

import pandas as pd

from finance_dashboard.metrics import TRADING_DAYS_PER_YEAR


class PortfolioAnalysis:
    def analyze_portfolio(self, prices: pd.DataFrame) -> dict[str, pd.DataFrame | int | None]:
        """Build portfolio features and risk groups without any UI concerns."""
        if prices.empty or len(prices.columns) == 0:
            return {"metrics": pd.DataFrame(), "risk_groups": pd.DataFrame(), "cluster_count": None}

        daily = self.returns(prices)
        metrics = pd.DataFrame(
            {
                "annual_return": daily.mean() * TRADING_DAYS_PER_YEAR,
                "annual_volatility": daily.std() * TRADING_DAYS_PER_YEAR**0.5,
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

        features = metrics[["annual_return", "annual_volatility"]]
        scaled = StandardScaler().fit_transform(features)
        model = KMeans(n_clusters=cluster_count, n_init=10, random_state=42)
        labels = model.fit_predict(scaled)
        centroids = pd.DataFrame(
            features.assign(cluster=labels).groupby("cluster")["annual_volatility"].mean()
        ).sort_values("annual_volatility")
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
