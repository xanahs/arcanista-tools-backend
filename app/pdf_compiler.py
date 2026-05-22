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

    # The provided Italian sheet is a static PDF without AcroForm fields. A
    # custom generated sheet is more reliable than coordinate-based overlays.
    _write_custom_character_sheet(character, output_path)

    pdf_url = f"{base_url.rstrip('/')}/files/{output_name}" if base_url else f"/files/{output_name}"

    return {
        "status": "ok",
        "pdf_url": pdf_url,
        "file_id": output_name,
        "filled_fields": _filled_fields(character),
        "unfilled_fields": character.get("notes_for_unfilled_fields", []),
        "warnings": [
            "Ho generato una scheda custom pulita perché il PDF italiano caricato non contiene campi modulo compilabili."
        ],
    }


def _filled_fields(character: dict[str, Any]) -> list[str]:
    fields = []
    for key, value in character.items():
        if value not in (None, "", [], {}):
            fields.append(key)
    return fields


def _write_custom_character_sheet(character: dict[str, Any], output_path: Path) -> None:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 36
    y = height - margin

    header = character.get("header", {})
    abilities = character.get("abilities", {})
    hp = character.get("hit_points", {})
    personality = character.get("personality", {})

    def new_page(title: str) -> None:
        nonlocal y
        c.showPage()
        y = height - margin
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, title)
        y -= 22

    def ensure(space: int) -> None:
        if y - space < margin:
            new_page("Scheda personaggio D&D 5e")

    def title(text: str) -> None:
        nonlocal y
        ensure(26)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, text)
        y -= 15
        c.line(margin, y + 5, width - margin, y + 5)

    def row(label: str, value: Any, x: int = margin, w: int = 250, line_height: int = 12) -> None:
        nonlocal y
        ensure(line_height + 4)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, y, label)
        c.setFont("Helvetica", 9)
        c.drawString(x + 88, y, str(value or "")[:80])
        y -= line_height

    def multi(label: str, values: list[str] | str, max_lines: int | None = None) -> None:
        nonlocal y
        if isinstance(values, list):
            text = "; ".join(str(v) for v in values if v)
        else:
            text = str(values or "")
        lines = _wrap(text, 95)
        if max_lines:
            lines = lines[:max_lines]
        ensure(14 + len(lines) * 11)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(margin, y, label)
        y -= 11
        c.setFont("Helvetica", 8)
        for line in lines:
            c.drawString(margin + 10, y, line)
            y -= 10

    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, str(header.get("character_name") or "Scheda personaggio"))
    c.setFont("Helvetica", 9)
    c.drawRightString(width - margin, y, "D&D 5e - Scheda custom Arcanista")
    y -= 24

    title("Intestazione")
    y_start = y
    row("Classe/Livello", header.get("class_and_level"))
    row("Background", header.get("background"))
    row("Razza/Specie", header.get("race_or_species"))
    row("Allineamento", header.get("alignment"))
    y = y_start
    row("Giocatore", header.get("player_name"), x=330)
    row("XP", header.get("experience_points"), x=330)
    row("Bonus competenza", character.get("proficiency_bonus"), x=330)
    row("Ispirazione", character.get("inspiration"), x=330)
    y -= 8

    title("Caratteristiche")
    ability_labels = [
        ("Forza", "strength"),
        ("Destrezza", "dexterity"),
        ("Costituzione", "constitution"),
        ("Intelligenza", "intelligence"),
        ("Saggezza", "wisdom"),
        ("Carisma", "charisma"),
    ]
    box_w = 86
    box_h = 48
    x = margin
    ensure(box_h + 10)
    for label, key in ability_labels:
        data = abilities.get(key, {})
        c.roundRect(x, y - box_h + 8, box_w, box_h, 4)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + box_w / 2, y - 5, label)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(x + box_w / 2, y - 25, str(data.get("modifier", "")))
        c.setFont("Helvetica", 9)
        c.drawCentredString(x + box_w / 2, y - 40, str(data.get("score", "")))
        x += box_w + 7
    y -= box_h + 10

    title("Combattimento")
    y_start = y
    row("Classe Armatura", character.get("armor_class"))
    row("Iniziativa", character.get("initiative"))
    row("Velocità", character.get("speed"))
    y = y_start
    row("PF massimi", hp.get("maximum"), x=250)
    row("PF attuali", hp.get("current"), x=250)
    row("PF temporanei", hp.get("temporary"), x=250)
    y = y_start
    row("Dadi Vita", character.get("hit_dice"), x=430)
    row("TS morte successi", hp.get("death_save_successes"), x=430)
    row("TS morte fallimenti", hp.get("death_save_failures"), x=430)
    y -= 10

    title("Tiri salvezza")
    _two_column_named_list(c, margin, y, character.get("saving_throws", []), height_limit=90)
    y -= 95

    title("Abilità")
    _three_column_named_list(c, margin, y, character.get("skills", []), height_limit=140)
    y -= 145

    title("Attacchi e incantesimi offensivi")
    _attack_table(c, margin, y, width - 2 * margin, character.get("attacks", [])[:8])
    y -= 18 + max(1, min(8, len(character.get("attacks", [])))) * 15

    title("Competenze e linguaggi")
    multi("Competenze/Linguaggi", character.get("proficiencies_and_languages", []), max_lines=7)

    title("Equipaggiamento")
    multi("Equipaggiamento", character.get("equipment", []), max_lines=10)

    title("Personalità")
    multi("Tratti", personality.get("personality_traits"), max_lines=3)
    multi("Ideali", personality.get("ideals"), max_lines=3)
    multi("Legami", personality.get("bonds"), max_lines=3)
    multi("Difetti", personality.get("flaws"), max_lines=3)

    title("Privilegi e tratti")
    multi("Privilegi", character.get("features_and_traits", []), max_lines=14)

    appearance = character.get("appearance") or {}
    if appearance:
        title("Aspetto")
        row("Età", appearance.get("age"))
        row("Altezza", appearance.get("height"))
        row("Peso", appearance.get("weight"))
        row("Occhi", appearance.get("eyes"))
        row("Pelle", appearance.get("skin"))
        row("Capelli", appearance.get("hair"))
        multi("Note aspetto", appearance.get("appearance_notes"), max_lines=5)

    title("Alleati, organizzazioni e storia")
    multi("Alleati/Organizzazioni", character.get("allies_and_organizations"), max_lines=8)
    multi("Backstory", character.get("backstory"), max_lines=18)
    multi("Tesoro", character.get("treasure"), max_lines=6)

    spellcasting = character.get("spellcasting") or {}
    if spellcasting:
        new_page("Incantesimi")
        row("Classe da incantatore", spellcasting.get("spellcasting_class"))
        row("Caratteristica", spellcasting.get("spellcasting_ability"))
        row("CD TS incantesimi", spellcasting.get("spell_save_dc"))
        row("Bonus attacco", spellcasting.get("spell_attack_bonus"))
        title("Trucchetti")
        multi("Trucchetti", spellcasting.get("cantrips", []), max_lines=6)
        for block in spellcasting.get("spells_by_level", []):
            title(f"Incantesimi livello {block.get('level')} - Slot {block.get('slots_total', '')}, spesi {block.get('slots_expended', '')}")
            multi("Incantesimi", block.get("spells", []), max_lines=10)

    notes = character.get("notes_for_unfilled_fields") or []
    if notes:
        title("Campi mancanti o da confermare")
        multi("Note", notes, max_lines=12)

    c.save()
    output_path.write_bytes(buffer.getvalue())


