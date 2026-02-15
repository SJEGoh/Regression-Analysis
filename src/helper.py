from massive import RESTClient
from dotenv import load_dotenv
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from statsmodels.regression.rolling import RollingOLS
import statsmodels.api as sm
from datetime import date
import streamlit as st
import yfinance as yf
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
        to = to,
        adjusted = True
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
    x=df.iloc[-63:].index,
    y=df.iloc[-63:]['residuals'],
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

def get_heatmap(df, mode="Differences"):
    temp = df.copy()[["Date", "Working"]]
    temp["Month"] = temp["Date"].dt.month
    temp["Year"] = temp["Date"].dt.year
    
    is_diff = "diff" in str(mode).lower() 
    
    if is_diff:
        monthly_df = temp.groupby(["Year", "Month"])["Working"].apply(
            lambda x: (1 + x).prod() - 1
        ).reset_index()
        val_fmt = ".1%"
        color_scale = 'RdYlGn'
        z_mid = 0
    else:
        monthly_df = temp.groupby(["Year", "Month"])["Working"].last().reset_index()
        val_fmt = ".1f"
        color_scale = 'Viridis' 
        z_mid = None

    heatmap_data = monthly_df.pivot(index='Year', columns='Month', values='Working')
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    month_map = dict(zip(range(1, 13), month_names))
    heatmap_data.rename(columns=month_map, inplace=True)
    heatmap_data = heatmap_data.reindex(columns=month_names)

    heatmap_data.sort_index(ascending=False, inplace=True)
    
    if is_diff:
        hit_rate = (heatmap_data > 0).sum() / heatmap_data.count()
        hit_rate_row = hit_rate.to_frame(name='Hit Rate').T
        mean_row = heatmap_data.mean().to_frame(name='Average').T
        final_df = pd.concat([hit_rate_row, mean_row, heatmap_data])
    else:
        final_df = heatmap_data

    final_df.index = final_df.index.astype(str) 
    text_template = final_df.map(lambda x: f"{x:{val_fmt}}" if pd.notnull(x) else "")

    fig = go.Figure(data=go.Heatmap(
        z=final_df.values,
        x=final_df.columns,
        y=final_df.index,
        colorscale=color_scale,
        zmid=z_mid,
        text=text_template,
        texttemplate="%{text}",
        textfont={"size": 10},
        xgap=1,
        ygap=1
    ))

    fig.update_layout(
        title=f'Monthly Seasonality Heatmap ({mode})',
        xaxis_nticks=12,
        yaxis=dict(type='category', tickmode='linear', autorange="reversed"),
        height=800,
        margin=dict(t=80, b=20, l=100, r=20),
        template="plotly_white"
    )

    return fig


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
                        line=dict(color=color, width=3, dash = "dash")
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
        template="plotly_white",  # Explicitly white
        paper_bgcolor="white",    # Force the outer margin to white
        plot_bgcolor="white",     # Force the plotting area to white
        font=dict(color="black"), # Ensure text isn't white-on-white
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(range=[x_min - pad_x, x_max + pad_x], constrain='domain'), 
        yaxis=dict(range=[y_min - pad_y, y_max + pad_y], constrain='domain')
    )

    return fig

def get_annual_series(ticker_price):
    temp = ticker_price.copy()
    temp["Year"] = temp["Date"].dt.year
    print(temp[temp["Year"] == 2026]["Working"].head(20))

    fig = go.Figure()
    for i, y in enumerate(x := temp["Year"].unique()[-3:-1]):
        curr = temp[temp["Year"] == y]
        curr["Date"] = curr["Date"] + pd.DateOffset(years = len(x) - i)
        fig.add_trace(go.Scatter(
            x = curr["Date"],
            y = curr["Close"]/curr.iloc[0]["Close"] - 1,
            mode = "lines",
            name = f"{y}"
        ))
    
    curr = temp[temp["Year"] == date.today().year]
    fig.add_trace(go.Scatter(
        x = curr["Date"],
        y = curr["Close"]/curr.iloc[0]["Close"] - 1,
        mode = "lines",
        name = date.today().year
    ))
    fig.update_layout(
        title='Monthly Returns Overlay',
        xaxis_title='Date',
        # ADD THIS BLOCK:
        yaxis=dict(
            title='Cumulative Return',
            tickformat='.0%' # Use '.1%' if you want one decimal place (e.g., 5.2%)
        ),
        template="plotly_white",  # Explicitly white
        paper_bgcolor="white",    # Force the outer margin to white
        plot_bgcolor="white",     # Force the plotting area to white
        font=dict(color="black"), # Ensure text isn't white-on-white
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    
    return fig

def get_monthly_series(ticker_price):
    temp = ticker_price.copy()
    temp["Year"] = temp["Date"].dt.year
    temp["Month"] = temp["Date"].dt.month
    temp = temp[temp["Month"] == date.today().month]

    fig = go.Figure()
    for i, y in enumerate(x := temp["Year"].unique()[-3:-1]):
        curr = temp[temp["Year"] == y]
        curr["Date"] = curr["Date"] + pd.DateOffset(years = len(x) - i)
        fig.add_trace(go.Scatter(
            x = curr["Date"],
            y = curr["Close"]/curr.iloc[0]["Close"] - 1,
            mode = "lines",
            name = f"{y}"
        ))
    
    curr = temp[temp["Year"] == date.today().year]
    fig.add_trace(go.Scatter(
        x = curr["Date"],
        y = curr["Close"]/curr.iloc[0]["Close"] - 1,
        mode = "lines",
        name = date.today().year
    ))
    fig.update_layout(
        title='Annual Returns Overlay',
        xaxis_title='Date',
        # ADD THIS BLOCK:
        yaxis=dict(
            title='Cumulative Return',
            tickformat='.0%' # Use '.1%' if you want one decimal place (e.g., 5.2%)
        ),
        template="plotly_white",  # Explicitly white
        paper_bgcolor="white",    # Force the outer margin to white
        plot_bgcolor="white",     # Force the plotting area to white
        font=dict(color="black"), # Ensure text isn't white-on-white
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    
    return fig



# Experiments
def get_types():
    details = client.get_ticker_details("2800")
    print(f"Ticker: {details.ticker}, Name: {details.name}, Market: {details.market}")

def find_hsi_etf():
    # This searches the whole database for 'Hang Seng'
    search_results = client.list_tickers(
        market="stocks", 
        search="Hang Seng", 
        active=True
    )
    
    for ticker in search_results:
        print(f"Ticker: {ticker.ticker} | Name: {ticker.name} | Locale: {ticker.locale}")

import pandas as pd
import requests
import io
import pandas_datareader.data as web
def get_stooq_macro(ticker):
    """
    Argentina 3Y: '3AR.B'
    SPY: 'SPY.US'
    """
    try:
        # data_source='stooq' is the key here
        df = web.DataReader(ticker, 'stooq')
        
        # Stooq returns data in reverse chronological order; sort it for analysis
        df = df.sort_index()
        
        if df.empty:
            print(f"Warning: No data returned for {ticker}")
            return None
            
        return df
    except Exception as e:
        print(f"Error fetching {ticker} via pandas_datareader: {e}")
        return None



def main():
    arg_3y = get_stooq_macro('5YCAP.B')
    spy = get_stooq_macro('SPY.US')

    print(arg_3y)


if __name__ == "__main__":
    print(main())
