from qbo_stock.weights import detect_unit_weight_kg, derive_base_sku


def test_detects_250g_from_name():
    result = detect_unit_weight_kg("RANU06250", "Rapé Nukini Onça - Pote 250g")
    assert result.kg == 0.25
    assert result.label == "250 g"
    assert not result.conflict


def test_detects_500g_from_safe_sku_suffix():
    result = detect_unit_weight_kg("RANU06-500", "Rapé Nukini Onça")
    assert result.kg == 0.5
    assert result.label == "500 g"


def test_does_not_guess_weight_from_ambiguous_code():
    result = detect_unit_weight_kg("RAKU2500", "Rapé Kuntanawa Osmildo")
    assert result.kg is None
    assert result.label == "Não identificado"


def test_terminal_kg_means_qty_is_already_in_kg():
    result = detect_unit_weight_kg("RAHK0200", "Rapé Huni Kuin Cacau Kg")
    assert result.kg == 1.0
    assert result.label == "1 kg"


def test_conflicting_name_and_sku_is_flagged():
    result = detect_unit_weight_kg("RANU06-500", "Rapé Nukini Onça 250g")
    assert result.kg is None
    assert result.conflict
    assert result.label == "Conflito"


def test_base_sku_only_removes_safe_suffix():
    assert derive_base_sku("RANU06-250") == "RANU06"
    assert derive_base_sku("RANU06-500G") == "RANU06"
    assert derive_base_sku("RAKU2500") is None
