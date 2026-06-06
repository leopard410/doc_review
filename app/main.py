import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from docx import Document
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.config import settings
from app.services.ai_analyzer import AnthropicAnalyzer
from app.services.annotator import process_document
from app.services.chapter_parser import detect_chapters, get_chapter_text

INDEX_HTML_PATH = Path(__file__).parent / "templates" / "index.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="DOCX Editorial Annotator", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.post("/process")
async def process_docx(
    file: UploadFile = File(...),
    closing_heading: str = Form(default=None),
    chapter_heading_styles: str = Form(default=None),
):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Upload must be a .docx file")

    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY is not configured. Set it in .env",
        )

    job_id = uuid.uuid4().hex[:12]
    upload_path = Path(settings.upload_dir) / f"{job_id}_{file.filename}"
    output_path = Path(settings.output_dir) / f"{job_id}_annotated_{file.filename}"

    try:
        with upload_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()

    heading_styles = None
    if chapter_heading_styles:
        heading_styles = tuple(
            style.strip() for style in chapter_heading_styles.split(",") if style.strip()
        )

    heading_text = closing_heading or settings.closing_heading_default

    try:
        document = Document(str(upload_path))
        chapters = detect_chapters(document, heading_styles)
        analyzer = AnthropicAnalyzer()

        analyses = []
        for chapter in chapters:
            analysis = analyzer.analyze_chapter(
                chapter.title,
                get_chapter_text(document, chapter),
                include_emphasis=chapter.is_odd,
                closing_heading=heading_text,
            )
            analyses.append((chapter, analysis))

        process_document(str(upload_path), str(output_path), analyses, heading_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc

    return FileResponse(
        path=str(output_path),
        filename=f"annotated_{file.filename}",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"X-Job-Id": job_id, "X-Chapters-Processed": str(len(chapters))},
    )
