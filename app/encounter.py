from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any


XP_THRESHOLDS_2014: dict[int, dict[str, int]] = {
    1: {"easy": 25, "medium": 50, "hard": 75, "deadly": 100},
    2: {"easy": 50, "medium": 100, "hard": 150, "deadly": 200},
    3: {"easy": 75, "medium": 150, "hard": 225, "deadly": 400},
    4: {"easy": 125, "medium": 250, "hard": 375, "deadly": 500},
    5: {"easy": 250, "medium": 500, "hard": 750, "deadly": 1100},
    6: {"easy": 300, "medium": 600, "hard": 900, "deadly": 1400},
    7: {"easy": 350, "medium": 750, "hard": 1100, "deadly": 1700},
    8: {"easy": 450, "medium": 900, "hard": 1400, "deadly": 2100},
    9: {"easy": 550, "medium": 1100, "hard": 1600, "deadly": 2400},
    10: {"easy": 600, "medium": 1200, "hard": 1900, "deadly": 2800},
    11: {"easy": 800, "medium": 1600, "hard": 2400, "deadly": 3600},
    12: {"easy": 1000, "medium": 2000, "hard": 3000, "deadly": 4500},
    13: {"easy": 1100, "medium": 2200, "hard": 3400, "deadly": 5100},
    14: {"easy": 1250, "medium": 2500, "hard": 3800, "deadly": 5700},
    15: {"easy": 1400, "medium": 2800, "hard": 4300, "deadly": 6400},
    16: {"easy": 1600, "medium": 3200, "hard": 4800, "deadly": 7200},
    17: {"easy": 2000, "medium": 3900, "hard": 5900, "deadly": 8800},
    18: {"easy": 2100, "medium": 4200, "hard": 6300, "deadly": 9500},
    19: {"easy": 2400, "medium": 4900, "hard": 7300, "deadly": 10900},
    20: {"easy": 2800, "medium": 5700, "hard": 8500, "deadly": 12700},
}

CR_XP_2014: dict[str, int] = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000,
}


@dataclass(frozen=True)
class XpBudget:
    easy: int
    medium: int
    hard: int
    deadly: int


def _member_level(member: dict[str, Any]) -> int:
    level = int(member.get("level", 1))
    return max(1, min(level, 20))


def calculate_party_budget(party: dict[str, Any]) -> XpBudget:
    budget = {"easy": 0, "medium": 0, "hard": 0, "deadly": 0}
    for member in party.get("members", []):
        thresholds = XP_THRESHOLDS_2014[_member_level(member)]
        for key in budget:
            budget[key] += thresholds[key]
    return XpBudget(**budget)


def monster_xp(candidate: dict[str, Any]) -> int:
    if candidate.get("xp_each") is not None:
        return int(candidate["xp_each"])
    cr = str(candidate.get("challenge_rating", "0")).strip()
    return CR_XP_2014.get(cr, 0)


def encounter_multiplier(monster_count: int, party_size: int) -> float:
    if monster_count <= 0:
        return 1.0
    if monster_count == 1:
        base = 1.0
    elif monster_count == 2:
        base = 1.5
    elif 3 <= monster_count <= 6:
        base = 2.0
    elif 7 <= monster_count <= 10:
        base = 2.5
    elif 11 <= monster_count <= 14:
        base = 3.0
    else:
        base = 4.0

    if party_size < 3:
        return _next_multiplier(base)
    if party_size > 5:
        return _previous_multiplier(base)
    return base


def _next_multiplier(value: float) -> float:
    ladder = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    for item in ladder:
        if item > value:
            return item
    return value


def _previous_multiplier(value: float) -> float:
    ladder = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    previous = 0.5
    for item in ladder:
        if item >= value:
            return previous
        previous = item
    return previous


def classify_difficulty(adjusted_xp: int, budget: XpBudget) -> str:
    if adjusted_xp < budget.easy:
        return "trivial"
    if adjusted_xp < budget.medium:
        return "easy"
    if adjusted_xp < budget.hard:
        return "medium"
    if adjusted_xp < budget.deadly:
        return "hard"
    return "deadly"


