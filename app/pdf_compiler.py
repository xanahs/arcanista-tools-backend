from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
TEMPLATE_DIR = ROOT / "templates"
DEFAULT_TEMPLATE = TEMPLATE_DIR / "dnd_blankcharactersheet_it.pdf"


def safe_filename(name: str | None, fallback: str = "scheda_personaggio.pdf") -> str:
    raw = name or fallback
    cleaned = re.sub(r"[^A-Za-z0-9_. -]+", "", raw).strip()
    if not cleaned:
        cleaned = fallback
    if not cleaned.lower().endswith(".pdf"):
        cleaned += ".pdf"
    return cleaned


def modifier(score: int) -> str:
    value = (score - 10) // 2
    return f"{value:+d}"


def compile_character_sheet(payload: dict[str, Any], base_url: str = "") -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    character = payload.get("character", {})
    header = character.get("header", {})
    output_name = safe_filename(payload.get("output_filename") or f"{header.get('character_name', 'scheda')}.pdf")
    output_path = OUTPUT_DIR / output_name

    if DEFAULT_TEMPLATE.exists():
        _write_overlay_on_template(character, DEFAULT_TEMPLATE, output_path)
    else:
        _write_summary_pdf(character, output_path)

    pdf_url = f"{base_url.rstrip('/')}/files/{output_name}" if base_url else f"/files/{output_name}"
    warnings = []
    if not DEFAULT_TEMPLATE.exists():
        warnings.append(
            "Template dnd_blankcharactersheet_it.pdf non trovato in arcanista_tools_backend/templates; "
            "ho generato un PDF riassuntivo invece di sovrapporre i campi alla scheda ufficiale."
        )

    return {
        "status": "ok",
        "pdf_url": pdf_url,
        "file_id": output_name,
        "filled_fields": _filled_fields(character),
        "unfilled_fields": character.get("notes_for_unfilled_fields", []),
        "warnings": warnings,
    }


def _filled_fields(character: dict[str, Any]) -> list[str]:
    fields = []
    for key, value in character.items():
        if value not in (None, "", [], {}):
            fields.append(key)
    return fields


def _write_summary_pdf(character: dict[str, Any], output_path: Path) -> None:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 48

    c.setFont("Helvetica-Bold", 16)
    c.drawString(48, y, "Scheda personaggio D&D 5e")
    y -= 28

    for line in _summary_lines(character):
        if y < 54:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 48
        if line.startswith("# "):
            c.setFont("Helvetica-Bold", 12)
            c.drawString(48, y, line[2:])
            c.setFont("Helvetica", 9)
        else:
            c.setFont("Helvetica", 9)
            c.drawString(48, y, line[:120])
        y -= 14

    c.save()
    output_path.write_bytes(buffer.getvalue())


