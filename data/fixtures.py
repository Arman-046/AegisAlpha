import datetime

class MockBar:
    def __init__(self, close: float):
        self.close = close

class MockEnum:
    def __init__(self, value: str):
        self.value = value

class MockContract:
    def __init__(self, symbol: str, type_val: str, expiration_date: str):
        self.symbol = symbol
        self.type = MockEnum(type_val)
        self.expiration_date = expiration_date

class MockQuote:
    def __init__(self, bid_price: float, ask_price: float):
        self.bid_price = bid_price
        self.ask_price = ask_price

class MockGreeks:
    def __init__(self, delta: float):
        self.delta = delta

class MockSnapshot:
    def __init__(self, latest_quote: MockQuote, open_interest: int = 100, delta: float = 0.5):
        self.latest_quote = latest_quote
        self.open_interest = open_interest
        self.implied_volatility = 0.45
        self.greeks = MockGreeks(delta) if delta is not None else None

def _get_target_date(days_ahead: int) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).date()
    target = now + datetime.timedelta(days=days_ahead)
    return target.strftime("%Y-%m-%d")

def get_mock_stock_bars(symbol: str):
    # Volatility needs at least 40 bars. We return ~50 bars.
    # We can fake a low vol regime for AAPL, high vol for TSLA, normal for NVDA.
    if symbol == "AAPL":
        return [MockBar(150.0 + (i * 0.1)) for i in range(50)]
    elif symbol == "TSLA":
        return [MockBar(200.0 + (i % 5) * 5.0) for i in range(50)]
    return [MockBar(100.0 + (i % 2)) for i in range(50)]

def get_mock_news(symbol: str):
    return ["Mock news article 1", "Mock news article 2", "Mock news article 3"]

def get_mock_option_contracts(symbol: str):
    if symbol == "AAPL":
        return [MockContract("AAPL240101C00150000", "call", _get_target_date(30))]
    elif symbol == "TSLA":
        return [MockContract("TSLA240101P00200000", "put", _get_target_date(30))]
    elif symbol == "NVDA":
        return [MockContract("NVDA240101C00100000", "call", _get_target_date(30))]
    return []

def get_mock_option_snapshots(symbols: list):
    res = {}
    for sym in symbols:
        if sym.startswith("AAPL"):
            # Scenario A: Approved Trade. 
            # 1 contract @ $0.15 = $15 max loss. Spread is small. Delta is 0.5.
            res[sym] = MockSnapshot(MockQuote(0.14, 0.15), 500, 0.5)
        elif sym.startswith("TSLA"):
            # Scenario B: Risk Rejection.
            # 1 contract @ $2.50 = $250 max loss. Spread is small. Delta is -0.5.
            res[sym] = MockSnapshot(MockQuote(2.40, 2.50), 500, -0.5)
        elif sym.startswith("NVDA"):
            # Scenario C: Data Rejection.
            # Invalid quote data (bid <= 0).
            res[sym] = MockSnapshot(MockQuote(0.00, 0.10), 10, None)
    return res
