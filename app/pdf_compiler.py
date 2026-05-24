from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
TEMPLATE_DIR = ROOT / "templates"
DEFAULT_TEMPLATE = TEMPLATE_DIR / "dnd_blankcharactersheet_it.pdf"

PAGE_W, PAGE_H = letter
MARGIN = 24
INK = colors.HexColor("#1F1F1F")
MID = colors.HexColor("#5A5A5A")
LIGHT = colors.HexColor("#D8D8D8")
VERY_LIGHT = colors.HexColor("#F4F4F1")

ABILITY_DEFS = [
    ("Forza", "strength", "FOR", ["forza", "strength", "str", "for"]),
    ("Destrezza", "dexterity", "DES", ["destrezza", "dexterity", "dex", "des"]),
    ("Costituzione", "constitution", "COS", ["costituzione", "constitution", "con", "cos"]),
    ("Intelligenza", "intelligence", "INT", ["intelligenza", "intelligence", "int"]),
    ("Saggezza", "wisdom", "SAG", ["saggezza", "wisdom", "wis", "sag"]),
    ("Carisma", "charisma", "CAR", ["carisma", "charisma", "cha", "car"]),
]

SKILL_DEFS = [
    ("Acrobazia", "acrobatics", "dexterity", "DES", ["acrobazia", "acrobatics"]),
    ("Addestrare Animali", "animal_handling", "wisdom", "SAG", ["addestrare animali", "animal handling"]),
    ("Arcano", "arcana", "intelligence", "INT", ["arcano", "arcana"]),
    ("Atletica", "athletics", "strength", "FOR", ["atletica", "athletics"]),
    ("Inganno", "deception", "charisma", "CAR", ["inganno", "deception"]),
    ("Storia", "history", "intelligence", "INT", ["storia", "history"]),
    ("Intuizione", "insight", "wisdom", "SAG", ["intuizione", "insight"]),
    ("Intimidire", "intimidation", "charisma", "CAR", ["intimidire", "intimidation"]),
    ("Indagare", "investigation", "intelligence", "INT", ["indagare", "investigation"]),
    ("Medicina", "medicine", "wisdom", "SAG", ["medicina", "medicine"]),
    ("Natura", "nature", "intelligence", "INT", ["natura", "nature"]),
    ("Percezione", "perception", "wisdom", "SAG", ["percezione", "perception"]),
    ("Intrattenere", "performance", "charisma", "CAR", ["intrattenere", "performance"]),
    ("Persuasione", "persuasion", "charisma", "CAR", ["persuasione", "persuasion"]),
    ("Religione", "religion", "intelligence", "INT", ["religione", "religion"]),
    ("Rapidita di Mano", "sleight_of_hand", "dexterity", "DES", ["rapidita di mano", "sleight of hand"]),
    ("Furtivita", "stealth", "dexterity", "DES", ["furtivita", "stealth"]),
    ("Sopravvivenza", "survival", "wisdom", "SAG", ["sopravvivenza", "survival"]),
]


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

    layout_warnings = _write_custom_character_sheet(character, output_path)

    pdf_url = f"{base_url.rstrip('/')}/files/{output_name}" if base_url else f"/files/{output_name}"

    return {
        "status": "ok",
        "pdf_url": pdf_url,
        "file_id": output_name,
        "filled_fields": _filled_fields(character),
        "unfilled_fields": character.get("notes_for_unfilled_fields", []),
        "warnings": [
            "Scheda custom Arcanista generata con riquadri scrivibili, spazi liberi e impaginazione fissa.",
            *layout_warnings,
        ],
    }


def _filled_fields(character: dict[str, Any]) -> list[str]:
    fields = []
    for key, value in character.items():
        if value not in (None, "", [], {}):
            fields.append(key)
    return fields


def _write_custom_character_sheet(character: dict[str, Any], output_path: Path) -> list[str]:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setTitle(_text(character.get("header", {}).get("character_name") or "Scheda personaggio"))

    _draw_page_one(c, character)
    c.showPage()
    overflow = _draw_page_two(c, character)
    continuation_warnings = _draw_continuation_pages(c, character, overflow)
    c.showPage()
    _draw_spell_page(c, character)

    c.save()
    output_path.write_bytes(buffer.getvalue())
    return continuation_warnings


