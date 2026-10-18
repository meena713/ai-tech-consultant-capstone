# AI Tech Consultant Capstone

Three connected services:
- Task 1: Python/FastAPI knowledge crawler, SQLite article index, retrieval, cited answers, and expert queue.
- Task 2: TypeScript/Express email classifier, reply drafter, feedback tracking, and guarded automation eligibility.
- Task 3: Python/FastAPI transcript-to-SOW draft, scope estimates, follow-up comparison, and human approval.

## Run
1. Install Docker Desktop / Docker Engine with Compose.
2. Copy `.env.example` to `.env`.
3. Add your Anthropic API key to `.env` if you want model generation.
4. Run `docker compose up --build`.
5. Open http://localhost:8000/docs and http://localhost:8002/docs. Task 2 health is http://localhost:3000/health.

## First test
Call Task 1 `POST /sync` to index the official sitemap. This may take a while due to the polite crawl delay. Then try `POST /ask`.
Use Task 2 `POST /draft` with `data/sample_emails_50.json` examples.
Use Task 3 `POST /generate`, then use the returned proposal ID with `/follow-up` and `/approve`.

## Important limitations
This is a runnable baseline, not a production deployment. Task 1 uses keyword search, not vector search; image/screenshot understanding and a daily scheduler are not implemented. Task 2 never sends emails; twenty unchanged drafts only mark a category eligible for review. Task 2 feedback is stored in a JSON file, suitable for a prototype but not concurrent production use. SOW hours are estimates for human review. The included evaluation cases are starter examples, not measured results. Run at least 20 cases per task and compare two model IDs using real outputs, latency, and cost before submitting.
