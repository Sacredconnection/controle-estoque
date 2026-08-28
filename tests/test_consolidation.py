from qbo_stock.consolidation import (
    consolidate_by_base_product,
    consolidate_inventory,
    normalize_sku,
)


def _item(slot, sku, name, qty):
    key, _ = normalize_sku(sku, name)
    return {
        "slot": slot,
        "sku": sku,
        "normalized_sku": key,
        "name": name,
        "qty_on_hand": qty,
        "active": 1,
    }


def test_sku_normalization_ignores_separators_and_case():
    key_a, basis_a = normalize_sku("FVNU06-28", "A")
    key_b, basis_b = normalize_sku("fvnu0628", "B")
    assert key_a == key_b == "FVNU0628"
    assert basis_a == basis_b == "SKU"


def test_consolidation_sums_two_companies_and_converts_250g_to_kg():
    inventory = [
        _item("A", "RANU06-250", "Nukini Onça 250g", 20),
        _item("B", "RANU06-250", "Nukini Ojo de Jaguar 250g", 12),
    ]
    rows, stats = consolidate_inventory(inventory, {"A": "A", "B": "B"})
    assert len(rows) == 1
    assert rows[0]["qty_a"] == 20
    assert rows[0]["qty_b"] == 12
    assert rows[0]["total"] == 32
    assert rows[0]["unit_weight_kg"] == 0.25
    assert rows[0]["kg_a"] == 5.0
    assert rows[0]["kg_b"] == 3.0
    assert rows[0]["kg_total"] == 8.0
    assert rows[0]["status"] == "Nos dois"
    assert stats["kg_total"] == 8.0
    assert stats["weight_known"] == 1


def test_missing_in_one_company_is_flagged():
    inventory = [_item("A", "ABC-500", "Produto ABC 500g", 2)]
    rows, _ = consolidate_inventory(inventory, {"A": "Empresa A", "B": "Empresa B"})
    assert rows[0]["status"] == "Somente Empresa A"
    assert rows[0]["kg_total"] == 1.0


def test_unknown_weight_does_not_create_false_kg_total():
    inventory = [_item("A", "RAKU2500", "Rapé Kuntanawa Osmildo", 5)]
    rows, stats = consolidate_inventory(inventory, {"A": "A", "B": "B"})
    assert rows[0]["unit_weight_kg"] is None
    assert rows[0]["kg_total"] is None
    assert "peso não identificado" in rows[0]["status"]
    assert stats["kg_total"] == 0
    assert stats["weight_unknown"] == 1


def test_base_summary_combines_250g_and_500g_variants():
    inventory = [
        _item("A", "RANU06-250", "Rapé Nukini Onça 250g", 20),
        _item("A", "RANU06-500", "Rapé Nukini Onça 500g", 8),
        _item("B", "RANU06-250", "Rapé Nukini Onça 250g", 12),
        _item("B", "RANU06-500", "Rapé Nukini Onça 500g", 4),
    ]
    rows, _ = consolidate_inventory(inventory, {"A": "A", "B": "B"})
    base = consolidate_by_base_product(rows, {"A": "A", "B": "B"})
    assert len(base) == 1
    assert base[0]["base_sku"] == "RANU06"
    assert base[0]["qty_a"] == 28
    assert base[0]["qty_b"] == 16
    assert base[0]["kg_a"] == 9.0
    assert base[0]["kg_b"] == 5.0
    assert base[0]["kg_total"] == 14.0
    assert base[0]["complete"]
