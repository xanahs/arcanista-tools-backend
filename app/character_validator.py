from __future__ import annotations

import re
import unicodedata
from typing import Any


ABILITY_DEFS = [
    ("strength", "Forza", ["strength", "forza", "str", "for"]),
    ("dexterity", "Destrezza", ["dexterity", "destrezza", "dex", "des"]),
    ("constitution", "Costituzione", ["constitution", "costituzione", "con", "cos"]),
    ("intelligence", "Intelligenza", ["intelligence", "intelligenza", "int"]),
    ("wisdom", "Saggezza", ["wisdom", "saggezza", "wis", "sag"]),
    ("charisma", "Carisma", ["charisma", "carisma", "cha", "car"]),
]

SKILL_DEFS = [
    ("acrobatics", "Acrobazia", ["acrobatics", "acrobazia"]),
    ("animal_handling", "Addestrare Animali", ["animal handling", "addestrare animali"]),
    ("arcana", "Arcano", ["arcana", "arcano"]),
    ("athletics", "Atletica", ["athletics", "atletica"]),
    ("deception", "Inganno", ["deception", "inganno"]),
    ("history", "Storia", ["history", "storia"]),
    ("insight", "Intuizione", ["insight", "intuizione"]),
    ("intimidation", "Intimidire", ["intimidation", "intimidire"]),
    ("investigation", "Indagare", ["investigation", "indagare"]),
    ("medicine", "Medicina", ["medicine", "medicina"]),
    ("nature", "Natura", ["nature", "natura"]),
    ("perception", "Percezione", ["perception", "percezione"]),
    ("performance", "Intrattenere", ["performance", "intrattenere"]),
    ("persuasion", "Persuasione", ["persuasion", "persuasione"]),
    ("religion", "Religione", ["religion", "religione"]),
    ("sleight_of_hand", "Rapidita di Mano", ["sleight of hand", "rapidita di mano"]),
    ("stealth", "Furtivita", ["stealth", "furtivita"]),
    ("survival", "Sopravvivenza", ["survival", "sopravvivenza"]),
]

SPELLCASTER_TERMS = {
    "artificer",
    "artefice",
    "bard",
    "bardo",
    "cleric",
    "chierico",
    "druid",
    "druido",
    "paladin",
    "paladino",
    "ranger",
    "sorcerer",
    "stregone",
    "warlock",
    "wizard",
    "mago",
}


def validate_character_sheet_payload(payload: dict[str, Any]) -> dict[str, Any]:
    character = payload.get("character", payload)
    if not isinstance(character, dict):
        return _report(
            [
                _finding(
                    "blocker",
                    "invalid_payload",
                    "character",
                    "Il payload non contiene un oggetto character valido.",
                    "Invia un JSON con la chiave character e i dati della scheda.",
                )
            ],
            {},
            None,
        )

    findings: list[dict[str, Any]] = []
    inferred: dict[str, Any] = {}
    header = _dict(character.get("header"))
    level = _parse_level(character, header)
    if level is not None:
        inferred["level"] = level

    _validate_header(header, findings)
    _validate_abilities(character, findings)
    _validate_proficiency(character, level, findings, inferred)
    _validate_saves_and_skills(character, findings)
    _validate_combat(character, findings)
    _validate_attacks(character, findings)
    _validate_features(character, findings)
    _validate_spellcasting(character, header, level, findings)
    _validate_character_context(character, findings)

    return _report(findings, character, level, inferred)


