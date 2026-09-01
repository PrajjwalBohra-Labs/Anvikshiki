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
uvicorn backend.app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the application at `http://localhost:5173`. The API runs at `http://localhost:8000`.

## Checks

```powershell
pytest
cd frontend
npm test
```

Keep local secrets in `.env`; do not commit that file.
