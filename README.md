# DOCX Editorial Annotator (MVP)

A FastAPI proof-of-concept that processes Microsoft Word (`.docx`) manuscripts chapter by chapter, uses the Anthropic API to identify editorial review points, and returns an annotated document.

**This tool flags items for human review only.** It does not rewrite or auto-correct manuscript content.

## Features

- **Chapter-by-chapter processing** — chapters are detected via Word heading styles (default: `Heading 1`)
- **Editorial review highlights** — potential spelling issues, unusual words, and typographical flags
- **Emphasis suggestions** — on odd chapters (1, 3, 5…), highlights one sentence for emphasis and one for block quote
- **Closing heading insertion** — inserts a configurable closing heading (default: `A manner of closing`) near the end of each chapter

## Requirements

- Python 3.11+
- Anthropic API key

## Setup

```bash
cd /path/to/simple

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

## Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 for the upload UI, or http://localhost:8000/docs for the API reference.

## Create a sample document

```bash
python scripts/create_sample_docx.py
```

This writes `sample/manuscript.docx` with three chapters and intentional editorial flags (`unusal`, `Teh`, etc.).

## Process a document

### curl

```bash
curl -X POST "http://localhost:8000/process" \
  -F "file=@sample/manuscript.docx" \
  -o annotated_manuscript.docx
```

### With options

```bash
curl -X POST "http://localhost:8000/process" \
  -F "file=@sample/manuscript.docx" \
  -F "closing_heading=A manner of closing" \
  -F "chapter_heading_styles=Heading 1" \
  -F "include_report=true"
```

### Python

```python
import requests

with open("sample/manuscript.docx", "rb") as f:
    response = requests.post(
        "http://localhost:8000/process",
        files={"file": ("manuscript.docx", f)},
        data={"closing_heading": "A manner of closing"},
    )

with open("annotated_manuscript.docx", "wb") as out:
    out.write(response.content)
```

## Annotation legend

| Highlight color | Meaning |
|----------------|---------|
| Yellow | Potential spelling issue |
| Turquoise | Unusual or suspicious word |
| Bright green | Possible typographical issue |
| Pink | Suggested emphasis (odd chapters) |
| Gray | Suggested block quote (odd chapters) |

Italic bracketed notes (e.g. `[spelling: …]`) are added next to matched highlights when the AI provides a reason.

## Configuration

Environment variables (`.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Model used for analysis |
| `CLOSING_HEADING_DEFAULT` | `A manner of closing` | Default closing heading text |

## Project layout

```
app/
  main.py                 # FastAPI endpoints
  config.py               # Settings
  models.py               # Pydantic schemas
  services/
    chapter_parser.py     # Chapter detection
    ai_analyzer.py        # Anthropic integration
    annotator.py          # Highlight + heading insertion
    docx_helpers.py       # Text highlighting utilities
scripts/
  create_sample_docx.py   # Sample manuscript generator
```

## Limitations (MVP)

- Highlight matching is best-effort; phrases split across Word runs may be missed
- Comment/track-changes support is not implemented; highlights and inline notes are used instead
- Large documents incur per-chapter API costs and processing time
- Formatting is preserved where possible, but complex run structures may simplify on highlight

## Deploy to Vercel

Vercel supports this FastAPI app with zero extra wiring. The repo already includes `pyproject.toml` and `vercel.json`.

### 1. Import the GitHub repo

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your connected GitHub repository
3. Leave **Framework Preset** as auto-detected (FastAPI)
4. Do not set a custom build command

### 2. Add environment variables

In **Project → Settings → Environment Variables**, add:

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | your Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` (optional) |
| `CLOSING_HEADING_DEFAULT` | `A manner of closing` (optional) |

Redeploy after saving env vars.

### 3. Deploy

Vercel deploys automatically on every push to `main`, or run locally:

```bash
npm i -g vercel   # if you don't have the CLI
vercel login
vercel --prod
```

Your upload UI will be at `https://your-project.vercel.app/`.

### Vercel limitations

This MVP can work on Vercel, but keep these constraints in mind:

- **Timeouts** — each upload runs as one serverless function. Multi-chapter manuscripts with several Anthropic calls may exceed limits on the Hobby plan (10s). Pro allows longer runs (up to 300s with `vercel.json`).
- **Upload size** — request body is limited to about **4.5 MB**.
- **No persistent disk** — files are written to `/tmp` during a request only.

For heavier manuscripts, consider **Railway**, **Render**, or **Fly.io** instead — they are better suited to long-running Python APIs.

## License

Internal proof-of-concept — use at your discretion.