def _summary_lines(character: dict[str, Any]) -> list[str]:
    header = character.get("header", {})
    abilities = character.get("abilities", {})
    lines = [
        "# Intestazione",
        f"Nome: {header.get('character_name', '')}",
        f"Classe e livello: {header.get('class_and_level', '')}",
        f"Background: {header.get('background', '')}",
        f"Razza/specie: {header.get('race_or_species', '')}",
        f"Allineamento: {header.get('alignment', '')}",
        "# Caratteristiche",
    ]
    for key in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
        value = abilities.get(key, {})
        lines.append(f"{key}: {value.get('score', '')} ({value.get('modifier', '')})")
    lines += [
        "# Combattimento",
        f"Bonus competenza: {character.get('proficiency_bonus', '')}",
        f"CA: {character.get('armor_class', '')}",
        f"Iniziativa: {character.get('initiative', '')}",
        f"Velocità: {character.get('speed', '')}",
        f"PF: {character.get('hit_points', {}).get('maximum', '')}",
        f"Dadi Vita: {character.get('hit_dice', '')}",
        "# Attacchi",
    ]
    for attack in character.get("attacks", []):
        lines.append(f"{attack.get('name', '')}: {attack.get('attack_bonus', '')}, {attack.get('damage_and_type', '')}")
    lines += ["# Equipaggiamento"]
    lines.extend(character.get("equipment", []))
    lines += ["# Personalità"]
    personality = character.get("personality", {})
    lines.append(f"Tratti: {personality.get('personality_traits', '')}")
    lines.append(f"Ideali: {personality.get('ideals', '')}")
    lines.append(f"Legami: {personality.get('bonds', '')}")
    lines.append(f"Difetti: {personality.get('flaws', '')}")
    lines += ["# Privilegi e tratti"]
    lines.extend(character.get("features_and_traits", []))
    lines += ["# Backstory", character.get("backstory", "")]
    spellcasting = character.get("spellcasting") or {}
    if spellcasting:
        lines += [
            "# Incantesimi",
            f"Classe: {spellcasting.get('spellcasting_class', '')}",
            f"Caratteristica: {spellcasting.get('spellcasting_ability', '')}",
            f"CD: {spellcasting.get('spell_save_dc', '')}",
            f"Bonus attacco: {spellcasting.get('spell_attack_bonus', '')}",
            "Trucchetti: " + ", ".join(spellcasting.get("cantrips", [])),
        ]
        for block in spellcasting.get("spells_by_level", []):
            lines.append(f"Livello {block.get('level')}: {', '.join(block.get('spells', []))}")
    return [line for line in lines if line is not None]


def _write_overlay_on_template(character: dict[str, Any], template_path: Path, output_path: Path) -> None:
    reader = PdfReader(str(template_path))
    writer = PdfWriter()

    first_page_overlay = _make_first_page_overlay(character)
    overlay_reader = PdfReader(first_page_overlay)

    for index, page in enumerate(reader.pages):
        if index == 0:
            page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    with output_path.open("wb") as handle:
        writer.write(handle)


def _make_first_page_overlay(character: dict[str, Any]) -> io.BytesIO:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica", 8)

    header = character.get("header", {})
    abilities = character.get("abilities", {})
    hp = character.get("hit_points", {})

    # These coordinates are intentionally conservative. They provide a useful
    # first-pass overlay; exact alignment can be refined after visual testing.
    c.drawString(70, 745, str(header.get("character_name", ""))[:32])
    c.drawString(260, 745, str(header.get("class_and_level", ""))[:32])
    c.drawString(400, 745, str(header.get("background", ""))[:24])
    c.drawString(260, 715, str(header.get("race_or_species", ""))[:24])
    c.drawString(400, 715, str(header.get("alignment", ""))[:20])

    ability_positions = {
        "strength": (42, 635),
        "dexterity": (42, 535),
        "constitution": (42, 438),
        "intelligence": (42, 340),
        "wisdom": (42, 242),
        "charisma": (42, 145),
    }
    for ability, (x, y) in ability_positions.items():
        value = abilities.get(ability, {})
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x + 24, y, str(value.get("modifier", "")))
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + 24, y - 20, str(value.get("score", "")))

    c.setFont("Helvetica", 9)
    c.drawString(305, 670, str(character.get("armor_class", "")))
    c.drawString(365, 670, str(character.get("initiative", "")))
    c.drawString(430, 670, str(character.get("speed", "")))
    c.drawString(345, 585, str(hp.get("maximum", "")))
    c.drawString(345, 545, str(hp.get("current", "")))
    c.drawString(345, 505, str(hp.get("temporary", "")))
    c.drawString(325, 455, str(character.get("hit_dice", ""))[:20])

    y = 640
    for attack in character.get("attacks", [])[:3]:
        c.drawString(320, y, str(attack.get("name", ""))[:18])
        c.drawString(430, y, str(attack.get("attack_bonus", ""))[:8])
        c.drawString(475, y, str(attack.get("damage_and_type", ""))[:20])
        y -= 18

    y = 330
    for item in character.get("equipment", [])[:12]:
        c.drawString(310, y, str(item)[:45])
        y -= 11

    c.save()
    buffer.seek(0)
    return buffer
