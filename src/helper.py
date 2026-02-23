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
import pandas_datareader.data as web
import re
from plotly.subplots import make_subplots

# Index mapping
INDEXES = {
    "SPX": "SPY",
    "HSI": "KTEC",
    "KOSPI": "EWY",

}

load_dotenv()

# Data Loading
client = RESTClient(st.secrets["POLYGON_API_KEY"])
def get_polygon_data(ticker, frm = "2015-01-01", to = date.today(), timespan = "day"):
    if ticker in INDEXES.keys():
        st.write(f"Mapping {ticker} to {INDEXES[ticker]}.")
        ticker = INDEXES[ticker]
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
    
def get_yfinance_data(ticker, frm="2015-01-01", to=date.today(), timespan="day"):
    # 1. Download data
    ticker = ticker + "=X"
    aggs = yf.download(ticker, start=frm, end=to)
    
    # 2. Fix the MultiIndex Column Error
    # If the columns are MultiIndex, collapse them to the Price Level (Close, Open, etc.)
    if isinstance(aggs.columns, pd.MultiIndex):
        aggs.columns = aggs.columns.get_level_values(0) 
    
    # 3. Clean up the 'Date' column and index
    aggs = aggs.reset_index()
    
    # Standardize the 'Date' column name (yfinance sometimes uses 'Date' or 'index')
    if 'Date' not in aggs.columns:
        aggs.rename(columns={aggs.columns[0]: 'Date'}, inplace=True)
        
    return aggs[["Date", "Close"]]

@st.cache_data(ttl = 1800) # 30 minutes
def get_data(ticker, asset_type, frm = "2015-01-01", to = date.today()):
    if not ticker or not asset_type:
        return pd.DataFrame()
    if asset_type == "Equity":
        df = get_polygon_data(ticker, frm, to)
    if asset_type == "Bond":
        df = get_bond_data(ticker)
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize() + pd.Timedelta(hours=5)
    if asset_type == "FX":
        df = get_yfinance_data(ticker, frm, to)
    if asset_type == "Bond Spread":
        df = get_spread(ticker)
    if asset_type == "Bond" or asset_type == "Bond Spread":
        df["pct_change"] = df["Close"].diff()
    else:
        df["pct_change"] = df["Close"].pct_change()

    return df


def get_rolling_stats(t_price, b_price, window = 20):
    ticker_price = t_price.copy()
    bench_price = b_price.copy()
    ticker_price['Date'] = pd.to_datetime(ticker_price['Date'])
    bench_price['Date'] = pd.to_datetime(bench_price['Date'])
    aligned_data = ticker_price[["Date", "Working"]].merge(
        bench_price[["Date", "Working"]], how = "inner", on = "Date"
    )
    aligned_data.set_index("Date", inplace = True)
    aligned_data.columns = ["Y", "X"]
    aligned_data = aligned_data.replace([np.inf, -np.inf], np.nan).dropna(subset=["Y", "X"])
    aligned_data = aligned_data.dropna(subset=['Y', 'X'])
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

def get_figs(t_price, b_price, labels, ticker_x, ticker_y, window = 20, rolling_period = 30):
    ticker_price = t_price.copy()
    bench_price = b_price.copy()
    ticker_price['Date'] = pd.to_datetime(ticker_price['Date']).dt.normalize()
    bench_price['Date'] = pd.to_datetime(bench_price['Date']).dt.normalize()
    aligned = pd.merge(ticker_price, bench_price, on="Date", suffixes=('', '_bench'))
    ticker_price = aligned[["Date", "Working"]]
    bench_price = aligned[["Date", "Working_bench"]].rename(columns={"Working_bench": "Working"})
    df = get_rolling_stats(ticker_price, bench_price, window = window)
    df = df.merge(bench_price, on = "Date", how = "inner")
    df = df.merge(ticker_price, on = "Date", how = "inner", suffixes = ("_bench", "_ticker"))
    df.loc[:, 'residuals'] = (
        df["Working_ticker"].values - 
        (df["beta"].values * df["Working_bench"].values + df["const"].values)
    )
    working = df.iloc[-rolling_period:]
    x=len(df.dropna())
    st.write(f"Max days: {x}")
    if rolling_period > x:
        st.write("Choose smaller number.")
        st.stop()
    
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x = working["Date"],
        y = working["beta"],
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
        x = working["Date"],
        y = working["r-squared"],
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
        x = working["Date"],
        y = working["p-value"],
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

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
    x=working.index,
    y=working['residuals'],
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
    fig5 = get_regression_plot(ticker_price, bench_price, df, ticker_x, ticker_y, labels)
    return fig1, fig2, fig3, fig4, fig5


