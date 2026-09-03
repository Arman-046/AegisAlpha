import pytest
import numpy as np
from data.volatility import calculate_realized_volatility_percentile

class DummyBar:
    def __init__(self, c):
        self.close = c

def test_volatility_percentiles():
    # Test high vol
    bars_high = []
    price = 100.0
    for i in range(160):
        price += np.random.normal(0, 0.5)
        bars_high.append(DummyBar(price))
    for i in range(20):
        price += np.random.normal(0, 5.0)
        bars_high.append(DummyBar(price))

    res_high = calculate_realized_volatility_percentile(bars_high)
    assert "EXPENSIVE / HIGH" in res_high

    # Test low vol
    bars_low = []
    price = 100.0
    for i in range(160):
        price += np.random.normal(0, 5.0)
        price = max(price, 10.0)
        bars_low.append(DummyBar(price))
    for i in range(20):
        price += np.random.normal(0, 0.1)
        price = max(price, 10.0)
        bars_low.append(DummyBar(price))

    res_low = calculate_realized_volatility_percentile(bars_low)
    assert "CHEAP / LOW" in res_low
