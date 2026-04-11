# ⚡ Jarvis AI Assistant

A full-stack AI assistant with a **FastAPI** backend, **React + Vite + Tailwind** frontend, and **SQLite** database.

## 🗂️ Project Structure

```
JARVIS AI/
├── backend/           # FastAPI app, auth, chat, notes, uploads
├── frontend/
│   ├── src/           # React UI (premium dashboard)
│   ├── dist/          # Production build output (run `npm run build`)
│   ├── package.json
│   └── vite.config.ts
├── frontend/_legacy/  # Previous vanilla static UI (optional reference)
├── jarvis.db
├── run.py
├── requirements.txt
└── .env.example
```

## 🚀 Quick Start

### 1. Backend

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set at least `SECRET_KEY` (and `GROQ_API_KEY` for AI).

### 2. Frontend (production)

From the `frontend` folder:

```bash
cd frontend
npm install
npm run build
```

This writes `frontend/dist/`, which the backend serves at **`/app`**.

### 3. Run the server

```bash
uvicorn backend.main:app --reload
```

Or:

```bash
python run.py
```

Open [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app).

### Frontend development (hot reload)

With the backend on `http://127.0.0.1:8000`:

```bash
cd frontend
npm run dev
```

Open the URL Vite prints (e.g. `http://127.0.0.1:5173/app`). API calls are proxied to the FastAPI server.

### API docs

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## 🤖 AI / chat logic

Reply and routing logic lives in `backend/main.py` (e.g. `_generate_chat_reply` and related helpers), not in a single `generate_reply()` stub.

## 📡 API overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Server status |
| GET | `/api/health` | Health + AI/provider status |
| POST | `/login`, `/register` | Auth (JWT) |
| GET | `/protected` | Current user id |
| GET/POST | `/api/chats`, `/api/chat/...` | Chats & messages |
| PATCH | `/api/conversations/{id}` | Update chat (e.g. rename) |
| GET/POST/PATCH/DELETE | `/api/notes` | Notes |

## 🛠️ Tech stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy, Pydantic v2, Uvicorn  
- **Database**: SQLite (`jarvis.db`)  
- **Frontend**: React 19, TypeScript, Vite 6, Tailwind CSS 3  
- **Markdown / code**: `marked`, `dompurify`, `highlight.js`