def get_heatmap(df, asset_type="Equity", mode="Differences"):
    temp = df.copy()[["Date", "pct_change"]]
    temp["Month"] = temp["Date"].dt.month
    temp["Year"] = temp["Date"].dt.year
    
    is_diff = "diff" in str(mode).lower() 
    is_bond = asset_type in ["Bond", "Bond Spread"]
    
    # 1. Metric Calculation
    if is_diff:
        if is_bond:
            monthly_df = temp.groupby(["Year", "Month"])["pct_change"].apply(
                lambda x: x.diff().sum() * 100
            ).reset_index()
            val_fmt = ".1f"
        else:
            monthly_df = temp.groupby(["Year", "Month"])["pct_change"].apply(
                lambda x: (1 + x).prod() - 1
            ).reset_index()
            val_fmt = ".1%"
        color_scale = 'RdYlGn'
        z_mid = 0
    else:
        monthly_df = temp.groupby(["Year", "Month"])["pct_change"].last().reset_index()
        val_fmt = ".1f"
        color_scale = 'Viridis' 
        z_mid = None

    # 2. Pivot and Structure
    heatmap_data = monthly_df.pivot(index='Year', columns='Month', values='pct_change')
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    heatmap_data = heatmap_data.reindex(columns=range(1, 13))
    heatmap_data.columns = month_names
    heatmap_data.sort_index(ascending=False, inplace=True)
    
    if is_diff:
        hit_rate = (heatmap_data > 0).sum() / heatmap_data.count()
        mean_row = heatmap_data.mean().to_frame(name='Average').T
        final_df = pd.concat([hit_rate.to_frame(name='Hit Rate').T, mean_row, heatmap_data])
    else:
        final_df = heatmap_data

    # 3. FIX: Row-by-Row Standardization with Absolute Hit Rate Scaling
    def standardize_row(row):
        # Map Hit Rate 0.0-1.0 to color scale -1 to 1 (0.5 is neutral/white)
        if "Hit Rate" in str(row.name):
            return (row * 2) - 1 
            
        std = row.std()
        if pd.isna(std) or std == 0:
            return row - row.mean()
        return (row - row.mean()) / std

    z_values = final_df.apply(standardize_row, axis=1)

    # 4. Text Template with RAW VALUES
    final_df.index = final_df.index.astype(str) 
    text_template = final_df.astype(object).copy()
    for row in text_template.index:
        fmt = ".1%" if "Hit Rate" in row else val_fmt
        text_template.loc[row] = final_df.loc[row].map(
            lambda x: f"{x:{fmt}}" if pd.notnull(x) else ""
        )

    # 5. Build Figure
    fig = go.Figure(data=go.Heatmap(
        z=z_values.values,
        text=text_template.values,
        x=final_df.columns,
        y=final_df.index,
        colorscale=color_scale,
        zmid=z_mid,
        zmin=-1, zmax=1,             # Fixes the range for standardized rows
        texttemplate="%{text}",
        textfont={"size": 10},
        xgap=1, ygap=1,
        showscale=False
    ))

    fig.update_layout(
        title=f'Monthly Seasonality: {asset_type} (Row-Standardized, Absolute Hit Rate)',
        xaxis_nticks=12,
        yaxis=dict(type='category', tickmode='linear', autorange="reversed"),
        height=400 + (len(final_df) * 25),
        margin=dict(t=80, b=20, l=100, r=20),
        template="plotly_white"
    )

    return fig

def get_regression_plot(ticker_price, bench_price, ols_data, ticker_x, ticker_y, labels=None):
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
    fig.add_trace(go.Scatter(
        x=line_x,
        y=line_y,
        mode='lines',
        name=f'Current Regime (β={m:.2f})',
        line=dict(color='black', width=2, dash='dash')
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
                        x=sub_df["Working_x"],
                        y=sub_df["Working_y"],
                        mode='markers',
                        name=f"{name} Dots",
                        marker=dict(color=color, size=7, opacity=0.8),
                        showlegend=False # Keep legend clean
                    ))

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
        xaxis_title=ticker_x,
        yaxis_title=ticker_y,
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