def _draw_page_one(c: canvas.Canvas, character: dict[str, Any]) -> None:
    header = character.get("header", {})
    abilities = character.get("abilities", {})
    hp = character.get("hit_points", {})

    _page_label(c, "Scheda personaggio", "Meccanica e combattimento")
    _draw_header(c, character)

    upper_y = 176
    upper_h = 520
    equip_y = 24
    equip_h = 140
    gap = 10
    left_x = MARGIN
    left_w = 144
    mid_x = left_x + left_w + gap
    mid_w = 210
    right_x = mid_x + mid_w + gap
    right_w = PAGE_W - MARGIN - right_x

    _draw_abilities(c, left_x, upper_y + 160, left_w, 360, abilities)
    _draw_saving_throws(c, left_x, upper_y, left_w, 150, character)
    _draw_skills(c, mid_x, upper_y + 125, mid_w, 395, character)
    _draw_text_area(
        c,
        "Competenze e linguaggi",
        character.get("proficiencies_and_languages", []),
        mid_x,
        upper_y,
        mid_w,
        115,
        line_count=8,
    )
    _draw_combat(c, right_x, upper_y + 290, right_w, 230, character, hp)
    _draw_attacks(c, right_x, upper_y, right_w, 280, character.get("attacks", []))
    _draw_text_area(
        c,
        "Equipaggiamento",
        character.get("equipment", []),
        MARGIN,
        equip_y,
        PAGE_W - MARGIN * 2,
        equip_h,
        line_count=9,
    )


def _draw_page_two(c: canvas.Canvas, character: dict[str, Any]) -> dict[str, list[str]]:
    personality = character.get("personality", {})
    appearance = character.get("appearance") or {}
    overflow: dict[str, list[str]] = {}

    _page_label(c, "Personalita e storia", "Spazio ampio per interpretazione, note e sviluppo")
    _small_identity_bar(c, character)

    top_y = 596
    box_w = (PAGE_W - MARGIN * 2 - 18) / 4
    for index, (label, key) in enumerate(
        [
            ("Tratti", "personality_traits"),
            ("Ideali", "ideals"),
            ("Legami", "bonds"),
            ("Difetti", "flaws"),
        ]
    ):
        x = MARGIN + index * (box_w + 6)
        _draw_text_area(c, label, personality.get(key), x, top_y, box_w, 118, line_count=6)

    usable_w = PAGE_W - MARGIN * 2
    main_gap = 10
    right_w = 136
    left_w = usable_w - right_w - main_gap
    backstory_x = MARGIN
    right_x = MARGIN + left_w + main_gap
    top_content = 584
    bottom_y = 24
    backstory_y = 316
    lower_y = 176
    lower_h = 128
    lower_gap = 8
    lower_w = (left_w - lower_gap) / 2
    backpack_h = 140

    overflow["Backstory"] = _draw_text_area(
        c,
        "Backstory",
        character.get("backstory"),
        backstory_x,
        backstory_y,
        left_w,
        top_content - backstory_y,
        line_count=17,
    )
    overflow["Privilegi, tratti e capacita speciali"] = _draw_feature_area(
        c,
        "Privilegi, tratti e capacita speciali",
        character.get("features_and_traits", []),
        right_x,
        bottom_y,
        right_w,
        top_content - bottom_y,
        line_count=43,
    )

    appearance_text = _appearance_text(appearance)
    overflow["Aspetto"] = _draw_text_area(c, "Aspetto", appearance_text, backstory_x, lower_y, lower_w, lower_h, line_count=7)
    overflow["Alleati e organizzazioni"] = _draw_text_area(
        c,
        "Alleati e organizzazioni",
        character.get("allies_and_organizations"),
        backstory_x + lower_w + lower_gap,
        lower_y,
        lower_w,
        lower_h,
        line_count=7,
    )
    overflow["Tesoro / zaino"] = _draw_text_area(
        c,
        "Tesoro / zaino",
        character.get("treasure") or character.get("backpack") or character.get("zaino"),
        backstory_x,
        bottom_y,
        left_w,
        backpack_h,
        line_count=9,
    )
    return {key: value for key, value in overflow.items() if value}


def _draw_continuation_pages(c: canvas.Canvas, character: dict[str, Any], overflow: dict[str, list[str]]) -> list[str]:
    warnings: list[str] = []
    sections = [(label, lines) for label, lines in overflow.items() if lines]
    if not sections:
        return warnings

    for label, lines in sections:
        warnings.append(f"Il contenuto di '{label}' continua in una pagina extra per non tagliare il testo.")
        chunks = _chunks(lines, 46)
        for index, chunk in enumerate(chunks, start=1):
            c.showPage()
            _page_label(c, f"Continuazione - {label}", f"Pagina extra {index}")
            _small_identity_bar(c, character)
            _draw_lines_area(c, label, chunk, MARGIN, 40, PAGE_W - MARGIN * 2, 660, line_count=46)
    return warnings


