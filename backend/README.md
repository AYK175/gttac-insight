# Backend (FastAPI)

## Run locally

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Environment variables are shared with the existing app:

- `DATABASE_URL`
- `ANTHROPIC_API_KEY` (required for `/query/nl`, `/query/nl_run`, `/explain`)

