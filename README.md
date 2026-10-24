# Finance Dashboard

An interactive financial analytics application that helps users explore stock market data, manage portfolios, and inspect data-driven risk and direction estimates.

The project combines market-data retrieval, statistical metrics, unsupervised clustering, a Random Forest classifier, and a constrained language-model assistant. It is an educational Computer Science portfolio project, not a trading product.

<!-- Optional: add a one-sentence personal motivation here. -->

---

## Live Demo

A public deployment URL is not configured in this repository.

To run the application locally, see [Installation and Local Setup](#installation-and-local-setup).

<!-- If you publish a demo, replace this section with:
## Live Demo
[Launch the Application](YOUR_DEPLOYMENT_URL)
-->

---

## Application Preview

Screenshots of the live UI are not in the repository yet. Capture them from a running `streamlit run app.py` session and save them under [`docs/screenshots/`](docs/screenshots/README.md). After the files exist, uncomment the blocks below.

<!--
### Portfolio Management
![Portfolio Management](docs/screenshots/portfolio-management.png)
Holdings, purchase prices, live profit/loss, and portfolio overview charts.

### Portfolio Analysis
![Portfolio Analysis](docs/screenshots/portfolio-analysis.png)
Period return, rolling volatility, and K-Means risk groups.

### Stock Direction Prediction
![Stock Direction Prediction](docs/screenshots/stock-prediction.png)
Random Forest next-day UP/DOWN estimate and feature importance.

### Portfolio Assistant
![Portfolio Assistant](docs/screenshots/portfolio-assistant.png)
Groq chat grounded in the application's calculated analysis snapshot.
-->

Until those files are added, the fastest way to preview the app is to follow the setup steps and open:

| View | How to reach it |
|---|---|
| Welcome / authentication | First screen after launch |
| Portfolio Management | Default signed-in page |
| Stock Details | Ticker button on a holding |
| Multi Stock Analysis | Sidebar |
| Sharpe Ratio / Cumulative Returns | Enable them under Dashboard Settings |

---

## The Problem and Motivation

Raw price charts are easy to find and still hard to interpret. Return, volatility, correlation, and concentration of risk are separate questions, and they are often spread across spreadsheets, broker screens, and one-off notebooks.

This project puts those pieces in one application so a user can:

- inspect historical prices for Yahoo Finance symbols
- keep a personal watchlist and authenticated portfolios
- compare assets on a common scale
- cluster holdings by return and volatility
- ask an assistant to explain *already computed* results rather than invent new numbers

The technical motivation is to practice building a full path from external data, through calculations and models, to a persisted user interface.

<!-- Student: add a short personal “why I built this” paragraph here if you want it in applications. -->

---

## Key Features

Each item below is implemented in the current codebase. Helpers that exist only as library methods are called out separately.

### Authentication

Users sign up and log in with an email and a password of at least eight characters. Passwords are stored as scrypt hashes with a random salt (`AuthService`). The signed-in user is held in Streamlit session state. There is no password-reset flow.

### Portfolio management

On **Portfolio Management**, a user can create named portfolios, add whole-share holdings with a purchase price, edit quantity, remove holdings, and see current profit/loss from recent market prices. Ticker symbols are validated against Yahoo Finance before they are saved.

When holdings exist, the page also shows:

- a historical valuation line chart of *current* share quantities (transaction dates are not stored)
- a purchase-cost risk allocation chart using K-Means labels when at least four market-data-valid holdings exist

Persistence uses MongoDB Atlas when `MONGODB_URI` authenticates; otherwise the session uses in-memory repositories and shows a warning.

### Multi-stock analytics

**Multi Stock Analysis** downloads or reuses cached adjusted close prices, then shows:

- stock comparison in **normalized** (base 100), **raw**, or **both** modes
- a return correlation heatmap (requires at least two tickers)

Users can type tickers or import a CSV watchlist of symbols. Optional pages for **Sharpe Ratio** and **Cumulative Returns** can be enabled in Dashboard Settings. Rolling volatility and rolling correlation are implemented in `Metrics` but are not sidebar pages; 20-day annualized volatility is shown on Stock Details.

### Portfolio analysis (unsupervised learning)

The **Analyze portfolio** expander lets the user choose a date range and volatility window, download that range, and compute period return and rolling daily-return volatility. Clustering is skipped for 1–3 assets, uses up to two K-Means clusters for 4–5 assets, and up to three clusters for 6 or more. Cluster labels are mapped to Low, Medium, or High Risk by cluster volatility and plotted as a return-versus-volatility scatter chart.

### Stock direction prediction (supervised learning)

From a holding ticker, **Stock Details** shows historical prices, daily returns, and 20-day annualized volatility. **Run Prediction** downloads about five years of adjusted closes and fits a Random Forest classifier for whether the *next* trading-day close is higher (UP) or lower (DOWN). The UI reports the direction, latest close, training observation count, and feature importance. This is an on-demand historical-data estimate; it is not a live trading signal.

### Portfolio assistant

After analysis, **Portfolio Assistant** sends holdings, prices, calculated metrics, and clustering results to Groq. The system prompt forbids inventing numbers or giving personalized investment advice. Conversations are stored per user and portfolio in MongoDB, with an in-memory fallback.

### Implemented in code, not exposed as product pages

| Capability | Where it lives | Status |
|---|---|---|
| DBSCAN clustering | `PortfolioAnalysis.risk_groups(method="dbscan")` | Library method; the UI analysis path uses K-Means |
| Correlation similarity recommendations | `PortfolioAnalysis.recommendations` | Library method; not a navigation page |
| Metric registry `register()` | `MetricRegistry` | Hook exists; calculation dispatch still lives in `Metrics.calculate` |

Not implemented: company filings, news research, a trading simulator, backtesting, or portfolio optimization.

---

## Technology Stack

| Category | Technology | Purpose |
|---|---|---|
| Language | Python (developed with 3.14) | Application logic and tests |
| Web UI | Streamlit | Pages, forms, session state, navigation |
| Data processing | pandas, NumPy | Prices, returns, rolling statistics |
| Visualization | Plotly | Line charts, heatmaps, scatter and allocation charts |
| Market data | yfinance | Adjusted close downloads |
| Machine learning | scikit-learn | `StandardScaler`, `KMeans`, `DBSCAN`, `RandomForestClassifier` |
| Persistence | MongoDB Atlas via pymongo | Users, portfolios, assistant conversations |
| Local fallback | In-memory repositories | Development when Atlas is unavailable |
| Authentication | scrypt (`hashlib`) | Password hashing |
| LLM | Groq API (`groq`) | Explanations of supplied analysis JSON |
| Tests | pytest | Unit tests for metrics, portfolios, prediction, and persistence helpers |

---

## System Architecture

The Streamlit script reruns on each widget change. `DashboardController` is an orchestrator for that model, not a separate HTTP API or microservice layer.

```mermaid
flowchart TD
  User[User] --> App["app.py / Streamlit"]
  App --> Auth[AuthService]
  App --> Nav[st.navigation pages]
  Nav --> PM[Portfolio Management]
  Nav --> MSA[Multi Stock Analysis]
  Nav --> SD[Stock Details - hidden]
  Nav --> Opt[Optional metric pages]

  PM --> PS[PortfolioService]
  PM --> PA[PortfolioAnalysis]
  PM --> Assist[PortfolioAssistant]
  MSA --> Metrics[Metrics]
  SD --> Metrics
  SD --> RF[StockDirectionPredictor]

  PS --> Repo[User / Portfolio / Conversation repositories]
  Auth --> Repo
  Assist --> Repo
  Repo --> Mongo[(MongoDB Atlas)]
  Repo --> Memory[In-memory fallback]

  PA --> YF[yfinance]
  Metrics --> Cache[Session price cache]
  Cache --> YF
  RF --> YF
  Assist --> Groq[Groq chat completions]
```

**Request path.** `app.py` constructs `DashboardController` and calls `display_metrics()`. After login, Streamlit navigation runs one page. Metric pages collect dates, tickers, and display options from a settings expander; Portfolio Management omits that expander.

**Market data.** `FinanceData.download` requests adjusted closes from Yahoo Finance, then falls back to per-ticker downloads if a batch request fails. Successful frames are cached in session state so slider and date changes do not re-hit the network unless the user refreshes or changes tickers.

**Calculations.** Statistical metrics stay in `Metrics`. Portfolio return, volatility, scaling, and K-Means stay in `PortfolioAnalysis`. Charts stay in `UI`. That split keeps Streamlit rendering out of the numeric modules.

**Machine learning.** Clustering runs inside portfolio analysis on two scaled features. The Random Forest is fit only when the user clicks **Run Prediction**, using lagged return and volatility features from five years of closes.

**Persistence.** `MongoRepositories` reads `MONGODB_URI` and `MONGODB_DATABASE` from the environment or `.streamlit/secrets.toml`, pings Atlas, and creates unique indexes on email and on `(user_id, name)`. Failed authentication or connection is cached for the Streamlit session and the app continues with in-memory stores.

**LLM.** The assistant does not fetch extra market data. It receives JSON produced by `PortfolioAssistant.build_context` plus prior messages, then returns an explanation.

---

## Machine Learning Deep Dive

### Unsupervised learning: portfolio risk groups

Portfolio analysis turns each holding with price history into two features:

| Feature | Meaning in this app |
|---|---|
| Period return | Last valid close / first valid close − 1 over the selected range |
| Period volatility | Last value of a rolling standard deviation of daily returns (default window 21) |

Those two columns are standardized with `StandardScaler` so return and volatility are on comparable scales before K-Means. Without scaling, the larger-magnitude feature would dominate Euclidean distance.

K-Means assigns each asset to a cluster. Cluster count is capped by asset count so tiny portfolios are not over-clustered. Mean volatility of each cluster determines the displayed names Low, Medium, or High Risk. That label describes *relative* volatility among the selected holdings in the chosen window. It is not a credit rating or an investability score.

Holdings without usable prices, or portfolios with fewer than four valid names, remain **Unclassified** on the overview allocation chart.

`PortfolioAnalysis.risk_groups` can also run DBSCAN on mean return and annualized volatility. The Streamlit analysis expander does not call that method; it uses the K-Means path in `analyze_portfolio`.

### Supervised learning: next-day direction

`StockFeatureEngineering.prepare` requires a `Close` series, sorts by date, and builds:

| Column | Construction |
|---|---|
| `Return_1D` | One-day percent change |
| `Return_5D` | Five-day percent change |
| `Return_10D` | Ten-day percent change |
| `Volatility_20D` | 20-day rolling standard deviation of daily returns |
| `Target` | 1 if tomorrow’s close is greater than today’s; unset on the last row |

`StockDirectionPredictor` keeps rows with a valid target and finite features, requires at least 30 training rows, fits `RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42)` on that history, and predicts the most recent feature row. The UI maps `1` to UP and `0` to DOWN and charts `feature_importances_`.

What this model does *not* do in the current code:

- it does not emit class probabilities (`predict_proba` is unused)
- it does not hold out a chronological test set or report accuracy in the UI
- it does not claim that past up/down patterns will continue

A chronological split would be the honest way to score this kind of time-series classifier, because shuffling days would leak nearby information into training. That evaluation is listed as future work.

---

## Engineering Challenges and Lessons Learned

The items below are taken from the repository (error handling, tests, and module boundaries). Personal anecdotes should be added by the author where marked.

### Unreliable market downloads

**Problem.** Yahoo Finance responses can be empty, multi-indexed, or fail for a subset of tickers.  
**Approach.** Try a batch download, coerce a `Close` frame, then retry ticker-by-ticker and skip failures.  
**Solution.** `FinanceData.download` returns whatever usable columns it can and raises only when none remain. Tests cover partial and total failure.  
**Learned.** External financial APIs need defensive parsing, not a single happy-path dataframe.

### Streamlit reruns versus expensive I/O

**Problem.** Every widget change reruns the script, which would re-download prices and re-open MongoDB.  
**Approach.** Cache price frames and analysis snapshots in `st.session_state`, keyed by tickers, dates, or holding signatures. Cache Mongo init for the session after a ping.  
**Solution.** Dashboard settings changes reuse cached prices unless refresh or ticker identity changes.  
**Learned.** A reactive UI needs an explicit cache policy, or latency and rate limits dominate the UX.

### Persistence that still runs without Atlas

**Problem.** Local development and bad Atlas credentials should not crash login.  
**Approach.** Repository adapters for MongoDB and memory; unique indexes when Mongo succeeds; a visible warning when it does not.  
**Solution.** `MongoRepositories` pings before creating indexes. `DashboardController` falls back to process-level in-memory stores.  
**Learned.** A repository boundary lets the rest of the app stay the same while the backing store changes.

### Small-sample clustering

**Problem.** K-Means on two or three points produces brittle “risk groups.”  
**Approach.** Skip clustering below four assets and cap cluster count by portfolio size.  
**Solution.** The UI explains the skip and still shows return and volatility.  
**Learned.** Unsupervised models need data-size guards, not only hyperparameters.

### Grounding an LLM in application numbers

**Problem.** Language models readily invent prices, returns, and advice.  
**Approach.** Serialize holdings, metrics, and clusters as JSON; instruct the model that those values are the only source of truth; keep temperature at 0.2; refuse non-market questions.  
**Solution.** `PortfolioAssistant.build_context` plus a strict system prompt. Tests check that context uses existing calculated values.  
**Learned.** For analytics, the model should explain the pipeline’s output rather than recompute finance.

### Password storage

**Problem.** Plaintext passwords are unacceptable even in a student app.  
**Approach.** scrypt with a random salt, encoded for MongoDB documents; constant-time compare on login.  
**Solution.** `AuthService` never stores the raw password.  
**Learned.** Authentication is a hashing and validation problem before it is a UI problem.

<!-- Student: add one or two short stories about a bug you actually fixed (for example MongoDB auth, Streamlit page routing, or yfinance column shapes). -->

---

## Installation and Local Setup

Requirements: Python 3.12+ (this repo has been run with Python 3.14), Git, and optionally a MongoDB Atlas cluster and a Groq API key.

```bash
git clone https://github.com/skyel123/stock-recommendation-system.git
cd stock-recommendation-system
```

If your local folder name differs, `cd` into the directory that contains `app.py`.

Create and activate a virtual environment:

```bash
python -m venv .venv
```

```bash
# macOS / Linux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` once for your user account.

Install dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

Create `.streamlit/secrets.toml` (this path is gitignored). Do not commit real credentials.

```toml
MONGODB_URI = "mongodb+srv://USERNAME:PASSWORD@CLUSTER.mongodb.net/?appName=APP_NAME"
MONGODB_DATABASE = "finance_dashboard"
GROQ_API_KEY = "your-groq-api-key"
```

Equivalent environment variables:

| Variable | Required for | Notes |
|---|---|---|
| `MONGODB_URI` | Saved users, portfolios, chats | Atlas SRV URI; URL-encode special characters in the password |
| `MONGODB_DATABASE` | Named database | Defaults to `finance_dashboard` if omitted |
| `GROQ_API_KEY` | Portfolio Assistant | Also readable from Streamlit secrets |
| `GROQ_MODEL` | Optional model override | Code default is `openai/gpt-oss-120b` |

Without a working `MONGODB_URI`, the app still starts. Accounts and portfolios then last only for the current process.

Start the UI:

```bash
streamlit run app.py
```

Entry point: [`app.py`](app.py). It sets the page title to Finance Dashboard and delegates to `DashboardController.display_metrics()`.

---

## How to Use the Application

1. Launch `streamlit run app.py` and open the local URL Streamlit prints.
2. Create an account (**Sign up**) or **Log in**.
3. On **Portfolio Management**, create a portfolio, add tickers with share counts and purchase prices, and inspect profit/loss.
4. Open **Analyze portfolio**, choose dates and a volatility window, then run analysis. With four or more valid assets, inspect the risk-group scatter plot.
5. Ask the **Portfolio Assistant** about those supplied metrics (requires `GROQ_API_KEY`).
6. Click a holding ticker to open **Stock Details**. Review price, return, and volatility charts, then optionally **Run Prediction**.
7. Open **Multi Stock Analysis**. In Dashboard Settings, set tickers (or upload a CSV watchlist), dates, comparison mode, and optional Sharpe / cumulative-return pages.

---

## Testing and Reliability

The repository includes **unit tests**, not browser or live-Atlas integration tests.

```bash
python -m pytest tests/ -v
```

| File | What it checks |
|---|---|
| `tests/test_metrics.py` | Volatility, comparison modes, correlation, date filters, Sharpe, cumulative returns, registry, CSV watchlists, download fallbacks |
| `tests/test_portfolio_management.py` | Portfolio CRUD, auth rules, analysis safeguards, aggregation, risk-allocation sanitization, assistant context, conversation isolation, Mongo setting helpers |
| `tests/test_stock_prediction.py` | Feature columns, next-day target, close-column validation, Random Forest output shape |

Other validation lives in application code:

- ticker and quantity checks before holdings are saved
- date-range checks for analysis and charts
- Yahoo Finance empty-result errors surfaced in the UI
- Mongo ping failure → in-memory warning
- missing Groq key → assistant error instead of a crash
- clustering skipped for small portfolios

There is no reported code-coverage percentage in this repository, and Groq calls are not mocked in CI.

---

## Future Improvements

These are **not** implemented:

- Out-of-sample / chronological evaluation for the Random Forest, including probabilities
- Expose DBSCAN or similarity recommendations in the UI
- User-defined metric formulas (`MetricRegistry.register` is only a hook today)
- Password reset and durable session tokens
- Streamlit interaction tests and mocked Groq tests
- Alternate data vendors (Alpha Vantage, FRED, and similar)
- Explicit “clear CSV / switch to live data” control
- Financial-document RAG, portfolio optimization, backtesting, Monte Carlo paths, and price alerts

---

## What I Learned

This section is written so a reviewer can map the repo to Computer Science topics. Customize the first-person sentences before using this README in an application.

The project demonstrates:

- **Modular design.** Controllers, services, repositories, metrics, analysis, prediction, and UI are separate modules.
- **Data structures.** Typed dataclasses for `User`, `Holding`, and `Portfolio`; pandas frames keyed by date and ticker; session dictionaries for caches.
- **Algorithms and statistics.** Rolling standard deviation, correlation, cumulative returns, a simple Sharpe construction, K-Means, and a tree ensemble.
- **Feature engineering.** Lagged returns, rolling volatility, and a binary next-day label from a close series.
- **Databases.** Document models, unique indexes, and a repository interface with a memory adapter.
- **Security basics.** scrypt password hashes and ownership checks when loading a portfolio for analysis.
- **API integration.** yfinance downloads with fallbacks; Groq chat with a constrained prompt.
- **Web state.** Streamlit reruns, hidden pages, and cache invalidation when holdings or tickers change.
- **Testing.** pytest for calculations and use cases that do not require a browser.

Example of a specific statement you can keep or edit:

> I learned how to turn a close-price series into lagged return and volatility features, label the next day’s direction, and report Random Forest feature importance—while still treating the output as a historical estimate rather than a forecast I would trade on.

---

## Limitations and Disclaimer

- Yahoo Finance data can be delayed, missing, or unavailable for some symbols.
- Models and charts describe the selected historical window only.
- Next-day UP/DOWN output is uncertain and is not evaluated out of sample in this repo.
- Clustering groups similar return/volatility profiles; it does not rank investment quality.
- The assistant may still err; it is limited to the JSON context but is not a verifier of finance.
- Performance charts value *current* quantities through time because trades are not dated.
- This is an educational project. It is **not financial advice**, and it does not place trades.

---

## Author and Acknowledgments

**Author:** [Your name]  
**GitHub:** [skyel123](https://github.com/skyel123)  
**Repository:** [stock-recommendation-system](https://github.com/skyel123/stock-recommendation-system)  
**Portfolio / contact:** [add if you want them public]

No additional collaborators, awards, or institutional affiliations are recorded in this repository.

Libraries and services used: [Streamlit](https://streamlit.io/), [pandas](https://pandas.pydata.org/), [NumPy](https://numpy.org/), [Plotly](https://plotly.com/), [yfinance](https://github.com/ranaroussi/yfinance), [scikit-learn](https://scikit-learn.org/), [pymongo](https://www.mongodb.com/docs/drivers/pymongo/), [MongoDB Atlas](https://www.mongodb.com/atlas), [Groq](https://groq.com/), and [pytest](https://pytest.org/). Market data belongs to its providers and is used here for education.

---

## Student input checklist

Fill these before treating the README as application-ready:

1. Your name, and optional website or email.
2. A short personal motivation (Section 1 or 4).
3. Screenshots in `docs/screenshots/` and uncommented image tags.
4. Live demo URL, only if you actually deploy the app.
5. One or two first-person debugging stories you personally remember.
6. Confirm the GitHub username and clone URL if the remote ever changes.