def _draw_spell_page(c: canvas.Canvas, character: dict[str, Any]) -> None:
    spellcasting = character.get("spellcasting") or {}
    _page_label(c, "Incantesimi", "Lista aggiornabile e spazi per slot")
    _small_identity_bar(c, character)

    stats_y = 676
    stat_w = (PAGE_W - MARGIN * 2 - 30) / 4
    _draw_field(c, "Classe da incantatore", spellcasting.get("spellcasting_class"), MARGIN, stats_y, stat_w, 42)
    _draw_field(c, "Caratteristica", spellcasting.get("spellcasting_ability"), MARGIN + stat_w + 10, stats_y, stat_w, 42)
    _draw_field(c, "CD TS incantesimi", spellcasting.get("spell_save_dc"), MARGIN + (stat_w + 10) * 2, stats_y, stat_w, 42)
    _draw_field(c, "Bonus attacco", spellcasting.get("spell_attack_bonus"), MARGIN + (stat_w + 10) * 3, stats_y, stat_w, 42)

    spells_by_level = _spell_blocks(spellcasting)
    titles = [("Trucchetti", 0)] + [(f"Livello {level}", level) for level in range(1, 10)]
    grid_x = MARGIN
    grid_y = 24
    col_w = (PAGE_W - MARGIN * 2 - 10) / 2
    row_h = 122
    gap = 8

    for index, (title, level) in enumerate(titles):
        col = index % 2
        row = 4 - index // 2
        x = grid_x + col * (col_w + 10)
        y = grid_y + row * (row_h + gap)
        data = spells_by_level.get(level, {})
        spells = spellcasting.get("cantrips", []) if level == 0 else data.get("spells", [])
        slots_total = "" if level == 0 else data.get("slots_total", "")
        _draw_spell_block(c, title, spells, slots_total, x, y, col_w, row_h, level)


def _draw_header(c: canvas.Canvas, character: dict[str, Any]) -> None:
    header = character.get("header", {})
    y = 704
    name_w = 160
    _draw_field(c, "Nome personaggio", header.get("character_name"), MARGIN, y, name_w, 52, value_size=12)

    x = MARGIN + name_w + 8
    w = PAGE_W - MARGIN - x
    gap = 6
    col_w = (w - gap * 2) / 3
    _draw_field(c, "Classe e livello", header.get("class_and_level"), x, y + 27, col_w, 25)
    _draw_field(c, "Background", header.get("background"), x + col_w + gap, y + 27, col_w, 25)
    _draw_field(c, "Giocatore", header.get("player_name"), x + (col_w + gap) * 2, y + 27, col_w, 25)
    _draw_field(c, "Razza/specie", header.get("race_or_species"), x, y, col_w, 25)
    _draw_field(c, "Allineamento", header.get("alignment"), x + col_w + gap, y, col_w, 25)
    _draw_field(c, "XP", header.get("experience_points"), x + (col_w + gap) * 2, y, col_w, 25)


def _small_identity_bar(c: canvas.Canvas, character: dict[str, Any]) -> None:
    header = character.get("header", {})
    name = header.get("character_name") or "Personaggio"
    details = header.get("class_and_level") or ""
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.7)
    c.line(MARGIN, 728, PAGE_W - MARGIN, 728)
    c.setFillColor(MID)
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN, 734, _text(name))
    c.drawRightString(PAGE_W - MARGIN, 734, _text(details))


def _page_label(c: canvas.Canvas, title: str, subtitle: str) -> None:
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, 766, _text(title))
    c.setFont("Helvetica", 8)
    c.setFillColor(MID)
    c.drawRightString(PAGE_W - MARGIN, 766, _text(subtitle))


def _draw_section(c: canvas.Canvas, title: str, x: float, y: float, w: float, h: float) -> None:
    c.setLineWidth(0.9)
    c.setStrokeColor(INK)
    c.setFillColor(colors.white)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=0)
    c.setFillColor(VERY_LIGHT)
    c.roundRect(x + 1, y + h - 18, w - 2, 17, 4, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(x + 7, y + h - 12, _text(title).upper())


def _draw_field(
    c: canvas.Canvas,
    label: str,
    value: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    value_size: float = 8,
    center: bool = False,
    middle_value: bool = False,
) -> None:
    c.setStrokeColor(INK)
    c.setLineWidth(0.75)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=0)
    c.setFillColor(MID)
    c.setFont("Helvetica-Bold", 5.8)
    c.drawString(x + 5, y + h - 8, _text(label).upper())

    text = _format_value(value)
    if not text:
        return

    c.setFillColor(INK)
    c.setFont("Helvetica", value_size)
    lines = _wrap(text, max(8, int(w / max(value_size * 0.48, 4))))
    max_lines = max(1, int((h - 13) / (value_size + 2)))
    start_y = y + (h - value_size) / 2 - 1 if middle_value else y + h - 18
    for line in lines[:max_lines]:
        if center:
            c.drawCentredString(x + w / 2, start_y, _text(line))
        else:
            c.drawString(x + 5, start_y, _text(line))
        start_y -= value_size + 2