def get_annual_series(ticker_price, asset_type = "Equity"):
    if asset_type in ["Bond", "Bond Spread"]:
        y_title = "Cumulative Change (bps)"
        y_format = ".1f"  # Shows 5.0 instead of 500%
        val_suffix = "bps"
    else:
        y_title = "Cumulative Return (%)"
        y_format = ".2%"  
        val_suffix = ""
    temp = ticker_price.copy()
    temp["Year"] = temp["Date"].dt.year

    fig = go.Figure()
    for i, y in enumerate(x := temp["Year"].unique()[-3:-1]):
        curr = temp[temp["Year"] == y].copy() # copy to avoid slice warnings
        curr["Date"] = curr["Date"] + pd.DateOffset(years = len(x) - i)
        
        # Logic swap: Difference * 100 for bonds, pct change for equities
        y_vals = (curr["Close"] - curr.iloc[0]["Close"]) * 100 if val_suffix == "bps" else curr["Close"]/curr.iloc[0]["Close"] - 1
        
        fig.add_trace(go.Scatter(
            x = curr["Date"],
            y = y_vals,
            mode = "lines",
            name = f"{y}"
        ))
    
    curr = temp[temp["Year"] == date.today().year].copy()
    y_vals = (curr["Close"] - curr.iloc[0]["Close"]) * 100 if val_suffix == "bps" else curr["Close"]/curr.iloc[0]["Close"] - 1
    
    fig.add_trace(go.Scatter(
        x = curr["Date"],
        y = y_vals,
        mode = "lines",
        name = date.today().year
    ))
    fig.update_layout(
        title='Annual Returns Overlay',
        xaxis_title='Date',
        yaxis=dict(
            title=y_title,
            tickformat=y_format
        ),
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="black"),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )


    return fig

def get_monthly_series(ticker_price, asset_type="Equity", mode="Difference"):
    if asset_type in ["Bond", "Bond Spread"]:
        y_title, y_format, val_suffix = "Cumulative Change (bps)", ".1f", "bps"
    else:
        y_title, y_format, val_suffix = "Cumulative Return (%)", ".2%", ""

    temp = ticker_price.copy()
    temp["Year"] = temp["Date"].dt.year
    temp["Month"] = temp["Date"].dt.month
    temp = temp[temp["Month"] == date.today().month]

    fig = go.Figure()
    # Logic for Cumulative Changes (Bips vs %)
    if mode == "Difference":
        for i, y in enumerate(x := temp["Year"].unique()[-3:-1]):
            curr = temp[temp["Year"] == y].copy()
            curr["Date"] = curr["Date"] + pd.DateOffset(years = len(x) - i)
            y_vals = (curr["Close"] - curr.iloc[0]["Close"]) * 100 if val_suffix == "bps" else curr["Close"]/curr.iloc[0]["Close"] - 1
            fig.add_trace(go.Scatter(x=curr["Date"], y=y_vals, mode="lines", name=f"{y}"))
        
        curr = temp[temp["Year"] == date.today().year].copy()
        y_vals = (curr["Close"] - curr.iloc[0]["Close"]) * 100 if val_suffix == "bps" else curr["Close"]/curr.iloc[0]["Close"] - 1
        fig.add_trace(go.Scatter(x=curr["Date"], y=y_vals, mode="lines", name=date.today().year))
        
        y_axis_config = dict(title=y_title, tickformat=y_format)

    # Logic for Absolute Levels (Yield % vs Price)
    else:
        for i, y in enumerate(x := temp["Year"].unique()[-3:-1]):
            curr = temp[temp["Year"] == y].copy()
            curr["Date"] = curr["Date"] + pd.DateOffset(years = len(x) - i)
            fig.add_trace(go.Scatter(x=curr["Date"], y=curr["Close"], mode="lines", name=f"{y}"))
        
        curr = temp[temp["Year"] == date.today().year].copy()
        fig.add_trace(go.Scatter(x=curr["Date"], y=curr["Close"], mode="lines", name=date.today().year))
        
        y_axis_config = dict(title='Yield %' if val_suffix == "bps" else 'Price', tickformat='.2f')

    fig.update_layout(
        title=f'Monthly Overlay (Month {date.today().month}) - {mode}',
        xaxis_title='Date',
        yaxis=y_axis_config,
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="black"),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    
    return fig

