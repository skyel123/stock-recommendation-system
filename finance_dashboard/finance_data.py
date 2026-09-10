"""Download and manage financial market data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import yfinance as yf


@dataclass
class FinanceData:
    """Container for price data fetched from external sources or uploads."""

    prices: pd.DataFrame = field(default_factory=pd.DataFrame)
    tickers: list[str] = field(default_factory=list)

    @staticmethod
    def _coerce_prices_frame(raw, ticker: str) -> pd.DataFrame:
        if raw is None or getattr(raw, "empty", True):
            return pd.DataFrame()

        if isinstance(raw.columns, pd.MultiIndex):
            frame = raw["Close"].copy()
            if isinstance(frame, pd.Series):
                frame = frame.to_frame()
        elif "Close" in raw.columns:
            frame = raw[["Close"]].copy()
        else:
            frame = raw.iloc[:, [0]].copy()

        frame.columns = [ticker]
        return frame.dropna(how="all").sort_index()

    def download(
        self,
        tickers: list[str],
        start: date,
        end: date,
        timeout_seconds: int | None = None,
    ) -> pd.DataFrame:
        """Fetch adjusted close prices from Yahoo Finance."""
        if not tickers:
            raise ValueError("At least one ticker is required.")

        normalized = [t.strip().upper() for t in tickers if t.strip()]
        if not normalized:
            raise ValueError("At least one valid ticker is required.")

        try:
            raw = yf.download(
                normalized,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=True,
                progress=False,
            )
            if raw is not None and not raw.empty:
                prices = self._coerce_prices_frame(raw, normalized[0])
                if prices.empty:
                    raise ValueError(f"No usable price data for tickers: {', '.join(normalized)}")

                if len(normalized) > 1 and isinstance(raw.columns, pd.MultiIndex):
                    prices = raw["Close"].copy()
                    prices = prices.dropna(how="all").sort_index()
                    prices.columns = [col for col in prices.columns]
                    if prices.empty:
                        raise ValueError(f"No usable price data for tickers: {', '.join(normalized)}")
                self.prices = prices
                self.tickers = list(prices.columns)
                return self.prices
        except Exception:
            pass

        frames: list[pd.DataFrame] = []
        for ticker in normalized:
            try:
                raw_ticker = yf.download(
                    [ticker],
                    start=start.isoformat(),
                    end=end.isoformat(),
                    auto_adjust=True,
                    progress=False,
                )
            except Exception:
                continue

            frame = self._coerce_prices_frame(raw_ticker, ticker)
            if not frame.empty:
                frames.append(frame)

        if not frames:
            raise ValueError(f"No usable price data for tickers: {', '.join(normalized)}")

        prices = pd.concat(frames, axis=1).sort_index()
        prices = prices.dropna(how="all")
        if prices.empty:
            raise ValueError(f"No usable price data for tickers: {', '.join(normalized)}")

        self.prices = prices
        self.tickers = list(prices.columns)
        return self.prices

    def load_from_csv(self, uploaded_file) -> list[str]:
        """Load list of stock tickers from a CSV file (e.g. watchlist)."""
        import pandas as pd
        if isinstance(uploaded_file, pd.DataFrame):
            frame = uploaded_file.copy()
        else:
            frame = pd.read_csv(uploaded_file, header=None)

        tickers = []
        for col in frame.columns:
            for val in frame[col].dropna():
                val_str = str(val).strip().upper()
                if val_str and all(c.isalnum() or c in ".-" for c in val_str):
                    if val_str not in tickers:
                        tickers.append(val_str)

        if not tickers:
            raise ValueError("CSV contains no valid ticker symbols.")

        self.tickers = tickers
        self.prices = pd.DataFrame()
        return tickers