def _draw_text_area(
    c: canvas.Canvas,
    label: str,
    value: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    line_count: int,
) -> list[str]:
    _draw_section(c, label, x, y, w, h)
    content_top = y + h - 27
    content_bottom = y + 10
    line_gap = (content_top - content_bottom) / max(1, line_count - 1)
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.35)
    for idx in range(line_count):
        yy = content_top - idx * line_gap
        c.line(x + 8, yy - 3, x + w - 8, yy - 3)

    text = _format_value(value)
    if not text:
        return []

    c.setFillColor(INK)
    c.setFont("Helvetica", 7.2)
    max_chars = max(16, int(w / 3.75))
    lines = _wrap(text, max_chars)
    visible, overflow = _visible_and_overflow(lines, line_count)
    yy = content_top - 1
    for line in visible:
        c.drawString(x + 9, yy, _text(line))
        yy -= line_gap
    return overflow


def _draw_feature_area(
    c: canvas.Canvas,
    label: str,
    features: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    line_count: int,
) -> list[str]:
    _draw_section(c, label, x, y, w, h)
    content_top = y + h - 27
    content_bottom = y + 10
    line_gap = (content_top - content_bottom) / max(1, line_count - 1)
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.35)
    for idx in range(line_count):
        yy = content_top - idx * line_gap
        c.line(x + 8, yy - 3, x + w - 8, yy - 3)

    lines = _feature_lines(features, max_chars=max(18, int(w / 3.55)))
    visible, overflow = _visible_and_overflow(lines, line_count)
    c.setFillColor(INK)
    yy = content_top - 1
    for line in visible:
        is_heading = line.startswith("- ")
        c.setFont("Helvetica-Bold" if is_heading else "Helvetica", 6.8)
        c.drawString(x + 9, yy, _text(line))
        yy -= line_gap
    return overflow


def _draw_lines_area(
    c: canvas.Canvas,
    label: str,
    lines: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    line_count: int,
) -> None:
    _draw_section(c, label, x, y, w, h)
    content_top = y + h - 28
    content_bottom = y + 12
    line_gap = (content_top - content_bottom) / max(1, line_count - 1)
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.35)
    for idx in range(line_count):
        yy = content_top - idx * line_gap
        c.line(x + 8, yy - 3, x + w - 8, yy - 3)
    c.setFillColor(INK)
    c.setFont("Helvetica", 7.1)
    yy = content_top - 1
    max_chars = max(24, int(w / 3.65))
    draw_lines: list[str] = []
    for line in lines:
        draw_lines.extend(_wrap(line, max_chars))
    for line in draw_lines[:line_count]:
        c.drawString(x + 9, yy, _text(line))
        yy -= line_gap


