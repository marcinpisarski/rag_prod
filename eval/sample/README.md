# Financial Consolidation System

Enterprise-grade financial consolidation system that integrates with **QuickBooks Online (QBO)** to aggregate, consolidate, and analyze financial data across multiple companies.

## What it does

- Pulls financial data (accounts, transactions, reports) from multiple QBO companies via OAuth2
- Converts currencies to a single base currency using configurable exchange rates
- Detects and eliminates intercompany transactions automatically
- Generates consolidated P&L, Balance Sheet, and Cash Flow statements
- Provides budget vs. actual variance analysis and multi-period forecasting
- Exposes a REST API (FastAPI) secured with API Keys and JWT tokens
- Persists all data locally in SQLite (dev) or PostgreSQL (prod)

---

## Project structure

```
QuickBooks/
├── main.py               # FastAPI app entry point, CORS, health check
├── config.py             # All configuration via environment variables
├── models.py             # Pydantic data models (enums, QBO objects, financial statements)
├── qbo_client.py         # QuickBooks API client (OAuth2, retry logic, rate limiting)
├── accounting_engine.py  # Consolidation logic, intercompany elimination, forecasting
├── data_storage.py       # SQLite/PostgreSQL persistence layer
├── internal_api.py       # FastAPI router — all /internal/* endpoints
├── requirements.txt      # Python dependencies
└── start.sh              # Quick-start reference script
```

---

## Architecture

```
QBO API
   │  OAuth2 / REST
   ▼
QuickBooksClient          ← fetches raw data per company
   │
   ▼
AccountingEngine          ← normalizes, converts currencies, eliminates intercompany, aggregates
   │
   ├── DataStorage         ← persists companies, transactions, reports, audit trail
   │
   └── InternalAPI         ← exposes consolidated results via FastAPI endpoints
          │
          ▼
    External callers (Bubble, microservices, dashboards)
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

### 3. Initialize the database

```bash
python -c "from data_storage import DataStorage; DataStorage()"
```

This creates all tables in `financial_data.db` (SQLite default).

### 4. Start the server

```bash
uvicorn main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Configuration reference

All settings are in `config.py` and loaded from environment variables. See `.env.example` for a full list.

| Variable | Description | Default |
|---|---|---|
| `QBO_CLIENT_ID` | QuickBooks OAuth2 client ID | — |
| `QBO_CLIENT_SECRET` | QuickBooks OAuth2 client secret | — |
| `QBO_REDIRECT_URI` | OAuth2 callback URL | — |
| `QBO_ENVIRONMENT` | `sandbox` or `production` | `sandbox` |
| `FINANCE_API_KEY` | API key for finance department access | — |
| `AUDIT_API_KEY` | API key for audit team access | — |
| `MANAGEMENT_API_KEY` | API key for management access | — |
| `JWT_SECRET_KEY` | Secret for signing JWT tokens | — |
| `DATABASE_URL` | SQLite or PostgreSQL connection string | `sqlite:///./financial_data.db` |
| `EXCHANGE_RATE_API_KEY` | OpenExchangeRates API key | — |
| `REDIS_URL` | Redis for exchange rate caching | `redis://localhost:6379/0` |

---

## API endpoints

All `/internal/*` endpoints require an API Key in the `Authorization: Bearer <key>` header.

### System

| Method | Path | Description |
|---|---|---|
| GET | `/` | Service status and supported features |
| GET | `/health` | Health check for monitoring |

### Internal API

| Method | Path | Description |
|---|---|---|
| POST | `/internal/consolidate` | Run financial consolidation for a set of companies |
| GET | `/internal/companies` | List all registered companies |
| GET | `/internal/company/{id}/financials` | Get historical financials for one company |
| GET | `/internal/consolidation/{id}` | Retrieve a past consolidation result |
| GET | `/internal/consolidations` | List all consolidation runs (paginated) |
| POST | `/internal/tokens` | Generate a JWT token for a department |
| POST | `/internal/oauth/tokens` | Store QuickBooks OAuth2 credentials for a company |
| POST | `/internal/budget/upload` | Upload budget data for variance analysis |
| GET | `/internal/dashboard` | Summary KPIs and intercompany overview |
| GET | `/internal/export` | Export statements as Excel / PDF / CSV |

### Consolidation request body (`POST /internal/consolidate`)

```json
{
  "company_ids": ["comp_1", "comp_2"],
  "period_start": "2025-01-01",
  "period_end": "2025-06-30",
  "base_currency": "USD",
  "consolidation_method": "Full",
  "include_details": true,
  "include_intercompany": true,
  "include_budget_vs_actual": false
}
```

---

## Authentication

Two layers:

1. **API Key** — passed as `Authorization: Bearer <key>`. Three keys are configured per department (`finance_department`, `audit_team`, `management`).
2. **JWT** — short-lived tokens (24 h) generated via `POST /internal/tokens`. Intended for microservice-to-microservice calls.

---

## Consolidation methods

| Method | When to use |
|---|---|
| `Full` | Fully-owned subsidiaries (default) |
| `Equity` | Associated companies (significant influence, <50% ownership) |
| `Proportional` | Joint ventures |

---

## Intercompany detection

The engine flags transactions as intercompany when:
- Customer or vendor name matches a known entity from another company in the group
- Transaction description contains keywords from `INTERCOMPANY_KEYWORDS` in `config.py` (e.g., `"intercompany"`, `"subsidiary"`, `"intra-group"`)

Detected transactions are eliminated from the consolidated P&L before the final report is generated.

---

## Database schema

10 tables in SQLite/PostgreSQL:

| Table | Contents |
|---|---|
| `companies` | QBO company metadata |
| `accounts` | Chart of accounts per company |
| `transactions` | All fetched transactions |
| `trial_balances` | Trial balance snapshots |
| `pnl_statements` | P&L statement records |
| `balance_sheets` | Balance sheet records |
| `consolidated_financials` | Consolidation run results |
| `intercompany_transactions` | Flagged and eliminated transactions |
| `audit_trail` | Every consolidation action with user and timestamp |
| `exchange_rates` | Cached currency rates (1 h TTL) |

---

## Supported currencies

USD, EUR, GBP, PLN, CAD, AUD, JPY, CHF, CNY

Exchange rates are fetched from [OpenExchangeRates](https://openexchangerates.org) and cached for 1 hour (configurable via `CACHE_TTL_SECONDS`).

---

## QuickBooks OAuth2 setup

Before running consolidations you must register OAuth credentials for each company:

```bash
curl -X POST http://localhost:8000/internal/oauth/tokens \
  -H "Authorization: Bearer finance_secure_key_2025" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "comp_1",
    "realm_id": "9341454165685533",
    "access_token": "<QBO_ACCESS_TOKEN>",
    "refresh_token": "<QBO_REFRESH_TOKEN>",
    "expires_at": "2025-07-03T12:00:00"
  }'
```

Tokens are stored in the `oauth_tokens` table and automatically refreshed when a 401 is received from the QBO API.
