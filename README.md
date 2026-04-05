# ⚡ Jarvis AI Assistant

A clean, full-stack AI assistant application with a **FastAPI** backend, vanilla **HTML/CSS/JS** frontend, and **SQLite** database.

## 🗂️ Project Structure

```
JARVIS AI/
├── backend/
│   ├── __init__.py       # Package init
│   ├── main.py           # FastAPI app & all routes
│   ├── database.py       # SQLite connection (SQLAlchemy)
│   ├── models.py         # ORM Models (Conversations, Messages, Notes)
│   ├── schemas.py        # Pydantic request/response schemas
│   └── crud.py           # Database CRUD operations
│
├── frontend/
│   ├── index.html        # Main UI shell
│   └── static/
│       ├── css/
│       │   └── style.css # Premium dark glassmorphism UI
│       └── js/
│           └── app.js    # Frontend logic & API calls
│
├── jarvis.db             # SQLite database (auto-created on first run)
├── run.py                # Convenience startup script
├── requirements.txt      # Python dependencies
└── .env.example          # Environment variable template
```

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the server

```bash


```

Or directly with uvicorn:

```bash
uvicorn backend.main:app --reload
```

### 3. Open the app

Visit [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app) in your browser.
The API root at [http://127.0.0.1:8000](http://127.0.0.1:8000) returns a lightweight status response.

### 4. API Docs

FastAPI auto-generates interactive docs at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## 🤖 Adding a Real AI Model

The reply logic lives in `backend/main.py` inside the `generate_reply()` function. Swap it with any AI provider:

```python
# Example: OpenAI
import openai
def generate_reply(message: str) -> str:
    openai.api_key = os.getenv("OPENAI_API_KEY")
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": message}]
    )
    return response.choices[0].message.content
```

## 📡 API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Lightweight server status |
| GET | `/api/health` | Health check |
| POST | `/api/chat` | Send a message to Jarvis |
| GET | `/api/conversations` | List conversations |
| POST | `/api/conversations` | Create conversation |
| GET | `/api/conversations/{id}/messages` | Get messages |
| GET | `/api/notes` | List notes |
| POST | `/api/notes` | Create note |
| PATCH | `/api/notes/{id}` | Update note |
| DELETE | `/api/notes/{id}` | Delete note |

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy, Pydantic v2
- **Database**: SQLite (file: `jarvis.db`)
- **Frontend**: HTML5, Vanilla CSS (glassmorphism), Vanilla JS (ES2020+)
- **Server**: Uvicorn (ASGI)