def _validate_header(header: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    required = {
        "character_name": "nome del personaggio",
        "class_and_level": "classe e livello",
        "race_or_species": "razza/specie/lineage",
        "background": "background",
    }
    for key, label in required.items():
        if _blank(header.get(key)):
            findings.append(
                _finding(
                    "blocker",
                    f"missing_header_{key}",
                    f"header.{key}",
                    f"Manca {label}.",
                    f"Compila header.{key}.",
                    "intestazione",
                )
            )
    if _blank(header.get("player_name")):
        findings.append(
            _finding(
                "warning",
                "missing_player_name",
                "header.player_name",
                "Manca il nome del giocatore.",
                "Puoi lasciarlo vuoto se non serve, oppure compilarlo prima del PDF finale.",
                "intestazione",
            )
        )


def _validate_abilities(character: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    abilities = _dict(character.get("abilities"))
    if not abilities:
        findings.append(
            _finding(
                "blocker",
                "missing_abilities",
                "abilities",
                "Mancano tutte le caratteristiche.",
                "Compila Forza, Destrezza, Costituzione, Intelligenza, Saggezza e Carisma.",
                "caratteristiche",
            )
        )
        return

    point_buy_scores: list[int] = []
    for key, label, aliases in ABILITY_DEFS:
        data = _ability_data(abilities, key, aliases)
        score = _parse_int(data.get("score") or data.get("value"))
        if score is None:
            findings.append(
                _finding(
                    "blocker",
                    f"missing_ability_{key}",
                    f"abilities.{key}.score",
                    f"Manca il punteggio di {label}.",
                    f"Compila abilities.{key}.score.",
                    "caratteristiche",
                )
            )
            continue
        if score < 1 or score > 30:
            findings.append(
                _finding(
                    "blocker",
                    f"invalid_ability_{key}",
                    f"abilities.{key}.score",
                    f"{label} ha un valore fuori scala: {score}.",
                    "Usa un valore plausibile per D&D 5e, di solito 1-30.",
                    "caratteristiche",
                )
            )
        if 8 <= score <= 15:
            point_buy_scores.append(score)
        modifier = data.get("modifier")
        expected = _modifier(score)
        if not _blank(modifier) and _signed(modifier) != expected:
            findings.append(
                _finding(
                    "warning",
                    f"ability_modifier_mismatch_{key}",
                    f"abilities.{key}.modifier",
                    f"Il modificatore di {label} sembra {modifier}, ma da {score} dovrebbe essere {expected}.",
                    f"Correggi il modificatore a {expected} o spiega il bonus speciale.",
                    "caratteristiche",
                )
            )

    if len(point_buy_scores) == 6:
        cost = sum(_point_buy_cost(score) for score in point_buy_scores)
        if cost > 27:
            findings.append(
                _finding(
                    "warning",
                    "point_buy_over_27",
                    "abilities",
                    f"I punteggi sembrano costare {cost} punti prima dei bonus, oltre il point buy 27.",
                    "Verifica se i punteggi includono bonus razziali/specie o se il point buy e' stato superato.",
                    "point_buy",
                )
            )
    else:
        findings.append(
            _finding(
                "warning",
                "point_buy_not_verifiable",
                "abilities",
                "Non posso verificare completamente il point buy 27 perche alcuni valori sono fuori dal range 8-15 o mancanti.",
                "Se vuoi controllo point buy preciso, invia anche i punteggi base prima dei bonus.",
                "point_buy",
            )
        )


def _validate_proficiency(
    character: dict[str, Any],
    level: int | None,
    findings: list[dict[str, Any]],
    inferred: dict[str, Any],
) -> None:
    prof = _parse_int(character.get("proficiency_bonus"))
    expected = _proficiency_for_level(level)
    if prof is None:
        if expected is None:
            findings.append(
                _finding(
                    "blocker",
                    "missing_proficiency_bonus",
                    "proficiency_bonus",
                    "Manca il bonus competenza.",
                    "Compila proficiency_bonus o rendi chiaro il livello del personaggio.",
                    "meccanica",
                )
            )
        else:
            inferred["proficiency_bonus"] = expected
            findings.append(
                _finding(
                    "warning",
                    "inferred_proficiency_bonus",
                    "proficiency_bonus",
                    f"Il bonus competenza non e' scritto, ma dal livello {level} dovrebbe essere +{expected}.",
                    "Aggiungi proficiency_bonus al JSON per evitare ambiguita.",
                    "meccanica",
                )
            )
        return
    if expected is not None and prof != expected:
        findings.append(
            _finding(
                "warning",
                "proficiency_bonus_mismatch",
                "proficiency_bonus",
                f"Il bonus competenza e' +{prof}, ma al livello {level} dovrebbe essere +{expected}.",
                "Correggi proficiency_bonus o chiarisci se ci sono regole speciali.",
                "meccanica",
            )
        )


def _validate_saves_and_skills(character: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    saves = character.get("saving_throws")
    if not isinstance(saves, list):
        findings.append(
            _finding(
                "blocker",
                "missing_saving_throws",
                "saving_throws",
                "Manca la lista completa dei tiri salvezza.",
                "Invia tutti e 6 i tiri salvezza con bonus e proficient true/false.",
                "competenze",
            )
        )
    else:
        for key, label, aliases in ABILITY_DEFS:
            if _find_named(saves, [key, label, *aliases]) is None:
                findings.append(
                    _finding(
                        "blocker",
                        f"missing_save_{key}",
                        "saving_throws",
                        f"Manca il tiro salvezza di {label}.",
                        f"Aggiungi {label} a saving_throws con bonus e proficient true/false.",
                        "competenze",
                    )
                )

    skills = character.get("skills")
    if not isinstance(skills, list):
        findings.append(
            _finding(
                "blocker",
                "missing_skills",
                "skills",
                "Manca la lista completa delle abilita.",
                "Invia tutte le 18 abilita con bonus e proficient true/false.",
                "competenze",
            )
        )
    else:
        for key, label, aliases in SKILL_DEFS:
            if _find_named(skills, [key, label, *aliases]) is None:
                findings.append(
                    _finding(
                        "blocker",
                        f"missing_skill_{key}",
                        "skills",
                        f"Manca l'abilita {label}.",
                        f"Aggiungi {label} a skills con bonus e proficient true/false.",
                        "competenze",
                    )
                )

    if _blank(character.get("proficiencies_and_languages")):
        findings.append(
            _finding(
                "warning",
                "missing_proficiencies_languages",
                "proficiencies_and_languages",
                "Mancano competenze e linguaggi.",
                "Aggiungi armi, armature, strumenti e linguaggi noti.",
                "competenze",
            )
        )


def _validate_combat(character: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for field, label in [
        ("armor_class", "Classe Armatura"),
        ("initiative", "iniziativa"),
        ("speed", "velocita"),
        ("hit_dice", "dadi vita"),
    ]:
        if _blank(character.get(field)):
            findings.append(
                _finding(
                    "blocker",
                    f"missing_{field}",
                    field,
                    f"Manca {label}.",
                    f"Compila {field}.",
                    "combattimento",
                )
            )
    hp = _dict(character.get("hit_points"))
    if _parse_int(hp.get("maximum")) is None:
        findings.append(
            _finding(
                "blocker",
                "missing_max_hp",
                "hit_points.maximum",
                "Mancano i PF massimi.",
                "Compila hit_points.maximum. PF attuali e temporanei possono restare vuoti nel PDF.",
                "combattimento",
            )
        )


def _validate_attacks(character: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    attacks = character.get("attacks")
    if not isinstance(attacks, list) or not attacks:
        findings.append(
            _finding(
                "warning",
                "missing_attacks",
                "attacks",
                "Non ci sono attacchi o incantesimi offensivi pronti.",
                "Aggiungi almeno arma principale, cantrip offensivo o attacco naturale se rilevante.",
                "combattimento",
            )
        )
        return
    for index, attack in enumerate(attacks[:5]):
        if not isinstance(attack, dict):
            continue
        if _blank(attack.get("name")) or _blank(attack.get("damage_and_type")):
            findings.append(
                _finding(
                    "warning",
                    "incomplete_attack",
                    f"attacks[{index}]",
                    "Un attacco non ha nome o danno/tipo.",
                    "Compila name, attack_bonus e damage_and_type.",
                    "combattimento",
                )
            )


def _validate_features(character: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    features = character.get("features_and_traits")
    if not isinstance(features, list) or not features:
        findings.append(
            _finding(
                "blocker",
                "missing_features_and_traits",
                "features_and_traits",
                "Mancano privilegi, tratti e capacita speciali.",
                "Aggiungi tratti di classe, sottoclasse, razza/specie, background, talenti e oggetti rilevanti.",
                "privilegi",
            )
        )
        return

    title_only: list[str] = []
    too_long: list[str] = []
    numbers_to_check: list[str] = []
    scaling_to_confirm: list[str] = []
    for item in features:
        if isinstance(item, dict):
            name = str(item.get("name") or "privilegio senza nome")
            summary = str(item.get("summary") or "")
            mechanics = str(item.get("mechanics") or "")
            uses = str(item.get("uses") or "")
            if len(summary.strip()) < 12 and len(mechanics.strip()) < 4 and len(uses.strip()) < 4:
                title_only.append(name)
            if len(summary.strip()) > 240:
                too_long.append(name)
            combined = " ".join(
                str(item.get(key) or "")
                for key in ["summary", "mechanics", "uses", "action_cost", "notes"]
            )
            if not re.search(r"\d|d\d|CD|DC|azione|action|riposo|rest|round|turno|bonus|reaction|reazione", combined, re.IGNORECASE):
                numbers_to_check.append(name)
            scaling = item.get("scaling") or item.get("higher_level_scaling") or item.get("future_scaling")
            if scaling and not _truthy(item.get("include_scaling") or item.get("include_higher_level_scaling")):
                scaling_to_confirm.append(name)
        elif isinstance(item, str) and len(item.strip()) < 28 and ":" not in item:
            title_only.append(item.strip())

    if title_only:
        findings.append(
            _finding(
                "blocker",
                "feature_names_without_rules",
                "features_and_traits",
                "Alcuni privilegi sembrano avere solo il titolo: " + ", ".join(title_only[:8]),
                "Per ogni privilegio aggiungi una breve spiegazione pratica con numeri, usi, azione, DC o durata se rilevanti.",
                "privilegi",
            )
        )
    if too_long:
        findings.append(
            _finding(
                "warning",
                "feature_summaries_too_long",
                "features_and_traits",
                "Alcuni privilegi hanno spiegazioni troppo lunghe per la scheda: " + ", ".join(too_long[:8]),
                "Riduci ogni spiegazione a una frase pratica; mantieni tutti i numeri in mechanics.",
                "privilegi",
            )
        )
    if numbers_to_check:
        findings.append(
            _finding(
                "warning",
                "feature_numbers_not_explicit",
                "features_and_traits",
                "Alcuni privilegi non mostrano numeri, usi, azione o durata espliciti: " + ", ".join(numbers_to_check[:8]),
                "Se il privilegio ha numeri, usi, DC, dadi, durata, range, costo d'azione o ricarica, inseriscili tutti in mechanics/uses/action_cost.",
                "privilegi",
            )
        )
    if scaling_to_confirm:
        findings.append(
            _finding(
                "warning",
                "feature_scaling_requires_confirmation",
                "features_and_traits",
                "Alcuni privilegi hanno scaling futuro non marcato per inclusione: " + ", ".join(scaling_to_confirm[:8]),
                "Chiedi all'utente se vuole stampare anche lo scaling dei livelli futuri; se sì usa include_scaling=true.",
                "privilegi",
            )
        )


def _validate_spellcasting(
    character: dict[str, Any],
    header: dict[str, Any],
    level: int | None,
    findings: list[dict[str, Any]],
) -> None:
    class_text = " ".join(str(value) for value in [header.get("class_and_level"), character.get("class_name")] if value)
    spellcasting = character.get("spellcasting")
    likely_caster = _looks_like_spellcaster(class_text)

    if likely_caster and not isinstance(spellcasting, dict):
        findings.append(
            _finding(
                "blocker",
                "missing_spellcasting",
                "spellcasting",
                "Il personaggio sembra un incantatore, ma manca la sezione incantesimi.",
                "Compila spellcasting con classe, caratteristica, CD, bonus attacco, trucchetti e incantesimi per livello.",
                "incantesimi",
            )
        )
        return
    if not isinstance(spellcasting, dict) or not spellcasting:
        return

    for field, label in [
        ("spellcasting_class", "classe da incantatore"),
        ("spellcasting_ability", "caratteristica da incantatore"),
        ("spell_save_dc", "CD incantesimi"),
        ("spell_attack_bonus", "bonus attacco incantesimi"),
    ]:
        if _blank(spellcasting.get(field)):
            findings.append(
                _finding(
                    "warning",
                    f"missing_spellcasting_{field}",
                    f"spellcasting.{field}",
                    f"Manca {label}.",
                    f"Compila spellcasting.{field} se il personaggio lancia incantesimi.",
                    "incantesimi",
                )
            )

    blocks = spellcasting.get("spells_by_level")
    if likely_caster and (not isinstance(blocks, list) or not blocks):
        findings.append(
            _finding(
                "blocker",
                "missing_spells_by_level",
                "spellcasting.spells_by_level",
                "Manca la lista degli incantesimi per livello.",
                "Aggiungi spells_by_level con livello, slot totali e incantesimi conosciuti/preparati.",
                "incantesimi",
            )
        )
    elif isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            spell_level = _parse_int(block.get("level"))
            if spell_level and spell_level > 0 and _blank(block.get("slots_total")):
                findings.append(
                    _finding(
                        "warning",
                        "missing_spell_slots",
                        "spellcasting.spells_by_level",
                        f"Mancano gli slot totali per gli incantesimi di livello {spell_level}.",
                        "Aggiungi slots_total per ogni livello di incantesimo disponibile.",
                        "incantesimi",
                    )
                )

    if level is not None and level >= 4 and not _has_asi_or_feat(character):
        findings.append(
            _finding(
                "warning",
                "asi_or_feat_not_visible",
                "features_and_traits",
                "Non vedo chiaramente ASI o talento per un livello in cui potrebbe esserci.",
                "Verifica ASI/talenti ai livelli corretti della classe.",
                "progressione",
            )
        )


def _validate_character_context(character: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    if _blank(character.get("equipment")):
        findings.append(
            _finding(
                "warning",
                "missing_equipment",
                "equipment",
                "Manca l'equipaggiamento.",
                "Aggiungi equipaggiamento iniziale, denaro, focus/componenti e oggetti importanti.",
                "equipaggiamento",
            )
        )
    if _blank(character.get("backstory")):
        findings.append(
            _finding(
                "warning",
                "missing_backstory",
                "backstory",
                "Manca la backstory.",
                "Puoi lasciarla vuota per una scheda meccanica, ma per Arcanista conviene aggiungere almeno motivo per partire e legame col party.",
                "narrativa",
            )
        )


def _report(
    findings: list[dict[str, Any]],
    character: dict[str, Any],
    level: int | None,
    inferred: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers = [item for item in findings if item["severity"] == "blocker"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    suggestions = [item for item in findings if item["severity"] == "suggestion"]
    ready = not blockers
    return {
        "status": "ready" if ready else "needs_review",
        "ready_for_pdf": ready,
        "summary": _summary(character, level, ready, blockers, warnings),
        "blockers": blockers,
        "warnings": warnings,
        "suggestions": suggestions,
        "missing_required": [item["field"] for item in blockers],
        "missing_optional": [item["field"] for item in warnings if item["code"].startswith("missing")],
        "inferred": inferred or {},
        "checklist": _checklist(findings),
    }


def _summary(
    character: dict[str, Any],
    level: int | None,
    ready: bool,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> str:
    name = _dict(character.get("header")).get("character_name") or "Personaggio"
    level_text = f" livello {level}" if level else ""
    if ready:
        return f"{name}{level_text}: pronto per il PDF con {len(warnings)} warning da controllare."
    return f"{name}{level_text}: non pronto per il PDF; {len(blockers)} problemi bloccanti e {len(warnings)} warning."


def _checklist(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    categories = [
        "intestazione",
        "caratteristiche",
        "point_buy",
        "meccanica",
        "competenze",
        "combattimento",
        "privilegi",
        "incantesimi",
        "equipaggiamento",
        "narrativa",
        "progressione",
    ]
    result = []
    for category in categories:
        items = [item for item in findings if item.get("category") == category]
        if any(item["severity"] == "blocker" for item in items):
            status = "needs_fix"
        elif any(item["severity"] == "warning" for item in items):
            status = "warning"
        else:
            status = "ok"
        result.append({"category": category, "status": status, "notes": str(len(items))})
    return result


def _finding(
    severity: str,
    code: str,
    field: str,
    message: str,
    fix: str,
    category: str = "generale",
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "field": field,
        "message": message,
        "fix": fix,
        "category": category,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _blank(value: Any) -> bool:
    return value in (None, "", [], {})


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _parse_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"-?\d+", str(value or ""))
    return int(match.group(0)) if match else None


def _parse_level(character: dict[str, Any], header: dict[str, Any]) -> int | None:
    for value in [
        character.get("level"),
        header.get("level"),
        header.get("class_and_level"),
        character.get("class_and_level"),
    ]:
        if isinstance(value, int):
            return value if 1 <= value <= 20 else None
        text = str(value or "")
        match = re.search(r"(?:livello|level|lv\.?|lvl\.?)\s*(\d{1,2})", text, re.IGNORECASE)
        if match:
            level = int(match.group(1))
            return level if 1 <= level <= 20 else None
        numbers = [int(item) for item in re.findall(r"\b([1-9]|1[0-9]|20)\b", text)]
        if numbers:
            return numbers[-1]
    return None


def _ability_data(abilities: dict[str, Any], key: str, aliases: list[str]) -> dict[str, Any]:
    if isinstance(abilities.get(key), dict):
        return abilities.get(key, {})
    alias_set = {_norm(alias) for alias in aliases}
    for candidate, value in abilities.items():
        if _norm(candidate) in alias_set and isinstance(value, dict):
            return value
    return {}


def _find_named(rows: list[Any], names: list[str]) -> dict[str, Any] | None:
    targets = {_norm(name) for name in names}
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = [row.get("name"), row.get("key"), row.get("label")]
        if any(_norm(value) in targets for value in values):
            return row
    return None


def _modifier(score: int) -> str:
    return f"{((score - 10) // 2):+d}"


def _signed(value: Any) -> str:
    parsed = _parse_int(value)
    return f"{parsed:+d}" if parsed is not None else str(value)


def _point_buy_cost(score: int) -> int:
    costs = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
    return costs.get(score, 99)


def _proficiency_for_level(level: int | None) -> int | None:
    if level is None or level < 1 or level > 20:
        return None
    return 2 + (level - 1) // 4


def _looks_like_spellcaster(text: str) -> bool:
    normalized = _norm(text)
    return any(term in normalized.split() or term in normalized for term in SPELLCASTER_TERMS)


def _has_asi_or_feat(character: dict[str, Any]) -> bool:
    features = character.get("features_and_traits")
    if not isinstance(features, list):
        return False
    text = " ".join(str(item) for item in features).lower()
    needles = ["asi", "ability score", "incremento", "aumento", "talento", "feat"]
    return any(needle in text for needle in needles)
