"""Groq-backed explanation layer for portfolio analysis."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


SYSTEM_PROMPT = """You are the Finance Dashboard portfolio assistant.
You may discuss only stocks, portfolios, market data, portfolio analytics, and the
provided clustering results. The application has already performed all financial
calculations and machine-learning analysis. Treat the supplied portfolio context
as the only source of truth: do not invent holdings, prices, dates, metrics, or
risk groups, and do not independently calculate or estimate financial values.
Explain the supplied results clearly and mention when a requested fact is not in
the context. Do not provide personalized investment advice or execute trades.
For questions outside the stock-market context, briefly say that you can only
help with this portfolio and stock-market analysis.
"""


@dataclass
class ConversationMessage:
    role: str
    content: str
    created_at: datetime

    def to_document(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }


class PortfolioAssistant:
    """Call Groq with application-owned portfolio facts and conversation history."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or self._secret("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"

    @staticmethod
    def _secret(name: str) -> str | None:
        value = os.getenv(name)
        if value:
            return value
        try:
            import streamlit as st

            return st.secrets.get(name)
        except (ImportError, FileNotFoundError):
            return None

    @staticmethod
    def build_context(
        portfolio: Any,
        prices: Any,
        result: dict[str, Any],
        start_date: Any,
        end_date: Any,
        window: int,
    ) -> dict[str, Any]:
        holdings = {}
        for ticker, holding in portfolio.holdings.items():
            current_values = prices[ticker].dropna() if ticker in prices else []
            holdings[ticker] = {
                "quantity": holding.quantity,
                "purchase_price": holding.purchase_price,
                "current_price": float(current_values.iloc[-1]) if len(current_values) else None,
            }

        def records(frame: Any) -> list[dict[str, Any]]:
            if frame is None or frame.empty:
                return []
            return json.loads(frame.to_json(orient="records"))

        return {
            "portfolio_name": portfolio.name,
            "holdings": holdings,
            "analysis_period": {"start": str(start_date), "end": str(end_date)},
            "volatility_window_days": window,
            "calculated_metrics": records(result.get("metrics")),
            "clustering": {
                "cluster_count": result.get("cluster_count"),
                "risk_groups": records(result.get("risk_groups")),
            },
        }

    def answer(self, question: str, context: dict[str, Any], history: list[ConversationMessage]) -> str:
        if not self.api_key:
            raise RuntimeError("Configure GROQ_API_KEY in .streamlit/secrets.toml to use the assistant.")
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError("Install the groq package to use the assistant.") from exc

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend({"role": item.role, "content": item.content} for item in history)
        messages.append(
            {
                "role": "user",
                "content": f"Portfolio context (authoritative JSON):\n{json.dumps(context, default=str)}\n\nQuestion: {question}",
            }
        )
        response = Groq(api_key=self.api_key).chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()


def new_message(role: str, content: str) -> ConversationMessage:
    return ConversationMessage(role, content, datetime.now(timezone.utc))