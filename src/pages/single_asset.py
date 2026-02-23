import streamlit as st
import sys
import os
from pathlib import Path
import datetime
import ast
import pandas as pd

# Add the parent directory to sys.path
path_root = Path(__file__).parents[1]
sys.path.append(str(path_root))

from helper import get_data, multiple_heatmap, multiple_line_plot

def main():
    st.title("Seasonality Analysis")
    st.set_page_config(page_title="Seasonality Analysis", layout="wide")
    # heatmap + T-10 - T+10 time series
    c1, c2 = st.columns([0.4, 0.6])
    with c1:
        asset_type_x = st.selectbox(
            "Select Asset Class",
            options = ["Equity", "Bond", "FX", "Bond Spread"]
        )
        if asset_type_x == "Bond":
            st.write("Eg. USA 3Y")
        if asset_type_x == "FX":
            st.write("Eg. SGDUSD")
        if asset_type_x == "Bond Spread":
            st.write("Eg. 2s5s10s")
        asset_ticker_x = st.text_input(
            "Enter Ticker"
        )
        
    with c2:
        sc1, sc2, sc3 = st.columns([2, 2, 1])
        labels = sc1.text_input("Enter labels (e.g.Label 1, Label 2)", 
                                value = '')
        t0 = sc2.text_input("Enter T-0 Date (e.g. 2025-01-01, 2024-01-01)",
                            value = '')
        days = sc3.number_input("Days from T-0",
                                value = 5)
        try:
            labels_list = [x.strip() for x in labels.split(",") if x.strip()]
            date_list = [x.strip() for x in t0.split(",") if x.strip()]
        except:
            date_list = []
            labels_list = []
    final_event_data = {}
    if (x := len(date_list) - len(labels_list)) > 0:
        for i in range(0, x):
            labels_list.append(f"Event {i + 1}")
    for label, date in zip(labels_list, date_list):
        try:
            start_date = pd.to_datetime(date, format='%Y-%m-%d')
            final_event_data[label] = (start_date, days)
        except:
            st.write(f"Could not parse date: {date}")
            continue


    try:
        dat = get_data(asset_ticker_x, asset_type_x)
    except:
        st.write("Ticker not found. Please try again.")
        st.stop()
    if dat.empty:
        st.stop()

    dat["Working"] = dat["Close"]
    if not final_event_data:
        st.stop()
    st.space()
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(multiple_heatmap(dat, final_event_data, asset_type_x), theme = None, width = "stretch")
    with c2:
        st.plotly_chart(multiple_line_plot(dat, final_event_data, asset_type_x), theme = None, width = "stretch")
    pass


if __name__ == "__main__":
    main()
