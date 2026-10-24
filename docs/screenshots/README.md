# Screenshot capture guide

This folder is for application screenshots used in the project README.

No screenshot files are committed yet. After running the app locally, capture the screens below from the real UI (not mockups or stock photos) and save them with these filenames:

| File | Page / view | What to show |
|---|---|---|
| `login.png` | Welcome / Log in | Email and password tabs before a session is created |
| `portfolio-management.png` | Portfolio Management | Holdings table, profit/loss, and the create-portfolio action |
| `portfolio-analysis.png` | Analyze portfolio expander | Return/volatility table and the return-versus-volatility scatter plot |
| `portfolio-assistant.png` | Portfolio Assistant | Chat about supplied holdings, metrics, and risk groups |
| `stock-details.png` | Stock Details | Historical price, returns, and 20-day volatility charts |
| `stock-prediction.png` | Stock Details | Random Forest UP/DOWN result and feature-importance chart |
| `multi-stock-analysis.png` | Multi Stock Analysis | Normalized or raw comparison chart and correlation heatmap |

Suggested capture steps:

1. Activate the virtual environment and run `streamlit run app.py`.
2. Sign in with a local test account.
3. Create a portfolio with at least four valid tickers if you want clustering and risk charts to appear.
4. Use the browser or OS screenshot tool at a desktop width (the app uses Streamlit’s wide layout).
5. Crop to the application window. Avoid including OS taskbars, API keys, or email addresses you do not want public.
6. Save PNG files in this directory using the names in the table.
7. Uncomment the matching image references in the root `README.md`.
