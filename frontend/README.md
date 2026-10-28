# EventProof Studio (frontend)

Next.js app over the EventProof backend API (`POST /runs`, `GET /runs/{id}`, `/tracks`, `/video`).

```bash
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # backend: cd ../backend && uv run uvicorn eventproof.api.main:app
npm run test:e2e                                         # Playwright smoke (API responses mocked from a recorded run)
```
