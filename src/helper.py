from massive import RESTClient
from dotenv import load_dotenv
import os
import pandas as pd
import numpy as np
from statsmodels.regression.rolling import RollingOLS
import statsmodels.api as sm

load_dotenv()

# Data Loading
client = RESTClient(os.getenv("POLYGON_API_KEY"))
def get_polygon_data(ticker, frm = "2023-01-01", to = "2025-01-01", timespan = "day"):
    aggs = client.get_aggs(
        ticker=ticker, 
        multiplier=1, 
        timespan=timespan, 
        from_=frm,
        to = to
    )

    return pd.DataFrame(aggs)

def get_rolling_beta(ticker_price, bench_price, window = 20):
    ticker_pct = ticker_price["ticker_pct"].dropna()
    bench_pct = bench_price["bench_pct"].dropna()
    return ticker_pct.rolling(window).cov(bench_pct)/bench_pct.rolling(window).var()

def get_rolling_stats(ticker_price, bench_price, window = 20):
    X = sm.add_constant(bench_price["bench_pct"])
    model = RollingOLS(ticker_price["ticker_pct"], X, window = window)
    results = model.fit()

    data = {
        "const": results.params["const"],
        "beta": results.params["bench_pct"],
        "p-value": results.pvalues[0:,1],
        "r-squared": results.rsquared 
    }

    return pd.DataFrame(data)

def main():
    return get_polygon_data("AAPL")

if __name__ == "__main__":
    print(main())
