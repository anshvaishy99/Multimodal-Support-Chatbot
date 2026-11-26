# Multimodal Support Chatbot MVP

An unauthenticated local-demo chatbot using Streamlit, FastAPI, MySQL, and Gemini.
It accepts text, images, and audio, answers questions using uploaded PDF/text
documents, and can generate spoken responses when the configured Gemini TTS model
supports audio output.

## Important safety and privacy limitations

- This MVP has no user authentication or authorization. All uploaded documents are
  stored in one shared MySQL knowledge base and are visible to anyone who can reach
  the app. Do not expose it publicly or upload sensitive documents.
- Chat text and attached media are sent to the configured Google Gemini API. Review
  the provider's data terms before using real or sensitive conversations.
- Chat history is held in the current Streamlit browser session and is not stored in
  MySQL. Uploaded document contents are stored in MySQL.
- The assistant is not a therapist, clinician, or emergency service. It must not be
  relied on for crisis response.
- Retrieval uses simple keyword overlap, not semantic/vector search. Answers may miss
  relevant passages; verify important information against the cited source.

## Requirements

- Python 3.10+
- MySQL 8.0+ (a database/schema named `support_chatbot` by default)
- A Gemini API key with access to the configured models

## Setup

In PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set the values in `.env`, including `GEMINI_API_KEY` and MySQL credentials. The app
loads this file from the project directory. Create the database once in MySQL:

```sql
CREATE DATABASE support_chatbot CHARACTER SET utf8mb4;
```

The application creates its document tables on first use. Environment variables
already defined in the shell take precedence over values in `.env`. For example:

```powershell
$env:GEMINI_API_KEY = "your-key"
$env:MYSQL_PASSWORD = "your-mysql-password"
```

Start the API in one terminal:

```powershell
uvicorn app.main:app --reload
```

Start Streamlit in another terminal:

```powershell
streamlit run streamlit_app.py
```

The UI opens at `http://localhost:8501`; the API health check is at
`http://localhost:8000/health` (`ready` requires MySQL and Gemini configuration).

Optional audio playback requires a Gemini TTS model available to your API key. Set
`GEMINI_TTS_MODEL` to a supported model if the default is unavailable. The text
conversation and multimodal input model are configured separately with `GEMINI_MODEL`.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## MVP and follow-up plan

**Included MVP:** text/image/audio input, grounded text responses, PDF/TXT ingestion,
MySQL persistence, source labels, optional Gemini speech output, input size/type
validation, and an empathetic non-clinical response policy.

**After the MVP:** add authentication and per-user document isolation before any
multi-user/public deployment; introduce semantic retrieval and evaluation; add
retention/deletion controls, deployment secrets management, rate limiting, and
security/privacy review; then consider richer generated media output.
