from massive import RESTClient
from dotenv import load_dotenv
import os
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from statsmodels.regression.rolling import RollingOLS
import statsmodels.api as sm
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import date
import streamlit as st
import yfinance as yf
from investiny import search_assets, historical_data
from datetime import datetime, date

load_dotenv()

# Data Loading
client = RESTClient(st.secrets["POLYGON_API_KEY"])
def get_polygon_data(ticker, frm = "2015-01-01", to = date.today(), timespan = "day"):
    aggs = client.get_aggs(
        ticker=ticker, 
        multiplier=1, 
        timespan=timespan, 
        from_=frm,
        to = to
    )

    df = pd.DataFrame(aggs)[["close", "timestamp"]]
    df["Date"] = pd.to_datetime(df["timestamp"], unit = "ms")
    df = df[["Date", "close"]]
    df.columns = ["Date", "Close"]
    return df

def get_investpy_data(ticker, frm="2015-01-01", to=date.today(), timespan="day"):
    if isinstance(frm, str):
        start_dt = datetime.strptime(frm, "%Y-%m-%d").strftime("%m/%d/%Y")
    else:
        start_dt = frm.strftime("%m/%d/%Y")

    if isinstance(to, str):
        end_dt = datetime.strptime(to, "%Y-%m-%d").strftime("%m/%d/%Y")
    else:
        end_dt = to.strftime("%m/%d/%Y")
    try:
        results = search_assets(query=ticker, limit=1, type="Bond")
        if results:
            investing_id = results[0]["id"]
        else:
            print(f"❌ Bond '{ticker}' not found.")
            return pd.DataFrame()
    except Exception as e:
        print(f"❌ Search Error: {e}")
        return pd.DataFrame()

    try:
        df = historical_data(
            investing_id=investing_id,
            from_date=start_dt,
            to_date=end_dt
        )
    except Exception as e:
        print(f"❌ Fetch Error: {e}")
        return pd.DataFrame()
    
    df.rename(columns={
        "date": "Date", 
        "open": "Open", 
        "high": "High", 
        "low": "Low", 
        "close": "Close"
    }, inplace=True)
    
    df["Date"] = pd.to_datetime(df["Date"])
    
    
    return df[["Date", "Close"]]
    
def get_yfinance_data(ticker, frm = "2015-01-01", to = date.today(), timespan = "day"):
    aggs = yf.download(ticker, start = frm, end = to)
    aggs = aggs.reset_index()
    return aggs[["Date", "Close"]]

@st.cache_data(ttl = 1800) # 30 minutes
def get_data(ticker, asset_type, frm = "2015-01-01", to = date.today()):
    if not ticker or not asset_type:
        return pd.DataFrame()
    if asset_type == "Equity":
        df = get_polygon_data(ticker, frm, to)
    if asset_type == "Bond":
        df = get_investpy_data(ticker, frm, to)
    if asset_type == "FX":
        df = get_yfinance_data(ticker, frm, to)
    
    df["pct_change"] = df["Close"].pct_change()

    return df


def get_rolling_stats(ticker_price, bench_price, window = 20):

    aligned_data = ticker_price[["Date", "Working"]].merge(
        bench_price[["Date", "Working"]], how = "inner", on = "Date"
    )
    aligned_data.set_index("Date", inplace = True)
    aligned_data.columns = ["Y", "X"]
    X = sm.add_constant(aligned_data["X"])
    model = RollingOLS(aligned_data["Y"], X, window = window)
    results = model.fit()
    data = {
        "const": results.params["const"],
        "beta": results.params["X"],
        "p-value": results.pvalues[0:,1],
        "r-squared": results.rsquared 
    }

    return pd.DataFrame(data)