def _draw_abilities(c: canvas.Canvas, x: float, y: float, w: float, h: float, abilities: dict[str, Any]) -> None:
    _draw_section(c, "Caratteristiche", x, y, w, h)
    row_h = (h - 25) / 6
    for index, (label, key, short, aliases) in enumerate(ABILITY_DEFS):
        data = _ability_data(abilities, key, aliases)
        score = data.get("score") or data.get("value") or ""
        mod = data.get("modifier") or _modifier_from_score(score)
        yy = y + h - 22 - (index + 1) * row_h
        cell_x = x + 10
        cell_y = yy + 5
        cell_w = w - 20
        cell_h = row_h - 8
        c.setStrokeColor(INK)
        c.setLineWidth(0.7)
        c.roundRect(cell_x, cell_y, cell_w, cell_h, 6, stroke=1, fill=0)

        title_h = 13
        title_x = cell_x + 10
        title_y = cell_y + cell_h - title_h - 4
        c.setFillColor(VERY_LIGHT)
        c.roundRect(title_x, title_y, cell_w - 20, title_h, 4, stroke=0, fill=1)
        c.setFillColor(MID)
        c.setFont("Helvetica-Bold", 6.4)
        c.drawCentredString(x + w / 2, title_y + 4, _text(label).upper())

        mod_w = 40
        mod_h = 18
        mod_x = cell_x + 18
        mod_y = cell_y + 6
        c.setStrokeColor(INK)
        c.setLineWidth(0.65)
        c.roundRect(mod_x, mod_y, mod_w, mod_h, 4, stroke=1, fill=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(mod_x + mod_w / 2, mod_y + 4.5, _text(mod))

        score_x = cell_x + cell_w - 29
        score_y = cell_y + 15
        c.setStrokeColor(INK)
        c.circle(score_x, score_y, 9, stroke=1, fill=0)
        c.setFont("Helvetica", 7)
        c.drawCentredString(score_x, score_y - 2.4, _text(score))


def _draw_saving_throws(c: canvas.Canvas, x: float, y: float, w: float, h: float, character: dict[str, Any]) -> None:
    _draw_section(c, "Tiri salvezza", x, y, w, h)
    rows = character.get("saving_throws", [])
    abilities = character.get("abilities", {})
    prof = _parse_int(character.get("proficiency_bonus"))
    row_h = 20
    start_y = y + h - 35
    for index, (label, key, short, aliases) in enumerate(ABILITY_DEFS):
        row = _find_row(rows, [key, short, *aliases])
        bonus = _row_bonus(row, abilities, key, prof)
        proficient = _row_proficient(row)
        yy = start_y - index * row_h
        _marker(c, x + 11, yy + 3, proficient)
        _tiny_bonus_box(c, x + 24, yy - 3, 26, 14, bonus)
        c.setFont("Helvetica", 7.4)
        c.setFillColor(INK)
        c.drawString(x + 56, yy + 1, _text(label))


def _draw_skills(c: canvas.Canvas, x: float, y: float, w: float, h: float, character: dict[str, Any]) -> None:
    _draw_section(c, "Abilita", x, y, w, h)
    rows = character.get("skills", [])
    abilities = character.get("abilities", {})
    prof = _parse_int(character.get("proficiency_bonus"))
    row_h = 18.5
    start_y = y + h - 33
    for index, (label, key, ability_key, ability_short, aliases) in enumerate(SKILL_DEFS):
        row = _find_row(rows, [key, label, *aliases])
        bonus = _row_bonus(row, abilities, ability_key, prof)
        proficient = _row_proficient(row)
        expertise = _truthy(row.get("expertise")) if row else False
        yy = start_y - index * row_h
        _marker(c, x + 11, yy + 3, proficient, expertise=expertise)
        _tiny_bonus_box(c, x + 25, yy - 3, 26, 14, bonus)
        c.setFont("Helvetica", 7.2)
        c.setFillColor(INK)
        c.drawString(x + 57, yy + 1, _text(f"{label} ({ability_short})"))

    passive = character.get("passive_perception") or _passive_perception(character)
    _draw_passive_perception(c, passive, x + 8, y + 15, w - 16, 18)


def _draw_combat(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    character: dict[str, Any],
    hp: dict[str, Any],
) -> None:
    _draw_section(c, "Combattimento", x, y, w, h)
    gap = 5
    stat_w = (w - 16 - gap * 2) / 3
    stat_y = y + h - 63
    _draw_field(c, "CA", character.get("armor_class"), x + 8, stat_y, stat_w, 36, value_size=13, center=True, middle_value=True)
    _draw_field(c, "Iniziativa", character.get("initiative"), x + 8 + stat_w + gap, stat_y, stat_w, 36, value_size=13, center=True, middle_value=True)
    _draw_field(c, "Velocita", character.get("speed"), x + 8 + (stat_w + gap) * 2, stat_y, stat_w, 36, value_size=10, center=True, middle_value=True)

    secondary_y = stat_y - 32
    _draw_field(c, "Bonus comp.", character.get("proficiency_bonus"), x + 8, secondary_y, stat_w, 24, center=True, middle_value=True)
    _draw_field(c, "Ispirazione", character.get("inspiration"), x + 8 + stat_w + gap, secondary_y, stat_w, 24, center=True, middle_value=True)
    _draw_field(c, "Dadi vita", character.get("hit_dice"), x + 8 + (stat_w + gap) * 2, secondary_y, stat_w, 24, center=True, middle_value=True)

    pf_max_y = secondary_y - 30
    _draw_field(c, "PF massimi", hp.get("maximum"), x + 8, pf_max_y, w - 16, 22, center=True, middle_value=True)
    hp_y = pf_max_y - 52
    _draw_field(c, "PF attuali", "", x + 8, hp_y, (w - 21) / 2, 44, value_size=13, center=True, middle_value=True)
    _draw_field(c, "PF temporanei", "", x + 13 + (w - 21) / 2, hp_y, (w - 21) / 2, 44, value_size=13, center=True, middle_value=True)

    _draw_death_saves(c, x + 8, y + 10, w - 16, 32)


def _draw_attacks(c: canvas.Canvas, x: float, y: float, w: float, h: float, attacks: list[dict[str, Any]]) -> None:
    _draw_section(c, "Attacchi e incantesimi offensivi", x, y, w, h)
    top = y + h - 31
    name_w = w * 0.42
    bonus_w = w * 0.17
    damage_w = w - 16 - name_w - bonus_w
    row_h = 23
    c.setFillColor(MID)
    c.setFont("Helvetica-Bold", 5.8)
    c.drawString(x + 8, top + 1, "NOME")
    c.drawString(x + 10 + name_w, top + 1, "BONUS")
    c.drawString(x + 12 + name_w + bonus_w, top + 1, "DANNO/TIPO")

    for index in range(5):
        attack = attacks[index] if index < len(attacks) else {}
        yy = top - (index + 1) * row_h
        _draw_plain_cell(c, x + 8, yy, name_w, 18, attack.get("name"))
        _draw_plain_cell(c, x + 10 + name_w, yy, bonus_w, 18, attack.get("attack_bonus"), center=True)
        _draw_plain_cell(c, x + 12 + name_w + bonus_w, yy, damage_w, 18, attack.get("damage_and_type"))

    notes = []
    for attack in attacks[:5]:
        if attack.get("notes"):
            notes.append(f"{attack.get('name', 'Attacco')}: {attack.get('notes')}")
    _draw_text_area(c, "Note attacchi / descrizione", notes, x + 8, y + 10, w - 16, 116, line_count=7)


def _draw_spell_block(
    c: canvas.Canvas,
    title: str,
    spells: Any,
    slots_total: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    level: int,
) -> None:
    _draw_section(c, title, x, y, w, h)
    if level > 0:
        c.setFont("Helvetica", 6.2)
        c.setFillColor(MID)
        slot_count = 6
        slot_size = 6
        slot_gap = 4
        slots_w = slot_count * slot_size + max(0, slot_count - 1) * slot_gap
        start_x = x + w - 10 - slots_w
        c.drawRightString(start_x - 5, y + h - 12, "SLOT")
        for idx in range(slot_count):
            c.rect(start_x + idx * (slot_size + slot_gap), y + h - 14, slot_size, slot_size, stroke=1, fill=0)

    lines = _as_lines(spells)
    content_top = y + h - 30
    content_bottom = y + 9
    line_count = 7
    line_gap = (content_top - content_bottom) / max(1, line_count - 1)
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.35)
    for idx in range(line_count):
        yy = content_top - idx * line_gap
        c.line(x + 8, yy - 3, x + w - 8, yy - 3)
    c.setFillColor(INK)
    c.setFont("Helvetica", 7)
    yy = content_top
    for line in lines[:line_count]:
        c.drawString(x + 9, yy, _text(line))
        yy -= line_gap