# single asset page
def multiple_heatmap(df, event_data, asset_type="Equity"):
    # 1. Setup Formatting Logic
    if asset_type in ["Bond", "Bond Spread"]:
        y_format = ".1f"
        val_suffix = "bps"
    else:
        y_format = ".2%"
        val_suffix = ""

    heatmap_rows = []
    max_d = int(max([val[1] for val in event_data.values()]))
    full_rel_days = list(range(-max_d, max_d + 1))
    df = df.reset_index(drop=True)

    # 2. Extract Event Windows
    for event_name, (target_date, d) in event_data.items():
        d = int(d)
        target_dt = pd.to_datetime(target_date)
        
        idx_matches = df.index[df['Date'] == target_dt]
        idx = idx_matches[0] if len(idx_matches) > 0 else (df['Date'] - target_dt).abs().idxmin()
        
        base_price = df.loc[idx, 'Working']
        for r_day in range(-max_d, max_d + 1): # Fill the full range for alignment
            g_idx = idx + r_day
            ret = np.nan
            if 0 <= g_idx < len(df) and abs(r_day) <= d:
                if asset_type in ["Equity", "FX"]:
                    ret = (df.loc[g_idx, 'Working'] / base_price - 1)
                else: 
                    ret = (df.loc[g_idx, 'Working'] - base_price) * 100
            heatmap_rows.append({'Event': event_name, 'Rel_Day': r_day, 'Return': ret})

    # 3. Structure Final DataFrame
    plot_df = pd.DataFrame(heatmap_rows)
    pivot_df = plot_df.pivot(index="Event", columns="Rel_Day", values="Return")
    pivot_df = pivot_df.reindex(columns=full_rel_days)

    hit_rate = (pivot_df > 0).sum() / pivot_df.count()
    mean_row = pivot_df.mean().to_frame(name='Mean Return').T
    
    # Merge Stats and Events into one DF for consistent indexing
    final_df = pd.concat([hit_rate.to_frame(name='Hit Rate (%)').T, mean_row, pivot_df])
    final_df.index = final_df.index.astype(str)

    # 4. ROW-BY-ROW STANDARDIZATION (Colors Only)
    def standardize_row(row):
        # Scale Hit Rate 0-1 into -1 to 1 spectrum
        if "Hit Rate" in str(row.name):
            return (row * 2) - 1
        std = row.std()
        if pd.isna(std) or std == 0:
            return row.fillna(0) - row.mean()
        return (row - row.mean()) / std

    z_values = final_df.apply(standardize_row, axis=1)

    # 5. TEXT TEMPLATE (Raw Values Only)
    text_template = final_df.astype(object).copy()
    for row in text_template.index:
        fmt = ".1%" if "Hit Rate" in row else y_format
        text_template.loc[row] = final_df.loc[row].map(
            lambda x: f"{x:{fmt}}" if pd.notnull(x) else ""
        )

    # 6. Build Figure (Single Heatmap instead of Subplots for "Style Sync")
    fig = go.Figure(data=go.Heatmap(
        z=z_values.values,           # The standardization drives the color intensity
        text=text_template.values,   # The raw bps/% drive the text labels
        x=final_df.columns,
        y=final_df.index,
        colorscale='RdYlGn',
        zmid=0,
        zmin=-1, zmax=1,             # Fixes the scale for standardized rows
        texttemplate="%{text}",
        xgap=1, ygap=1,
        showscale=False
    ))

    fig.update_layout(
        title=f"Event Analysis: T-{max_d} to T+{max_d} ({asset_type})",
        xaxis_title="Relative Days from Event",
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="black"),
        height=400 + (len(final_df) * 25),
        yaxis=dict(autorange='reversed', type='category')
    )

    return fig

