from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Iterable, Mapping

from .weights import (
    derive_base_sku,
    detect_unit_weight_kg,
    strip_weight_from_name,
)


def _ascii_upper(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").upper().strip()


def normalize_sku(sku: str | None, name: str | None = None) -> tuple[str, str]:
    """
    Return a matching key and the method used.

    SKU matching is intentionally tolerant: spaces, hyphens, dots, slashes and
    accents are ignored. Example: ``FVNU06-28`` and ``fvnu0628`` become the
    same key. If an item has no SKU, its normalized name is used and the UI
    flags that match for review.
    """
    sku_clean = re.sub(r"[^A-Z0-9]", "", _ascii_upper(sku or ""))
    if sku_clean:
        return sku_clean, "SKU"

    name_clean = re.sub(r"[^A-Z0-9]", "", _ascii_upper(name or ""))
    if name_clean:
        return f"NOME::{name_clean}", "NOME"
    return "SEM_IDENTIFICADOR", "SEM_IDENTIFICADOR"


def _empty_slot() -> dict:
    return {
        "qty": 0.0,
        "skus": set(),
        "names": [],
        "active": [],
        "weight_candidates": set(),
        "weight_sources": [],
        "weight_conflict": False,
    }


def consolidate_inventory(
    inventory: Iterable[Mapping], labels: Mapping[str, str]
) -> tuple[list[dict], dict]:
    grouped: dict[str, dict] = defaultdict(
        lambda: {
            "basis": "SKU",
            "A": _empty_slot(),
            "B": _empty_slot(),
        }
    )

    for item in inventory:
        slot = str(item["slot"]).upper()
        if slot not in {"A", "B"}:
            continue
        key = item.get("normalized_sku")
        basis = "NOME" if str(key).startswith("NOME::") else "SKU"
        bucket = grouped[str(key)]
        bucket["basis"] = basis
        bucket[slot]["qty"] += float(item.get("qty_on_hand", 0) or 0)
        sku = (item.get("sku") or "").strip()
        if sku:
            bucket[slot]["skus"].add(sku)
        name = (item.get("name") or "").strip()
        if name and name not in bucket[slot]["names"]:
            bucket[slot]["names"].append(name)
        bucket[slot]["active"].append(bool(item.get("active", True)))

        detected = detect_unit_weight_kg(sku, name)
        if detected.kg is not None:
            bucket[slot]["weight_candidates"].add(round(detected.kg, 9))
        if detected.source not in bucket[slot]["weight_sources"]:
            bucket[slot]["weight_sources"].append(detected.source)
        bucket[slot]["weight_conflict"] = (
            bucket[slot]["weight_conflict"] or detected.conflict
        )

    result: list[dict] = []
    total_a = total_b = 0.0
    kg_a_total = kg_b_total = 0.0
    both = only_a = only_b = no_sku = duplicate_groups = 0
    weight_known = weight_unknown = weight_conflicts = 0

    for key, bucket in grouped.items():
        a = bucket["A"]
        b = bucket["B"]
        exists_a = bool(a["names"] or a["skus"])
        exists_b = bool(b["names"] or b["skus"])

        qty_a = round(a["qty"], 6)
        qty_b = round(b["qty"], 6)
        total_a += qty_a
        total_b += qty_b

        if exists_a and exists_b:
            status = "Nos dois"
            both += 1
        elif exists_a:
            status = f"Somente {labels['A']}"
            only_a += 1
        else:
            status = f"Somente {labels['B']}"
            only_b += 1

        if bucket["basis"] == "NOME":
            status += " · sem SKU (unido pelo nome)"
            no_sku += 1

        duplicates = []
        if len(a["names"]) > 1 or len(a["skus"]) > 1:
            duplicates.append(labels["A"])
        if len(b["names"]) > 1 or len(b["skus"]) > 1:
            duplicates.append(labels["B"])
        if duplicates:
            status += " · revisar duplicidade: " + ", ".join(duplicates)
            duplicate_groups += 1

        all_weight_candidates = set(a["weight_candidates"]) | set(
            b["weight_candidates"]
        )
        has_detection_conflict = bool(
            a["weight_conflict"] or b["weight_conflict"] or len(all_weight_candidates) > 1
        )
        if has_detection_conflict:
            unit_weight_kg = None
            weight_label = "Conflito"
            weight_status = "Revisar peso: há gramaturas divergentes no mesmo SKU"
            status += " · peso divergente"
            weight_conflicts += 1
        elif len(all_weight_candidates) == 1:
            unit_weight_kg = next(iter(all_weight_candidates))
            grams = unit_weight_kg * 1000
            if abs(unit_weight_kg - round(unit_weight_kg)) < 1e-9 and unit_weight_kg >= 1:
                weight_label = f"{int(round(unit_weight_kg))} kg"
            elif abs(grams - round(grams)) < 1e-9:
                weight_label = f"{int(round(grams))} g"
            else:
                weight_label = f"{grams:.3f}".rstrip("0").rstrip(".").replace(".", ",") + " g"
            weight_status = "Peso identificado automaticamente"
            weight_known += 1
        else:
            unit_weight_kg = None
            weight_label = "Não identificado"
            weight_status = "Inclua 250g/500g no nome ou um sufixo como -250/-500 no SKU"
            status += " · peso não identificado"
            weight_unknown += 1

        if unit_weight_kg is not None:
            kg_a = round(qty_a * unit_weight_kg, 6)
            kg_b = round(qty_b * unit_weight_kg, 6)
            kg_total = round(kg_a + kg_b, 6)
            kg_a_total += kg_a
            kg_b_total += kg_b
        else:
            kg_a = kg_b = kg_total = None

        product = (a["names"] or b["names"] or ["Produto sem nome"])[0]
        display_sku = sorted(a["skus"] or b["skus"] or {key})[0]
        weight_sources = []
        for source in a["weight_sources"] + b["weight_sources"]:
            if source not in weight_sources:
                weight_sources.append(source)

        result.append(
            {
                "match_key": key,
                "sku": display_sku,
                "product": product,
                "sku_a": ", ".join(sorted(a["skus"])),
                "qty_a": qty_a,
                "kg_a": kg_a,
                "sku_b": ", ".join(sorted(b["skus"])),
                "qty_b": qty_b,
                "kg_b": kg_b,
                "total": round(qty_a + qty_b, 6),
                "kg_total": kg_total,
                "unit_weight_kg": unit_weight_kg,
                "weight_label": weight_label,
                "weight_source": "; ".join(weight_sources),
                "weight_status": weight_status,
                "weight_conflict": has_detection_conflict,
                "status": status,
                "basis": bucket["basis"],
                "inactive_a": exists_a and a["active"] and not any(a["active"]),
                "inactive_b": exists_b and b["active"] and not any(b["active"]),
            }
        )

    result.sort(key=lambda row: (_ascii_upper(row["sku"]), _ascii_upper(row["product"])))
    stats = {
        "products": len(result),
        "qty_a": round(total_a, 6),
        "qty_b": round(total_b, 6),
        "qty_total": round(total_a + total_b, 6),
        "kg_a": round(kg_a_total, 6),
        "kg_b": round(kg_b_total, 6),
        "kg_total": round(kg_a_total + kg_b_total, 6),
        "both": both,
        "only_a": only_a,
        "only_b": only_b,
        "no_sku": no_sku,
        "duplicate_groups": duplicate_groups,
        "weight_known": weight_known,
        "weight_unknown": weight_unknown,
        "weight_conflicts": weight_conflicts,
    }
    return result, stats


def consolidate_by_base_product(
    rows: Iterable[Mapping], labels: Mapping[str, str]
) -> list[dict]:
    """Agrupa potes de gramaturas diferentes em um resumo por rapé-base."""

    grouped: dict[str, dict] = {}

    for row in rows:
        candidate_skus = []
        for value in [row.get("sku_a"), row.get("sku_b"), row.get("sku")]:
            for sku in str(value or "").split(","):
                sku = sku.strip()
                if sku and sku not in candidate_skus:
                    candidate_skus.append(sku)

        base_skus = [derive_base_sku(sku) for sku in candidate_skus]
        base_skus = [sku for sku in base_skus if sku]
        if base_skus:
            base_display = sorted(base_skus, key=_ascii_upper)[0]
            key = "SKU::" + re.sub(r"[^A-Z0-9]", "", _ascii_upper(base_display))
        else:
            base_display = ""
            base_name_key = re.sub(
                r"[^A-Z0-9]", "", _ascii_upper(strip_weight_from_name(row.get("product")))
            )
            key = "NOME::" + (base_name_key or str(row.get("match_key") or "SEM_NOME"))

        if key not in grouped:
            grouped[key] = {
                "base_sku": base_display,
                "product": strip_weight_from_name(row.get("product")),
                "qty_a": 0.0,
                "qty_b": 0.0,
                "kg_a": 0.0,
                "kg_b": 0.0,
                "variants": set(),
                "unknown_variants": 0,
                "known_variants": 0,
            }

        bucket = grouped[key]
        bucket["qty_a"] += float(row.get("qty_a") or 0)
        bucket["qty_b"] += float(row.get("qty_b") or 0)
        variant = f"{row.get('sku') or 'sem SKU'} ({row.get('weight_label')})"
        bucket["variants"].add(variant)
        if row.get("kg_total") is None:
            bucket["unknown_variants"] += 1
        else:
            bucket["known_variants"] += 1
            bucket["kg_a"] += float(row.get("kg_a") or 0)
            bucket["kg_b"] += float(row.get("kg_b") or 0)

    result = []
    for bucket in grouped.values():
        unknown = int(bucket["unknown_variants"])
        if unknown:
            status = f"Parcial: {unknown} variação(ões) sem peso confiável"
        else:
            status = "Completo"
        known = int(bucket["known_variants"])
        kg_a = round(bucket["kg_a"], 6) if known else None
        kg_b = round(bucket["kg_b"], 6) if known else None
        kg_total = round(bucket["kg_a"] + bucket["kg_b"], 6) if known else None
        result.append(
            {
                "base_sku": bucket["base_sku"] or "—",
                "product": bucket["product"],
                "qty_a": round(bucket["qty_a"], 6),
                "qty_b": round(bucket["qty_b"], 6),
                "kg_a": kg_a,
                "kg_b": kg_b,
                "kg_total": kg_total,
                "variants": ", ".join(sorted(bucket["variants"], key=_ascii_upper)),
                "status": status,
                "complete": unknown == 0,
            }
        )

    result.sort(key=lambda row: (_ascii_upper(row["base_sku"]), _ascii_upper(row["product"])))
    return result