def build_encounter_response(payload: dict[str, Any]) -> dict[str, Any]:
    party = payload.get("party", {})
    members = party.get("members", [])
    party_size = len(members)
    budget = calculate_party_budget(party)
    monsters = payload.get("candidate_monsters") or []

    raw_xp = 0
    monster_count = 0
    for monster in monsters:
        count = int(monster.get("count") or 1)
        raw_xp += monster_xp(monster) * count
        monster_count += count

    multiplier = encounter_multiplier(monster_count, party_size) if monsters else 1.0
    adjusted_xp = int(raw_xp * multiplier)
    target = payload.get("target_difficulty") or "medium"
    estimated = classify_difficulty(adjusted_xp, budget) if monsters else "needs_monsters"

    if not members:
        return {
            "status": "needs_more_party_data",
            "summary": "Mi serve almeno il numero di PG e il livello di ciascuno.",
            "assumptions": [],
            "warnings": ["Party vuoto: impossibile calcolare budget XP."],
        }

    assumptions = []
    if party.get("current_resource_state", "unknown") == "unknown":
        assumptions.append("Stato risorse del party non indicato: considero un party mediamente pronto.")
    if not monsters:
        assumptions.append("Nessun mostro candidato fornito: restituisco struttura e target budget, non una lista definitiva.")

    warnings = []
    if estimated == "deadly" and party.get("current_resource_state") in {"half_spent", "heavily_spent"}:
        warnings.append("Encounter deadly contro party già consumato: rischio TPK elevato.")
    if monster_count == 1 and party_size >= 4 and target in {"boss", "deadly"}:
        warnings.append("Singolo nemico contro molti PG: aggiungi legendary actions, minion, fasi o obiettivi secondari.")

    battlefield = (payload.get("environment") or {}).get("terrain") or "terreno da definire"
    goal = payload.get("encounter_goal") or "mettere pressione al party con una scelta tattica o narrativa"

    return {
        "status": "ok",
        "summary": f"Budget calcolato per {party_size} PG. Difficoltà stimata: {estimated}. Target richiesto: {target}.",
        "assumptions": assumptions,
        "xp_budget": {
            "easy": budget.easy,
            "medium": budget.medium,
            "hard": budget.hard,
            "deadly": budget.deadly,
            "raw_monster_xp": raw_xp,
            "adjusted_xp": adjusted_xp,
            "multiplier_notes": f"{monster_count} creature, moltiplicatore x{multiplier}.",
        },
        "proposed_encounter": {
            "title": payload.get("title") or "Encounter bilanciato da Arcanista",
            "monsters": monsters,
            "battlefield": battlefield,
            "objective": goal,
            "opening_situation": "Presenta il pericolo insieme alla posta in gioco, non solo i nemici.",
            "round_2_or_3_complication": "Aggiungi una complicazione ambientale, un rinforzo, un ostaggio, un rituale o un cambio di terreno.",
            "tactics": [
                "Fai agire i nemici secondo obiettivi, non come blocchi statici di HP.",
                "Proteggi i ruoli fragili dei nemici con copertura, distanza o minion.",
                "Dai ai PG almeno una scelta diversa dal puro danno.",
            ],
            "noncombat_options": [
                "Parlare, intimidire, negoziare o scoprire una vulnerabilità.",
                "Interrompere un obiettivo invece di uccidere tutti.",
                "Usare ambiente, stealth o skill per cambiare la difficoltà.",
            ],
            "success": "I PG ottengono obiettivo, informazione, accesso o risorsa.",
            "failure": "La storia avanza con costo: risorsa persa, clock avanti, posizione peggiore o nemico rafforzato.",
            "reward_or_clue": payload.get("constraints", {}).get("treasure_or_clue_needed") or "Inserire una ricompensa o un indizio coerente con la scena.",
        },
        "balance_notes": [
            "Il budget XP è una base, non una verità assoluta: action economy, terreno, risorse e controllo contano molto.",
            "Se i PG sono ottimizzati o pieni di oggetti magici, alza pressione o obiettivi secondari.",
            "Se i PG sono inesperti o consumati, riduci danni concentrati e opzioni save-or-suck.",
        ],
        "scaling_knobs": [
            "Facile: rimuovi minion, riduci HP effettivi, dai copertura ai PG.",
            "Difficile: aggiungi minion, terreno pericoloso o timer.",
            "Boss: aggiungi legendary/lair action, fasi o obiettivo non combattivo.",
            "Anti-TPK: prevedi fuga, resa, ostaggio, negoziazione o conseguenza non letale.",
        ],
        "warnings": warnings,
    }
