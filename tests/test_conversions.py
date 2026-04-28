from calculator.conversions import convert_value, parse_inline_conversion


def test_length_conversion():
    converted, category, _ = convert_value(150, "cm", "m")
    assert converted == 1.5
    assert category == "Length"


def test_inline_conversion_parser():
    parsed = parse_inline_conversion("150 lb to kg")
    assert parsed == (150.0, "lb", "kg")
