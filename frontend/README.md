## GTTAC Insight Frontend

Next.js dashboard UI for the GTTAC Insight backend.

## Getting Started

Create `.env.local` (optional):

```bash
cp .env.local.example .env.local
```

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

By default, the UI expects the API at `http://localhost:8000`. Override with `NEXT_PUBLIC_API_BASE`.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Key screens

- **Dashboard overview**: KPI cards + top distributions (region, country, ideology, tactic, weapon type, group).\n+- **SQL Query Builder** (left): natural language prompt + filters.\n+- **Results** (right): table preview + RAG-assisted explanation panel.
