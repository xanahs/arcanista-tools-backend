from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .encounter import build_encounter_response
from .pdf_compiler import OUTPUT_DIR, compile_character_sheet


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
    return compile_character_sheet(payload, base_url=base_url)


@app.post("/encounters/build-or-balance-5e-2014")
def build_or_balance_5e_2014_encounter(
    payload: dict[str, Any],
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    return build_encounter_response(payload)