def _draw_plain_cell(c: canvas.Canvas, x: float, y: float, w: float, h: float, value: Any, *, center: bool = False) -> None:
    c.setStrokeColor(INK)
    c.setLineWidth(0.55)
    c.rect(x, y, w, h, stroke=1, fill=0)
    text = _format_value(value)
    if text:
        c.setFillColor(INK)
        c.setFont("Helvetica", 6.8)
        if center:
            c.drawCentredString(x + w / 2, y + 5.5, _text(text[:14]))
        else:
            c.drawString(x + 3, y + 5.5, _text(text[: int(w / 3.9)]))


def _tiny_bonus_box(c: canvas.Canvas, x: float, y: float, w: float, h: float, value: Any) -> None:
    c.setStrokeColor(INK)
    c.setLineWidth(0.55)
    c.roundRect(x, y, w, h, 3, stroke=1, fill=0)
    if value not in (None, ""):
        c.setFillColor(INK)
        c.setFont("Helvetica", 7)
        c.drawCentredString(x + w / 2, y + 4, _text(value))


def _draw_passive_perception(c: canvas.Canvas, value: Any, x: float, y: float, w: float, h: float) -> None:
    c.setStrokeColor(INK)
    c.setLineWidth(0.55)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=0)
    c.setFillColor(MID)
    c.setFont("Helvetica-Bold", 5.8)
    c.drawString(x + 6, y + 6, "PERCEZIONE PASSIVA")

    value_w = 24
    c.setStrokeColor(INK)
    c.roundRect(x + w - value_w - 5, y + 3, value_w, h - 6, 4, stroke=1, fill=0)
    if value not in (None, ""):
        c.setFillColor(INK)
        c.setFont("Helvetica", 7.2)
        c.drawCentredString(x + w - value_w / 2 - 5, y + 6, _text(value))


