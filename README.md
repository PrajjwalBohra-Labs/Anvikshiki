##Anvikshiki

Anvikshiki is a quiet place for serious questions.

The name points to the practice of looking closely: asking better questions, staying near the evidence, and remaining open to being wrong. Anvikshiki gives you room to gather sources, follow an idea, notice uncertainty, and see how your understanding changes over time.

It is not meant to think for you or force every question into a neat conclusion. It is a companion for careful, curious thinking.

## Running locally

You will need Python 3.11+, Node.js, Docker, and Ollama.

```powershell
git clone <https://github.com/PrajjwalBohra-Labs/Anvikshiki.git>
cd anvikshiki
python -m venv .venv
\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d postgres
alembic upgrade head
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the application at `http://localhost:5173` or the machine's private LAN
address, such as `http://192.168.1.38:5173`. The frontend derives the API host
from the browser host by default. Set `VITE_API_BASE_URL` only when the API is
on a different host, for example `http://192.168.1.38:8000/api/v1`.

`/health` reports process/runtime health and database status. `/ready` returns
HTTP 200 only when the configured database (and pgvector in PostgreSQL mode)
is available; a listening Uvicorn process alone is not application readiness.

Authentication is intentionally username-only: `POST /api/v1/users` creates a
new identity, while `POST /api/v1/auth/login` authenticates an existing
username and issues a bearer session. The browser stores that session token
locally for persistence; browser identity is not used as authentication.

## Checks

```powershell
pytest
cd frontend
npm test
```

Keep local secrets in `.env`; do not commit that file.
