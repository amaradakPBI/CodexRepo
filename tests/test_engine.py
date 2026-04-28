from calculator.engine import CalculatorEngine, display_in_bases


def build_engine():
    return CalculatorEngine()


def test_scientific_trig_respects_degree_mode():
    engine = build_engine()
    result = engine.evaluate(
        "sin(30)",
        mode="Scientific",
        angle_unit="Degree",
        precision=6,
        display_format="Decimal",
        word_size=64,
        variables={},
        ans=0,
    )
    assert result.display == "0.5"


def test_assignment_returns_variable_name():
    engine = build_engine()
    result = engine.evaluate(
        "x = 42",
        mode="Scientific",
        angle_unit="Degree",
        precision=6,
        display_format="Decimal",
        word_size=64,
        variables={},
        ans=0,
    )
    assert result.assigned_variable == "x"
    assert result.display == "42"


def test_programmer_mode_formats_all_bases():
    result = display_in_bases(15, 8)
    assert result["BIN"] == "00001111"
    assert result["HEX"] == "0F"
