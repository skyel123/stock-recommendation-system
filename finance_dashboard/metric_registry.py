"""Registry for built-in and user-added dashboard metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    graph_type: str
    description: str = ""
    min_tickers: int = 1
    requires_single_ticker: bool = False
    requires_two_tickers: bool = False
    supports_comparison_mode: bool = False
    enabled_by_default: bool = True


BUILTIN_METRICS: dict[str, MetricDefinition] = {
    "Rolling Volatility": MetricDefinition(
        name="Rolling Volatility",
        graph_type="line",
        description="Annualized rolling standard deviation of daily returns.",
        requires_single_ticker=True,
    ),
    "Stock Comparison": MetricDefinition(
        name="Stock Comparison",
        graph_type="line",
        description="Compare stocks using normalized or raw price series.",
        min_tickers=1,
        supports_comparison_mode=True,
    ),
    "Correlation Matrix": MetricDefinition(
        name="Correlation Matrix",
        graph_type="heatmap",
        description="Return correlation matrix across selected stocks.",
        min_tickers=2,
    ),
    "Rolling Correlation": MetricDefinition(
        name="Rolling Correlation",
        graph_type="line",
        description="Rolling pairwise correlation between two stocks.",
        min_tickers=2,
        requires_two_tickers=True,
    ),
    "Sharpe Ratio": MetricDefinition(
        name="Sharpe Ratio",
        graph_type="line",
        description="Rolling annualized Sharpe ratio (excess return / volatility).",
        requires_single_ticker=True,
        enabled_by_default=False,
    ),
    "Cumulative Returns": MetricDefinition(
        name="Cumulative Returns",
        graph_type="line",
        description="Cumulative percentage return from the start of the period.",
        min_tickers=1,
        enabled_by_default=False,
    ),
}


class MetricRegistry:
    """Manage available metrics, including optional user-registered features."""

    def __init__(self) -> None:
        self._definitions: dict[str, MetricDefinition] = dict(BUILTIN_METRICS)
        self._calculators: dict[str, Callable] = {}

    def register(
        self,
        definition: MetricDefinition,
        calculator: Callable,
    ) -> None:
        self._definitions[definition.name] = definition
        self._calculators[definition.name] = calculator

    def get_definition(self, name: str) -> MetricDefinition:
        if name not in self._definitions:
            raise ValueError(f"Unknown metric: {name}")
        return self._definitions[name]

    def default_metrics(self) -> list[str]:
        return [name for name, d in self._definitions.items() if d.enabled_by_default]

    def optional_metrics(self) -> list[str]:
        return [name for name, d in self._definitions.items() if not d.enabled_by_default]

    def active_metrics(self, enabled_optional: list[str]) -> list[MetricDefinition]:
        active = [self._definitions[name] for name in self.default_metrics()]
        for name in enabled_optional:
            if name in self._definitions and name not in {m.name for m in active}:
                active.append(self._definitions[name])
        return active

    def graph_type(self, name: str) -> str:
        return self.get_definition(name).graph_type

    @property
    def definitions(self) -> dict[str, MetricDefinition]:
        return dict(self._definitions)