def _wrap(text: str, width: int) -> list[str]:
    words = text.replace("\n", " ").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _two_column_named_list(c: canvas.Canvas, x: int, y: int, rows: list[dict[str, Any]], height_limit: int) -> None:
    c.setFont("Helvetica", 8)
    col_w = 250
    row_h = 12
    for index, item in enumerate(rows[:14]):
        col = index // 7
        pos = index % 7
        xx = x + col * col_w
        yy = y - pos * row_h
        mark = "P" if item.get("proficient") else "-"
        c.drawString(xx, yy, f"{mark} {item.get('name', '')}: {item.get('bonus', '')}")


def _three_column_named_list(c: canvas.Canvas, x: int, y: int, rows: list[dict[str, Any]], height_limit: int) -> None:
    c.setFont("Helvetica", 7.5)
    col_w = 175
    row_h = 12
    per_col = 7
    for index, item in enumerate(rows[:21]):
        col = index // per_col
        pos = index % per_col
        xx = x + col * col_w
        yy = y - pos * row_h
        mark = "E" if item.get("expertise") else ("P" if item.get("proficient") else "-")
        c.drawString(xx, yy, f"{mark} {item.get('name', '')}: {item.get('bonus', '')}")


def _attack_table(c: canvas.Canvas, x: int, y: int, w: int, rows: list[dict[str, Any]]) -> None:
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y, "Nome")
    c.drawString(x + 185, y, "Bonus")
    c.drawString(x + 250, y, "Danno/Tipo")
    c.drawString(x + 390, y, "Note")
    c.line(x, y - 3, x + w, y - 3)
    c.setFont("Helvetica", 8)
    yy = y - 16
    for row in rows:
        c.drawString(x, yy, str(row.get("name", ""))[:30])
        c.drawString(x + 185, yy, str(row.get("attack_bonus", ""))[:8])
        c.drawString(x + 250, yy, str(row.get("damage_and_type", ""))[:24])
        c.drawString(x + 390, yy, str(row.get("notes", ""))[:26])
        yy -= 15


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
