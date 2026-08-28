from __future__ import annotations

from .consolidation import normalize_sku


def _item(item_id: str, sku: str, name: str, qty: float) -> dict:
    key, _ = normalize_sku(sku, name)
    return {
        "item_id": item_id,
        "sku": sku,
        "normalized_sku": key,
        "name": name,
        "qty_on_hand": qty,
        "item_type": "Inventory",
        "track_qty_on_hand": True,
        "active": True,
    }


DEMO_ITEMS = {
    "A": [
        _item("A-1", "RANU06-250", "Rapé Nukini Onça - Pote 250g", 20),
        _item("A-2", "RANU06-500", "Rapé Nukini Onça - Pote 500g", 8),
        _item("A-3", "RAYA02-250", "Rapé Yawanawa Força Feminina 250g", 30),
        _item("A-4", "RAYA02-500", "Rapé Yawanawa Força Feminina 500g", 10),
        _item("A-5", "RAHK0200", "Rapé Huni Kuin Cacau Kg", 11.12),
    ],
    "B": [
        _item("B-1", "RANU06-250", "Nukini Ojo de Jaguar - 250 g", 12),
        _item("B-2", "RANU06-500", "Nukini Ojo de Jaguar - 500 g", 4),
        _item("B-3", "RAYA02-250", "Yawanawa Feminine Force 250g", 16),
        _item("B-4", "RAYA02-500", "Yawanawa Feminine Force 500g", 6),
        _item("B-5", "RAHK0200", "Huni Kuin Cacao Warrior Heart Kg", 4.80),
        _item("B-6", "SEM-PESO", "Produto para revisar", 5),
    ],
}
