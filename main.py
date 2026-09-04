"""
main.py
FastAPI backend for the Legal Case Analysis & Court Speech Generation System.

Endpoints:
    POST /api/analyze              - upload a PDF/DOCX/TXT, run the LangGraph
                                      pipeline, and generate a legal brief
                                      (.docx) plus a structured fact sheet (.json)
    GET  /api/download/docx/{id}   - download the generated legal brief
    GET  /api/download/json/{id}   - download the structured fact sheet
    GET  /api/status/{id}          - check processing status / retrieve results inline
    GET  /health                   - simple liveness check
"""
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()


import json
import os
import shutil
import uuid
from typing import Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from document_builder import save_case_outputs
from state_graph import run_case_pipeline

UPLOAD_DIR = os.environ.get("LEGAL_UPLOAD_DIR", "uploads")
OUTPUT_DIR = os.environ.get("LEGAL_OUTPUT_DIR", "output")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(
    title="Legal Case Analysis & Court Speech Generation API",
    description="Uploads case documents, runs a LangGraph legal-analysis pipeline, "
                "and generates downloadable legal briefs and fact sheets.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory registry mapping file_id -> generated output paths & status.
# For a production deployment this should be backed by a database.
_JOB_REGISTRY: Dict[str, Dict[str, str]] = {}


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze_case(
    file: UploadFile = File(..., description="Case document (PDF, DOCX, or TXT)"),
    client_role: str = Form(
        "Plaintiff / Victim",
        description="Which side the client represents: 'Plaintiff / Victim' or 'Defendant / Respondent'",
    ),
) -> JSONResponse:
    original_name = file.filename or "uploaded_file"
    extension = os.path.splitext(original_name)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Allowed types: {sorted(ALLOWED_EXTENSIONS)}",
        )

    file_id = uuid.uuid4().hex
    saved_upload_path = os.path.join(UPLOAD_DIR, f"{file_id}{extension}")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Uploaded file exceeds the 25MB size limit.")

    with open(saved_upload_path, "wb") as destination:
        destination.write(file_bytes)

    if client_role not in {"Plaintiff / Victim", "Defendant / Respondent"}:
        client_role = "Plaintiff / Victim"

    try:
        final_state = run_case_pipeline(
            file_path=saved_upload_path,
            file_name=original_name,
            client_role=client_role,
            file_id=file_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}") from exc

    try:
        output_paths = save_case_outputs(final_state)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Document generation failed: {exc}") from exc

    _JOB_REGISTRY[file_id] = {
        "docx_path": output_paths["docx_path"],
        "json_path": output_paths["json_path"],
        "original_name": original_name,
        "status": final_state.get("status", "unknown"),
    }

    with open(output_paths["json_path"], "r", encoding="utf-8") as json_file:
        fact_sheet = json.load(json_file)

    return JSONResponse(
        content={
            "file_id": file_id,
            "status": final_state.get("status", "unknown"),
            "errors": final_state.get("errors", []),
            "fact_sheet": fact_sheet,
            "download_links": {
                "docx": f"/api/download/docx/{file_id}",
                "json": f"/api/download/json/{file_id}",
            },
        }
    )


@app.get("/api/status/{file_id}")
def get_status(file_id: str) -> Dict[str, str]:
    job = _JOB_REGISTRY.get(file_id)
    if not job:
        raise HTTPException(status_code=404, detail="No job found for this file_id.")
    return {"file_id": file_id, "status": job["status"]}


@app.get("/api/download/docx/{file_id}")
def download_docx(file_id: str) -> FileResponse:
    job = _JOB_REGISTRY.get(file_id)
    docx_path = job["docx_path"] if job else os.path.join(OUTPUT_DIR, f"{file_id}_legal_brief.docx")

    if not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="Legal brief document not found for this file_id.")

    return FileResponse(
        path=docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"legal_brief_{file_id}.docx",
    )


@app.get("/api/download/json/{file_id}")
def download_json(file_id: str) -> FileResponse:
    job = _JOB_REGISTRY.get(file_id)
    json_path = job["json_path"] if job else os.path.join(OUTPUT_DIR, f"{file_id}_fact_sheet.json")

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Fact sheet JSON not found for this file_id.")

    return FileResponse(
        path=json_path,
        media_type="application/json",
        filename=f"fact_sheet_{file_id}.json",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