def multiple_line_plot(df, event_data, asset_type = "Equity"):
    fig = go.Figure()
    max_d = int(max([val[1] for val in event_data.values()]))
    df = df.reset_index(drop=True)
    if asset_type in ["Bond", "Bond Spread"]:
        y_title = "Cumulative Change (bps)"
        y_format = ".1f"  # Shows 5.0 instead of 500%
        val_suffix = "bps"
    else:
        y_title = "Cumulative Return (%)"
        y_format = ".2%"  
        val_suffix = ""
    # Store returns for mean calculation
    all_returns = {d: [] for d in range(-max_d, max_d + 1)}

    for event_name, (target_date, d) in event_data.items():
        d = int(d)
        target_dt = pd.to_datetime(target_date)
        
        idx_matches = df.index[df['Date'] == target_dt]
        idx = idx_matches[0] if len(idx_matches) > 0 else (df['Date'] - target_dt).abs().idxmin()
        
        rel_days = np.arange(-d, d + 1)
        window_indices = np.arange(idx - d, idx + d + 1)
        base_price = df.loc[idx, 'Working']
        
        y_values, x_values = [], []
        
        for r_day, g_idx in zip(rel_days, window_indices):
            if 0 <= g_idx < len(df):
                if asset_type == "Equity" or asset_type == "FX":
                    ret = (df.loc[g_idx, 'Working'] / base_price - 1)
                else: 
                    ret = (df.loc[g_idx, 'Working'] - base_price) * 100
                y_values.append(ret)
                x_values.append(r_day)
                all_returns[r_day].append(ret)
        
        # Determine line style: Dotted if "Current", otherwise solid
        is_current = (event_name == "Current")
        
        line_style = dict(
            width=2, 
            dash='dot' if is_current else 'solid', 
        )

        fig.add_trace(go.Scatter(
            x=x_values, y=y_values,
            mode='lines',
            opacity=0.8 if is_current else 0.2,
            name=event_name,
            line=line_style,
            hovertemplate=(
                    f"<b>{event_name}</b><br>"
                    f"Day: T%{{x}}<br>"
                    f"Change: %{{y:{y_format}}}{val_suffix}"
                    "<extra></extra>"
                )
            ))

    # Calculate and add the Mean Line (Average)
    mean_x = sorted(all_returns.keys())
    mean_y = [np.mean(all_returns[day]) if all_returns[day] else np.nan for day in mean_x]

    fig.add_trace(go.Scatter(
        x=mean_x, y=mean_y,
        mode='lines',
        name='AVERAGE MOVE',
        line=dict(color='black', width=4), 
        hovertemplate=(
            f"<b>{event_name}</b><br>"
            f"Day: T%{{x}}<br>"
            f"Change: %{{y:{y_format}}}{val_suffix}"
            "<extra></extra>"
        )
    ))

    # Layout configurations
    fig.update_layout(
        title=f"Seasonality Drift: T-{max_d} to T+{max_d}",
        xaxis=dict(title="Days from Event (T=0)", tickmode='linear', dtick=1, range=[-max_d, max_d]),
        yaxis=dict(title=y_title, tickformat=y_format, zeroline=True, zerolinewidth=1.5, zerolinecolor='gray'),
        template="plotly_white",  # Explicitly white
        paper_bgcolor="white",    # Force the outer margin to white
        plot_bgcolor="white",     # Force the plotting area to white
        font=dict(color="black"), # Ensure text isn't white-on-white
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified"
    )

    fig.add_vline(x=0, line_dash="dash", line_color="red", line_width=2)
    
    return fig

def get_stooq_macro(ticker):
    STOOQ_BOND_MAP = {
        # --- NORTH AMERICA ---
        "USA 2Y": "2YUSY.B",
        "USA 5Y": "5YUSY.B",
        "USA 10Y": "10YUSY.B",
        "USA 30Y": "30YUSY.B",
        "CANADA 2Y": "2YCAY.B",
        "CANADA 5Y": "5YCAY.B",
        "CANADA 10Y": "10YCAY.B",
        "CANADA 30Y": "30YCAY.B",
        "MEXICO 2Y": "2YMXY.B",
        "MEXICO 5Y": "5YMXY.B",
        "MEXICO 10Y": "10YMXY.B",

        # --- EUROPE (MAJOR) ---
        "GERMANY 2Y": "2YDEY.B",
        "GERMANY 5Y": "5YDEY.B",
        "GERMANY 10Y": "10YDEY.B",
        "GERMANY 30Y": "30YDEY.B",
        "UK GILT 2Y": "2YUKY.B",
        "UK GILT 5Y": "5YUKY.B",
        "UK GILT 10Y": "10YUKY.B",
        "UK GILT 30Y": "30YUKY.B",
        "FRANCE 2Y": "2YFRY.B",
        "FRANCE 5Y": "5YFRY.B",
        "FRANCE 10Y": "10YFRY.B",
        "FRANCE 30Y": "30YFRY.B",
        "ITALY 2Y": "2YITY.B",
        "ITALY 5Y": "5YITY.B",
        "ITALY 10Y": "10YITY.B",
        "ITALY 30Y": "30YITY.B",

        # --- EUROPE (SECONDARY) ---
        "SPAIN 10Y": "10YESY.B",
        "NETHERLANDS 10Y": "10NLY.B",
        "SWITZERLAND 10Y": "10CHY.B",
        "POLAND 10Y": "10PLY.B",

        # --- ASIA-PACIFIC ---
        "JAPAN 2Y": "2YJPY.B",
        "JAPAN 5Y": "5YJPY.B",
        "JAPAN 10Y": "10JPY.B",
        "JAPAN 30Y": "30JPY.B",
        "AUSTRALIA 2Y": "2YAUY.B",
        "AUSTRALIA 5Y": "5YAUY.B",
        "AUSTRALIA 10Y": "10YAUY.B",
        "AUSTRALIA 30Y": "30YAUY.B",
        "HONG KONG 2Y": "2YHKY.B",
        "HONG KONG 10Y": "10YHKY.B"
    }
    ticker = STOOQ_BOND_MAP.get(ticker)
    if not ticker:
        st.write("Bond not found")
        st.stop()
    try:
        # data_source='stooq' is the key here
        df = web.DataReader(ticker, 'stooq')
        
        # Stooq returns data in reverse chronological order; sort it for analysis
        df = df.sort_index()
        
        if df.empty:
            print(f"Warning: No data returned for {ticker}")
            return None
            
        return df.reset_index()
    except Exception as e:
        print(f"Error fetching {ticker} via pandas_datareader: {e}")
        return None

