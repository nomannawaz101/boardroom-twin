# Boardroom Twin

A multi-agent proposal simulator: a proposal team drafts, a client board chosen per brief reviews it, and code decides scores, gates, costs and the verdict.

## Rules

- Never create, request or store an Anthropic API key. Ask before adding any paid or new service.
- Ask before adding any library not already in `requirements.txt` or `requirements-dev.txt`.
- Layers: `routers/` parse HTTP and call `services/`; `services/` orchestrate; `domain/` and `guards/` are pure code with no network. A lower layer never imports a higher one.
- Models write and judge; code decides every score, vote, cost, date, gate outcome and verdict.
- Limits, caps, prices and model names live in `config.py`. Type hints on every function; pydantic at every boundary.
- Never log or print brief content, model output or environment values. AI text is rendered with `textContent` only.
- Plain HTML, CSS and JavaScript with system fonts. No CDN, no framework.
- Tests use the fake model and never call a real one.
- Work on a branch per phase (`phase-N-name`); never push to `main` directly.

## Commands

```sh
python -m venv .venv
".venv/Scripts/python" -m pip install -r requirements-dev.txt
".venv/Scripts/python" -m pytest
".venv/Scripts/python" -m ruff check . && ".venv/Scripts/python" -m ruff format --check .
".venv/Scripts/python" -m uvicorn app:app --reload
".venv/Scripts/python" scripts/check_llm.py
".venv/Scripts/python" scripts/secret_scan.py
```

The pre-commit hook runs `scripts/secret_scan.py`.
