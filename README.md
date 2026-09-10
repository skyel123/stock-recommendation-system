# stock-recommendation-system

## Finance Dashboard setup

Install dependencies and configure MongoDB Atlas before starting Streamlit:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:MONGODB_URI = "mongodb+srv://..."
$env:MONGODB_DATABASE = "finance_dashboard"
streamlit run app.py
```

`MONGODB_URI` is required for persistent users and portfolios. Without it, the app uses in-memory repositories for local development only. MongoDB indexes enforce unique user emails and portfolio names per user.
