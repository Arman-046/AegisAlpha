import pytest
import datetime
from utils.occ import parse_occ_symbol

def test_occ_normal_symbol():
    res = parse_occ_symbol("AAPL230915C00150000")
    assert res["underlying"] == "AAPL"
    assert res["expiration"] == datetime.date(2023, 9, 15)
    assert res["type"] == "call"
    assert res["strike"] == 150.0

def test_occ_symbol_with_digits():
    res = parse_occ_symbol("3M230915P00100000")
    assert res["underlying"] == "3M"
    assert res["type"] == "put"
    assert res["strike"] == 100.0

def test_occ_malformed_length():
    # Missing some trailing characters
    with pytest.raises(ValueError):
        parse_occ_symbol("AAPL230915C00150")

def test_occ_malformed_date():
    # Invalid date 999999
    with pytest.raises(ValueError):
        parse_occ_symbol("AAPL999999C00150000")

def test_occ_unexpected_format():
    # Just a regular stock ticker
    with pytest.raises(ValueError):
        parse_occ_symbol("AAPL")
