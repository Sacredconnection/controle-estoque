from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class WeightDetection:
    """Resultado da identificação do peso de uma unidade de estoque."""

    kg: float | None
    label: str
    source: str
    conflict: bool = False


# Códigos de gramatura aceitos no fim do SKU quando existe um separador.
# Ex.: RANU06-250, RANU06-500, FVNU06-07, FVNU06-14, FVNU06-28.
_SUFFIX_GRAMS: dict[str, float] = {
    "05": 5.0,
    "5": 5.0,
    "07": 7.1,
    "7.1": 7.1,
    "7,1": 7.1,
    "10": 10.0,
    "14": 14.0,
    "20": 20.0,
    "28": 28.0,
    "50": 50.0,
    "100": 100.0,
    "250": 250.0,
    "500": 500.0,
    "1000": 1000.0,
}

_WEIGHT_WITH_UNIT_RE = re.compile(
    r"(?<![\d])(?P<value>\d{1,4}(?:[\.,]\d+)?)\s*"
    r"(?P<unit>KG|KGS?|QUILOS?|KILOGRAMAS?|G|GR|GRS?|GRAMAS?|GRAMS?)\b",
    re.IGNORECASE,
)
_SKU_SEPARATED_SUFFIX_RE = re.compile(
    r"(?:^|[-_. /])(?P<code>05|5|07|7[\.,]1|10|14|20|28|50|100|250|500|1000)"
    r"(?P<unit>KG|G|GR)?$",
    re.IGNORECASE,
)
_SKU_EXPLICIT_UNIT_SUFFIX_RE = re.compile(
    r"(?P<value>\d{1,4}(?:[\.,]\d+)?)(?P<unit>KG|G|GR)$",
    re.IGNORECASE,
)
_TERMINAL_KG_RE = re.compile(r"(?:^|\s)KG\s*$", re.IGNORECASE)


def _ascii_upper(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").upper().strip()


def _to_number(value: str) -> float:
    return float(value.replace(",", "."))


def _to_kg(value: float, unit: str) -> float:
    unit = _ascii_upper(unit)
    if unit.startswith("K") or unit.startswith("Q"):
        return value
    return value / 1000.0


def format_weight_label(kg: float | None) -> str:
    if kg is None:
        return "Não identificado"
    grams = kg * 1000.0
    if abs(kg - round(kg)) < 1e-9 and kg >= 1:
        amount = f"{int(round(kg))}"
        return f"{amount} kg"
    if abs(grams - round(grams)) < 1e-9:
        amount = f"{int(round(grams))}"
    else:
        amount = f"{grams:.3f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{amount} g"


def _candidates_from_name(name: str | None) -> list[tuple[float, str]]:
    text = name or ""
    candidates: list[tuple[float, str]] = []
    for match in _WEIGHT_WITH_UNIT_RE.finditer(text):
        value = _to_number(match.group("value"))
        kg = _to_kg(value, match.group("unit"))
        if 0 < kg <= 1000:
            candidates.append((kg, f"nome: {match.group(0).strip()}"))

    # Alguns cadastros usam apenas "... Kg" para informar que QtyOnHand já está em kg.
    # Só aplicamos essa regra quando nenhuma gramatura numérica foi encontrada no nome.
    if not candidates and _TERMINAL_KG_RE.search(text):
        candidates.append((1.0, "nome: unidade Kg"))
    return candidates


def _candidates_from_sku(sku: str | None) -> list[tuple[float, str]]:
    text = (sku or "").strip()
    if not text:
        return []

    candidates: list[tuple[float, str]] = []
    explicit = _SKU_EXPLICIT_UNIT_SUFFIX_RE.search(text)
    if explicit:
        value = _to_number(explicit.group("value"))
        kg = _to_kg(value, explicit.group("unit"))
        if 0 < kg <= 1000:
            candidates.append((kg, f"SKU: {explicit.group(0)}"))

    separated = _SKU_SEPARATED_SUFFIX_RE.search(text)
    if separated:
        code = separated.group("code").replace(",", ".")
        unit = separated.group("unit")
        if unit:
            value = _to_number(code)
            kg = _to_kg(value, unit)
        else:
            kg = _SUFFIX_GRAMS[code] / 1000.0
        candidates.append((kg, f"SKU: {separated.group(0).lstrip('-_. /')}"))

    return candidates


def detect_unit_weight_kg(sku: str | None, name: str | None) -> WeightDetection:
    """
    Detecta o peso de uma unidade do item.

    A regra é conservadora: ela só usa gramaturas explícitas no nome ou um
    sufixo seguro no SKU. Quando há divergência entre SKU e nome, o peso não é
    calculado e o item fica marcado para revisão, evitando uma conversão errada.
    """

    candidates = _candidates_from_name(name) + _candidates_from_sku(sku)
    if not candidates:
        return WeightDetection(
            kg=None,
            label="Não identificado",
            source="Nenhuma gramatura encontrada no SKU ou no nome",
        )

    grouped: dict[float, list[str]] = {}
    for kg, source in candidates:
        key = round(kg, 9)
        grouped.setdefault(key, [])
        if source not in grouped[key]:
            grouped[key].append(source)

    if len(grouped) > 1:
        details = []
        for kg, sources in sorted(grouped.items()):
            details.append(f"{format_weight_label(kg)} ({', '.join(sources)})")
        return WeightDetection(
            kg=None,
            label="Conflito",
            source="Pesos divergentes: " + "; ".join(details),
            conflict=True,
        )

    kg = next(iter(grouped))
    sources = grouped[kg]
    return WeightDetection(
        kg=kg,
        label=format_weight_label(kg),
        source="; ".join(sources),
    )


def strip_weight_from_name(name: str | None) -> str:
    """Remove gramatura explícita do nome para formar um nome-base legível."""

    text = name or "Produto sem nome"
    text = _WEIGHT_WITH_UNIT_RE.sub("", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*[-–—|/]\s*$", "", text)
    text = _TERMINAL_KG_RE.sub("", text)
    return text.strip(" -–—|/") or (name or "Produto sem nome")


def derive_base_sku(sku: str | None) -> str | None:
    """
    Remove apenas sufixos de gramatura inequívocos.

    Não removemos números colados sem separador (ex.: RAKU2500), pois podem ser
    parte do código-base e não uma gramatura.
    """

    text = (sku or "").strip()
    if not text:
        return None

    explicit = _SKU_EXPLICIT_UNIT_SUFFIX_RE.search(text)
    if explicit:
        base = text[: explicit.start()].rstrip("-_. / ")
        return base or None

    separated = _SKU_SEPARATED_SUFFIX_RE.search(text)
    if separated:
        base = text[: separated.start()].rstrip("-_. / ")
        return base or None

    return None
