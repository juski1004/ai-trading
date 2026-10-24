from ai_trading.data.prices import parse


def row(code, name, price, end="stock", stop="TRADING", tradable="tradable", at="2026-10-23T20:20:22+09:00"):
    return {"stockEndType": end, "itemCode": code, "stockName": name, "closePrice": price, "fluctuationsRatio": "-0.47",
            "accumulatedTradingVolume": "16,019,854", "marketValue": "12,481,805", "localTradedAt": at,
            "tradeStopType": {"name": stop}, "tradableStatus": tradable}


def test_parse_keeps_stocks_only_and_flags_halts():
    out = parse([row("005930", "삼성전자", "213,500"), row("069500", "KODEX 200", "40,000", end="etf"),
                 row("000660", "SK하이닉스", "1,263,000", stop="STOP")], "KOSPI")
    assert set(out) == {"005930.KS", "000660.KS"}
    assert out["005930.KS"]["price"] == 213500 and out["005930.KS"]["halt"] is False
    assert out["000660.KS"]["halt"] is True


def test_parse_kosdaq_suffix():
    assert list(parse([row("247540", "에코프로비엠", "100,000")], "KOSDAQ")) == ["247540.KQ"]
