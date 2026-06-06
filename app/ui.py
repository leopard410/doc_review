from pathlib import Path


def get_index_html() -> str:
    """Load upload UI. Tries app/static first, then public/ (Vercel CDN path)."""
    candidates = [
        Path(__file__).parent / "static" / "index.html",
        Path(__file__).parent.parent / "public" / "index.html",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError("index.html not found in app/static or public/")
