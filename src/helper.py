from massive import RESTClient
from dotenv import load_dotenv
import os
import pandas as pd
import numpy as np
from statsmodels.regression.rolling import RollingOLS
import statsmodels.api as sm
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import date
from heston import get_gbm_percentiles

load_dotenv()

# Data Loading
client = RESTClient(os.getenv("POLYGON_API_KEY"))
def get_polygon_data(ticker, frm = "2015-01-01", to = date.today(), timespan = "day"):
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

def get_heatmap(df):
    # 1. Prepare data (Just copy what we need)
    # We assume df already has 'Year', 'Month', and 'ticker_pct'
    temp = df.copy()[["Year", "Month", "ticker_pct"]]

    # 2. Pivot Directly
    # Since we have Year/Month, we don't need to resample or extract dates.
    # We just group by Year/Month and sum/prod the returns if there are multiple entries,
    # OR if 'ticker_pct' is already monthly, just pivot.
    
    # CASE A: If 'ticker_pct' is DAILY data, we must aggregate it first
    # We group by the existing Year/Month columns and compound the returns
    monthly_df = temp.groupby(['Year', 'Month'])['ticker_pct'].apply(lambda x: (1 + x).prod() - 1).reset_index()

    # CASE B: If 'ticker_pct' is already MONTHLY, just skip to pivoting
    # monthly_df = temp 

    # 3. Pivot: Year (Rows) x Month (Columns)
    heatmap_data = monthly_df.pivot(index='Year', columns='Month', values='ticker_pct')

    # 4. Rename columns (1 -> Jan, etc.)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    month_map = dict(zip(range(1, 13), month_names))
    heatmap_data.rename(columns=month_map, inplace=True)

    # 5. Calculate Stats
    hit_rate = (heatmap_data > 0).sum() / heatmap_data.count()
    hit_rate_row = hit_rate.to_frame(name='Hit Rate').T

    mean_row = heatmap_data.mean().to_frame(name='Average').T

    # 6. Stack & Plot
    final_df = pd.concat([hit_rate_row, mean_row, heatmap_data])

    plt.figure(figsize=(14, 10))
    sns.heatmap(final_df, annot=True, fmt=".1%", cmap="RdYlGn", center=0, linewidths=0.5)
    plt.title('Monthly Seasonality Heatmap')
    plt.show()

# 1. Create the Plot for Regression (Scatter)
def plot_regression_analysis(df):
    plt.figure(figsize=(10, 6))
    
    # Plot historical data points
    plt.scatter(df['bench_pct'], df['ticker_pct'], color='blue', alpha=0.4, label='Historical Returns')

    # Get the latest stats for the line and current point
    latest = df.iloc[-1]
    
    # Draw the OLS Line: y = beta * x + const
    # We create a range of x-values from the min to max of your benchmark returns
    x_range = np.linspace(df['bench_pct'].min(), df['bench_pct'].max(), 100)
    y_range = latest['beta'] * x_range + latest['const']
    
    plt.plot(x_range, y_range, color='black', linestyle='--', label=f'OLS Line (Beta: {latest["beta"]:.2f})')

    # Highlight the current point as a Red Bubble
    plt.scatter(latest['bench_pct'], latest['ticker_pct'], color='red', s=200, 
                edgecolors='black', label='Current Point', zorder=5)

    # Formatting
    plt.axhline(0, color='gray', lw=0.5)
    plt.axvline(0, color='gray', lw=0.5)
    plt.title('Ticker vs Benchmark Returns')
    plt.xlabel('Benchmark % Change')
    plt.ylabel('Ticker % Change')
    plt.legend()
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.show()

# 2. Create the Plot for Residuals (Rich/Cheap Gauge)
def plot_residuals(df):
    plt.figure(figsize=(10, 4))
    
    # Plot the residuals over the index
    plt.bar(df["date"], df['residuals'], color='green', label='Residuals')
    
    # Zero line represents "Fair Value"
    plt.axhline(0, color='red', linestyle='--', label='Fair Value')
    
    plt.title('Residuals over Time')
    plt.xlabel('Record Index')
    plt.ylabel('Residual Value')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()



def get_percentiles(plot_data, year_data, days_left, n_paths = 1000):
    mu = plot_data["ticker_pct"].mean() * 252.0
    sd = plot_data["ticker_pct"].std() * np.sqrt(252.0)

    percentiles = get_gbm_percentiles(plot_data.iloc[-1]["ticker_close"], mu = mu, sd = sd, days_left = days_left)
    
    return percentiles

def main():
    return get_polygon_data("AAPL")

if __name__ == "__main__":
    print(main())
