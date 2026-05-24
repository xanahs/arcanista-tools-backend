from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .character_validator import validate_character_sheet_payload
from .encounter import build_encounter_response
from .pdf_compiler import OUTPUT_DIR, compile_character_sheet


ROOT = Path(__file__).resolve().parents[1]
PRIVACY_PAGE = ROOT / "privacy.html"

app = FastAPI(
    title="Arcanista Tools Backend",
    version="1.0.0",
    description="PDF character sheet compiler and D&D 5e encounter builder for Arcanista del Tavolo.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/privacy", include_in_schema=False)
@app.get("/privacy.html", include_in_schema=False)
def privacy_policy():
    if PRIVACY_PAGE.exists():
        return FileResponse(str(PRIVACY_PAGE), media_type="text/html")
    return HTMLResponse("<h1>Informativa Privacy - Arcanista del Tavolo</h1>")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("ARCANISTA_API_KEY")
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key.",
        )


@app.post("/character-sheet/fill-italian-5e")
async def fill_italian_5e_character_sheet(
    request: Request,
    payload: dict[str, Any],
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    return _validate_then_compile_character_sheet(payload, base_url=base_url)


@app.post("/character-sheet/validate-5e-2014")
def validate_5e_2014_character_sheet(
    payload: dict[str, Any],
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    return validate_character_sheet_payload(payload)


@app.post("/character-sheet/validate-and-fill-italian-5e")
async def validate_and_fill_italian_5e_character_sheet(
    request: Request,
    payload: dict[str, Any],
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    return _validate_then_compile_character_sheet(payload, base_url=base_url)


@app.post("/encounters/build-or-balance-5e-2014")
def build_or_balance_5e_2014_encounter(
    payload: dict[str, Any],
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    return build_encounter_response(payload)


def _validate_then_compile_character_sheet(payload: dict[str, Any], base_url: str) -> dict[str, Any]:
    validation_report = validate_character_sheet_payload(payload)
    force_fill = bool(payload.get("force_fill_when_incomplete"))
    if not validation_report.get("ready_for_pdf") and not force_fill:
        return {
            "status": "needs_review",
            "pdf_url": None,
            "file_id": None,
            "filled_fields": [],
            "unfilled_fields": validation_report.get("missing_required", []),
            "warnings": [
                "PDF non generato: la validazione ha trovato problemi bloccanti.",
                "Risolvi i blocker oppure reinvia con force_fill_when_incomplete=true per generare lasciando campi incompleti.",
            ],
            "validation_report": validation_report,
        }

    result = compile_character_sheet(payload, base_url=base_url)
    result["validation_report"] = validation_report
    result["warnings"] = [
        *result.get("warnings", []),
        *[item.get("message", "") for item in validation_report.get("warnings", []) if item.get("message")],
    ]
    if force_fill and not validation_report.get("ready_for_pdf"):
        result["status"] = "needs_review"
        result["warnings"].insert(0, "PDF generato forzatamente nonostante problemi bloccanti.")
    return result