def _draw_death_saves(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    c.setStrokeColor(INK)
    c.setLineWidth(0.55)
    c.roundRect(x, y, w, h, 4, stroke=1, fill=0)
    c.setFillColor(MID)
    c.setFont("Helvetica-Bold", 5.8)
    c.drawCentredString(x + w / 2, y + h - 8, "TIRI SALVEZZA MORTE")
    mid_x = x + w / 2
    c.setStrokeColor(LIGHT)
    c.line(mid_x, y + 5, mid_x, y + h - 13)
    c.setFillColor(INK)
    c.setFont("Helvetica", 6.2)
    c.drawString(x + 8, y + 9, "Successi")
    c.drawString(mid_x + 8, y + 9, "Fallimenti")
    _three_empty_circles(c, x + 51, y + 11)
    _three_empty_circles(c, mid_x + 57, y + 11)


def _marker(c: canvas.Canvas, x: float, y: float, filled: bool, *, expertise: bool = False) -> None:
    c.setStrokeColor(INK)
    c.setLineWidth(0.7)
    c.circle(x, y, 4, stroke=1, fill=0)
    if filled:
        c.setFillColor(INK)
        c.circle(x, y, 2.6, stroke=0, fill=1)
    if expertise:
        c.circle(x, y, 5.4, stroke=1, fill=0)


def _three_empty_circles(c: canvas.Canvas, x: float, y: float) -> None:
    c.setStrokeColor(INK)
    c.setLineWidth(0.7)
    for idx in range(3):
        c.circle(x + idx * 12, y, 4, stroke=1, fill=0)


def _wrap(text: str, width: int) -> list[str]:
    width = max(4, width)
    raw_words = _text(text).replace("\n", " ").split()
    words: list[str] = []
    for raw_word in raw_words:
        if len(raw_word) <= width:
            words.append(raw_word)
            continue
        start = 0
        while start < len(raw_word):
            words.append(raw_word[start : start + width])
            start += width
    if not words:
        return []
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


def _visible_and_overflow(lines: list[str], line_count: int) -> tuple[list[str], list[str]]:
    if len(lines) <= line_count:
        return lines, []
    if line_count <= 1:
        return ["[continua...]"], lines
    visible = lines[: line_count - 1] + ["[continua nella pagina extra...]"]
    return visible, lines[line_count - 1 :]


def _chunks(lines: list[str], size: int) -> list[list[str]]:
    return [lines[index : index + size] for index in range(0, len(lines), size)]


def _format_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, list):
        return "; ".join(_format_value(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if item not in (None, "", [], {}):
                parts.append(f"{key}: {_format_value(item)}")
        return "; ".join(parts)
    return _text(str(value))


def _as_lines(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [_format_value(item) for item in value if item not in (None, "")]
    return _wrap(_format_value(value), 35)


def _feature_lines(features: Any, max_chars: int) -> list[str]:
    items = features if isinstance(features, list) else [features]
    lines: list[str] = []
    for item in items:
        text = _feature_text(item)
        if not text:
            continue
        wrapped = _wrap(text, max_chars)
        for index, line in enumerate(wrapped):
            if index == 0:
                lines.append(f"- {line}")
            else:
                lines.append(f"  {line}")
    return lines


def _feature_text(item: Any) -> str:
    if item in (None, "", [], {}):
        return ""
    if not isinstance(item, dict):
        return _format_value(item)

    name = item.get("name") or item.get("title") or item.get("feature") or "Privilegio"
    source = item.get("source") or item.get("category") or item.get("type")
    action_cost = item.get("action_cost") or item.get("action") or item.get("activation")
    uses = item.get("uses") or item.get("uses_or_limits") or item.get("recharge")
    summary = item.get("summary") or item.get("description") or item.get("effect") or item.get("what_it_does")
    mechanics = item.get("mechanics") or item.get("rules") or item.get("numbers") or item.get("mechanical_notes")
    scaling = item.get("scaling") or item.get("higher_level_scaling") or item.get("future_scaling")
    notes = item.get("notes")

    title_bits = [str(name)]
    detail_bits = []
    if source:
        detail_bits.append(str(source))
    if action_cost:
        detail_bits.append(str(action_cost))
    if uses:
        detail_bits.append(str(uses))
    if detail_bits:
        title_bits.append(f"({', '.join(detail_bits)})")

    body_bits = []
    if summary:
        body_bits.append(str(summary))
    if mechanics:
        body_bits.append(f"Numeri: {mechanics}")
    if scaling and _truthy(item.get("include_scaling") or item.get("include_higher_level_scaling")):
        body_bits.append(f"Scala: {scaling}")
    if notes:
        body_bits.append(str(notes))

    if body_bits:
        return f"{' '.join(title_bits)}: {' '.join(body_bits)}"
    return " ".join(title_bits)


def _appearance_text(appearance: dict[str, Any]) -> str:
    if not appearance:
        return ""
    labels = [
        ("Eta", "age"),
        ("Altezza", "height"),
        ("Peso", "weight"),
        ("Occhi", "eyes"),
        ("Pelle", "skin"),
        ("Capelli", "hair"),
        ("Note", "appearance_notes"),
    ]
    parts = []
    for label, key in labels:
        if appearance.get(key):
            parts.append(f"{label}: {appearance.get(key)}")
    return "; ".join(parts)


def _ability_data(abilities: dict[str, Any], key: str, aliases: list[str]) -> dict[str, Any]:
    for _, ability_key, _, ability_aliases in ABILITY_DEFS:
        if ability_key == key:
            aliases = list({*aliases, *ability_aliases})
            break
    if isinstance(abilities.get(key), dict):
        return abilities.get(key, {})
    for candidate, value in abilities.items():
        if _norm(candidate) in {_norm(alias) for alias in aliases} and isinstance(value, dict):
            return value
    return {}


def _find_row(rows: Any, names: list[str]) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    accepted = {_norm(name) for name in names}
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidates = [
            row.get("key"),
            row.get("id"),
            row.get("name"),
            row.get("label"),
            row.get("ability"),
        ]
        if any(_norm(candidate) in accepted for candidate in candidates if candidate):
            return row
    return None


def _row_bonus(row: dict[str, Any] | None, abilities: dict[str, Any], ability_key: str, proficiency_bonus: int | None) -> str:
    if row:
        for key in ("bonus", "modifier", "value"):
            if row.get(key) not in (None, ""):
                return _signed(row.get(key))

    ability = _ability_data(abilities, ability_key, [ability_key])
    base = _parse_int(ability.get("modifier") or _modifier_from_score(ability.get("score")))
    if base is None:
        return ""
    total = base
    if row and proficiency_bonus is not None:
        if _truthy(row.get("expertise")):
            total += proficiency_bonus * 2
        elif _row_proficient(row):
            total += proficiency_bonus
    return f"{total:+d}"


def _row_proficient(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    for key in (
        "proficient",
        "is_proficient",
        "competent",
        "proficiency",
        "has_proficiency",
        "trained",
        "is_trained",
    ):
        if key in row and _truthy(row.get(key)):
            return True
    return False


def _passive_perception(character: dict[str, Any]) -> str:
    row = _find_row(character.get("skills", []), ["perception", "percezione"])
    bonus = _row_bonus(row, character.get("abilities", {}), "wisdom", _parse_int(character.get("proficiency_bonus")))
    value = _parse_int(bonus)
    if value is None:
        return ""
    return str(10 + value)


def _spell_blocks(spellcasting: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for block in spellcasting.get("spells_by_level", []) or []:
        if not isinstance(block, dict):
            continue
        level = _parse_int(block.get("level"))
        if level is not None:
            result[level] = block
    return result


def _modifier_from_score(score: Any) -> str:
    parsed = _parse_int(score)
    if parsed is None:
        return ""
    return modifier(parsed)


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"[-+]?\d+", str(value))
    if not match:
        return None
    return int(match.group(0))


def _signed(value: Any) -> str:
    parsed = _parse_int(value)
    if parsed is None:
        return _text(value)
    return f"{parsed:+d}"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return _norm(value) in {"1", "true", "yes", "si", "proficient", "competent"}


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value).lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def _text(value: Any) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


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
        f"Velocita: {character.get('speed', '')}",
        f"PF: {character.get('hit_points', {}).get('maximum', '')}",
        f"Dadi Vita: {character.get('hit_dice', '')}",
        "# Attacchi",
    ]
    for attack in character.get("attacks", []):
        lines.append(f"{attack.get('name', '')}: {attack.get('attack_bonus', '')}, {attack.get('damage_and_type', '')}")
    lines += ["# Equipaggiamento"]
    lines.extend(character.get("equipment", []))
    lines += ["# Personalita"]
    personality = character.get("personality", {})
    lines.append(f"Tratti: {personality.get('personality_traits', '')}")
    lines.append(f"Ideali: {personality.get('ideals', '')}")
    lines.append(f"Legami: {personality.get('bonds', '')}")
    lines.append(f"Difetti: {personality.get('flaws', '')}")
    lines += ["# Privilegi e tratti"]
    lines.extend(_feature_lines(character.get("features_and_traits", []), max_chars=90))
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