def get_fred_bond_data(ticker_input):
    ticker_map = {
        "USA 1M": "DGS1MO",
        "USA 3M": "DGS3MO",
        "USA 6M": "DGS6MO",
        "USA 1Y": "DGS1",
        "USA 2Y": "DGS2",
        "USA 3Y": "DGS3",
        "USA 5Y": "DGS5",
        "USA 7Y": "DGS7",
        "USA 10Y": "DGS10",
        "USA 20Y": "DGS20",
        "USA 30Y": "DGS30",
    }
    symbol = ticker_map.get(ticker_input.upper())
    if not symbol:
        st.write("Bond not found")
        st.stop()
    
    try:
        # 1. Fetch data
        df = web.DataReader(symbol, 'fred', start='2015-01-01')
    
        
        if df.empty:
            return pd.DataFrame()

        # 2. Reformat
        df = df.reset_index()
        df.columns = ['Date', 'Close']
        
        # 3. Clean specifically
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.dropna(subset=['Close']) # Only drop if the price is missing
        
        return df
    except Exception as e:
        print(f"FRED Error: {e}")
        return pd.DataFrame()
BOND_COUNTRIES = {
    "AUSTRALIA",
    "CANADA",
    "FRANCE",
    "GERMANY",
    "HONG KONG",
    "ITALY",
    "JAPAN",
    "MEXICO",
    "NETHERLANDS",
    "POLAND",
    "SPAIN",
    "SWITZERLAND",
    "UK",
    "USA",
    "US"
}

def get_international(ticker_input):
    return get_stooq_macro(ticker_input)

def get_bond_data(ticker_input):
    ticker_input = ticker_input.upper()
    country, length = ticker_input.upper().split(" ")
    if country == "US":
        country += "A"
    if country == "USA":
        return get_fred_bond_data(ticker_input)
    
    if country in BOND_COUNTRIES:
        return get_international(ticker_input)

def get_spread(ticker_input):
    ticker_input = ticker_input.upper()
    tenors = re.findall(r'\d+', ticker_input)
    if len(tenors) == 3:
        tenor_first = get_fred_bond_data(f"USA {tenors[0]}Y")
        tenor_mid = get_fred_bond_data(f"USA {tenors[1]}Y")
        tenor_last = get_fred_bond_data(f"USA {tenors[2]}Y")

        compiled = tenor_first.merge(tenor_mid, on = "Date", how = "inner", suffixes = ("_f", "_m"))
        compiled = compiled.merge(tenor_last, on = "Date", how = "inner")

        compiled["Close"] = 2 * compiled["Close_m"] - (compiled["Close"] + compiled["Close_f"])
        return compiled[["Date", "Close"]]
        
    if len(tenors) == 2:
        tenor_first = get_fred_bond_data(f"USA {tenors[0]}Y")
        tenor_second = get_fred_bond_data(f"USA {tenors[1]}Y")
        compiled = tenor_first.merge(tenor_second, on = "Date", how = "inner", suffixes = ("_f", "_s"))

        compiled["Close"] = compiled["Close_f"] - compiled["Close_s"]
        return compiled[["Date", "Close"]]
    
    return
    
def main():
    arg_3y = get_stooq_macro('5YCAP.B')
    spy = get_stooq_macro('SPY.US')



if __name__ == "__main__":
    main()