def get_figs(ticker_price, bench_price, labels, window = 20):
    df = get_rolling_stats(ticker_price, bench_price, window = window)

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x = df.index,
        y = df["beta"],
        mode = "lines",
        name = "Rolling Beta"
    ))
    fig1.update_layout(
        title='Rolling Beta',
        yaxis_title='Beta Value',
        xaxis_title='Date',
        height=500, # Matches figsize=(10, 5) approx
        template="plotly_white",  # Explicitly white
        paper_bgcolor="white",    # Force the outer margin to white
        plot_bgcolor="white",     # Force the plotting area to white
        font=dict(color="black"), # Ensure text isn't white-on-white
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x = df.index,
        y = df["r-squared"],
        mode = "lines",
        name = "Rolling R-squared"
    ))
    fig2.update_layout(
        title='Rolling R-squared',
        yaxis_title='R-squared',
        xaxis_title='Date',
        height=500, # Matches figsize=(10, 5) approx
        template="plotly_white",  # Explicitly white
        paper_bgcolor="white",    # Force the outer margin to white
        plot_bgcolor="white",     # Force the plotting area to white
        font=dict(color="black"), # Ensure text isn't white-on-white
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x = df.index,
        y = df["p-value"],
        mode = "lines",
        name = "Rolling p-value"
    ))
    fig3.update_yaxes(type="log")
    fig3.update_layout(
        title='Rolling p-value',
        yaxis_title='p-value',
        xaxis_title='Date',
        height=500, # Matches figsize=(10, 5) approx
        template="plotly_white",  # Explicitly white
        paper_bgcolor="white",    # Force the outer margin to white
        plot_bgcolor="white",     # Force the plotting area to white
        font=dict(color="black"), # Ensure text isn't white-on-white
        margin=dict(l=20, r=20, t=40, b=20)
    )
    df["residuals"] = (
        ticker_price["Working"].values - 
        (df["beta"].values * bench_price["Working"].values + df["const"].values)
    )

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
    x=df.index,
    y=df['residuals'],
    marker_opacity = 1.0,
    name='Residuals',
    hovertemplate='<b>Date</b>: %{x}<br><b>Error</b>: %{y:.4f}<extra></extra>'
    ))

    fig4.add_hline(
        y=0, 
        line_dash="dash", 
        line_color="black", 
        opacity=0.5,
        annotation_text="Fair Value (0)", 
        annotation_position="bottom right"
    )

    # 4. Update Layout
    fig4.update_layout(
        title='Residuals over Time',
        xaxis_title='Date',
        yaxis_title='Residual Value',
        bargap = 0, # Adds a small gap between bars for readability
        template="plotly_white",  # Explicitly white
        paper_bgcolor="white",    # Force the outer margin to white
        plot_bgcolor="white",     # Force the plotting area to white
        font=dict(color="black"), # Ensure text isn't white-on-white
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fig5 = get_regression_plot(ticker_price, bench_price, df, labels)
    return fig1, fig2, fig3, fig4, fig5

def get_heatmap(df):
    # 1. Prepare data
    temp = df.copy()[["Year", "Month", "ticker_pct"]]

    # 2. Aggregate Daily -> Monthly Returns
    # Group by Year/Month and compound the returns: (1+r)*(1+r)... - 1
    monthly_df = temp.groupby(['Year', 'Month'])['ticker_pct'].apply(
        lambda x: (1 + x).prod() - 1
    ).reset_index()

    # 3. Pivot: Year (Rows) x Month (Columns)
    heatmap_data = monthly_df.pivot(index='Year', columns='Month', values='ticker_pct')

    # 4. Rename columns (1 -> Jan, etc.)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    month_map = dict(zip(range(1, 13), month_names))
    heatmap_data.rename(columns=month_map, inplace=True)
    
    # Ensure columns are ordered Jan-Dec (Pivot sometimes messes up order)
    heatmap_data = heatmap_data.reindex(columns=month_names)

    # 5. Calculate Stats
    # Hit Rate: % of months that were positive
    hit_rate = (heatmap_data > 0).sum() / heatmap_data.count()
    hit_rate_row = hit_rate.to_frame(name='Hit Rate').T

    # Average: Mean monthly return
    mean_row = heatmap_data.mean().to_frame(name='Average').T

    # 6. Stack (Hit Rate at top, then Average, then Years)
    # We sort years descending so recent years are near the top (under stats)
    heatmap_data.sort_index(ascending=False, inplace=True)
    final_df = pd.concat([hit_rate_row, mean_row, heatmap_data])
    
    # 7. Create Text Matrix for Annotations (e.g., "5.2%")
    # We map NaN values to empty strings so they don't show as "nan"
    text_template = final_df.applymap(lambda x: f"{x:.1%}" if pd.notnull(x) else "")

    # 8. Plotly Heatmap
    fig = go.Figure(data=go.Heatmap(
        z=final_df.values,
        x=final_df.columns,
        y=final_df.index,
        colorscale='RdYlGn',
        zmid=0,             # Center the color scale at 0%
        text=text_template, # Use our pre-formatted text
        texttemplate="%{text}",
        textfont={"size": 10},
        xgap=1,             # Add white lines between cells
        ygap=1
    ))

    # 9. Layout Updates
    fig.update_layout(
        title='Monthly Seasonality Heatmap',
        yaxis_autorange='reversed', # Put Hit Rate/Average at the top
        height=800,                 # Make it tall enough
        xaxis_title="Month",
        yaxis_title="Year / Metric",
        template="plotly_white"
    )

    return fig

# 1. Create the Plot for Regression (Scatter)
def get_regression_plot(ticker_price, bench_price, ols_data, labels=None):
    fig = go.Figure()
    
    # 1. Prepare Data
    df = ticker_price.merge(bench_price, on="Date", how="inner").dropna()[["Date", "Working_x", "Working_y"]]
    df["Date"] = pd.to_datetime(df["Date"], errors='coerce')

    # 2. EXTRACT EQUATION & CREATE "INFINITE" LINE
    # We grab the latest Beta (Slope) and Const (Intercept)
    m = ols_data["beta"].iloc[-1]
    c = ols_data["const"].iloc[-1]

    # Hardcode the huge range you asked for
    line_x = [-100000, 100000]
    line_y = [m * x + c for x in line_x]

    # Plot this "infinite" line FIRST (so it's behind the dots)
    fig.add_trace(go.Scatter(
        x=line_x,
        y=line_y,
        mode='lines',
        name=f'Current Regime (β={m:.2f})',
        line=dict(color='black', width=2, dash='dash')
    ))

    # 3. Plot the Data Cloud
    fig.add_trace(go.Scatter(
        x=df["Working_x"],
        y=df["Working_y"],
        mode="markers",
        name="History",
        marker=dict(color='rgba(31, 119, 180, 0.5)', size=6),
        hovertemplate='<b>Date</b>: %{text}<br><b>Bench</b>: %{x:.2f}<br><b>Ticker</b>: %{y:.2f}<extra></extra>',
        text=df["Date"].dt.strftime('%Y-%m-%d')
    ))

    # 4. Handle Specific Period Labels (Lines Only)
    if labels:
            colors = ['#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#e377c2']
            for i, (name, (start, end)) in enumerate(labels.items()):
                mask = (df["Date"] >= pd.to_datetime(start)) & (df["Date"] <= pd.to_datetime(end))
                sub_df = df[mask]
                
                if len(sub_df) > 2:
                    color = colors[i % len(colors)]
                    X_sub = sm.add_constant(sub_df["Working_x"])
                    model = sm.OLS(sub_df["Working_y"], X_sub).fit()
                    
                    m_sub = model.params.get("Working_x", 0)
                    c_sub = model.params.get("const", 0)

                    inf_x = [-100000, 100000]
                    inf_y = [m_sub * x + c_sub for x in inf_x]
                    
                    fig.add_trace(go.Scatter(
                        x=inf_x, 
                        y=inf_y, 
                        mode='lines', 
                        name=f"{name} (β={m_sub:.2f})",
                        line=dict(color=color, width=3)
                    ))
    # 5. Plot Red Dot
    latest = df.iloc[-1]
    fig.add_trace(go.Scatter(
        x=[latest["Working_x"]],
        y=[latest["Working_y"]],
        mode='markers',
        name=f'Latest ({latest["Date"].date()})',
        marker=dict(color='red', size=12, symbol='circle', line=dict(width=2, color='white')),
        hovertemplate='<b>LATEST</b><br>Bench: %{x:.2f}<br>Ticker: %{y:.2f}<extra></extra>'
    ))

    # 6. FORCE THE CAMERA TO ZOOM IN ON THE DATA
    # If we don't do this, the chart will show -100k to +100k and your data will be invisible.
    x_min, x_max = df["Working_x"].min(), df["Working_x"].max()
    y_min, y_max = df["Working_y"].min(), df["Working_y"].max()
    
    pad_x = (x_max - x_min) * 0.1
    pad_y = (y_max - y_min) * 0.1

    fig.update_layout(
        title="Regression Analysis",
        xaxis_title="Benchmark",
        yaxis_title="Ticker",
        template="plotly_white",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        # LOCK THE VIEW
        xaxis=dict(range=[x_min - pad_x, x_max + pad_x], constrain='domain'), 
        yaxis=dict(range=[y_min - pad_y, y_max + pad_y], constrain='domain')
    )

    return fig

def main():
    return get_polygon_data("AAPL")

if __name__ == "__main__":
    print(main())
