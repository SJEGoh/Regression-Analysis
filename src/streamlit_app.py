import streamlit as st
from helper import get_data, get_figs, get_heatmap, get_annual_series, get_monthly_series
import pandas as pd
import datetime



def main():
    st.set_page_config(page_title="Regression Analysis", layout="wide")
    with st.expander("Query Options", expanded = True):
        c1, c2, c3 = st.columns([0.2, 0.2, 0.6])

        with c1:
            asset_type_x = st.selectbox(
                "Select First Asset Class",
                options = ["Equity", "Bond", "FX", "Bond Spread"]
            )
            if asset_type_x == "Bond":
                st.write("Eg. USA 3Y")
            if asset_type_x == "FX":
                st.write("Eg. SGDUSD")
            if asset_type_x == "Bond Spread":
                st.write("Eg. 2s5s10s")
            asset_ticker_x = st.text_input(
                "Enter First Ticker"
            )
            lvd = st.radio(
                "Levels or Difference",
                ["Levels", "Difference"],
                horizontal = True
            )

        with c2:
            asset_type_y = st.selectbox(
                "Select Second Asset Class",
                options = ["Equity", "Bond", "FX", "Bond Spread"]
            )
            if asset_type_y == "Bond":
                st.write("Eg. USA 3Y")
            if asset_type_y == "FX":
                st.write("Eg. SGDUSD")
            if asset_type_y == "Bond Spread":
                st.write("Eg. 2s5s10s")
            asset_ticker_y = st.text_input(
                "Enter Second Ticker"
            )
            rolling_period = st.number_input(
                "Enter Rolling Period",
                value = 30
            )
            period_shown = st.number_input(
                "Enter Period to Graph",
                value = 30
            )

        with c3:
            c1, c2 = st.columns([0.6, 0.4])
            with c1:
                n_events = st.number_input("Number of Events",
                                        value = 1, step = 1)
            with c2:
                st.text("Date Format: YYYY-MM-DD \n(e.g. 2025-12-31)")
            c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
            final_event_data = {}
            for i in range(n_events):
                label = c1.text_input("Enter Event",
                                      value = "", key = f"Event {i}")
                start_date = c2.text_input("Enter Start Date",
                                           value = "", key = f"Start {i}")
                end_date = c3.text_input("Enter End Date",
                                         value = "", key = f"End {i}")
            
                if label and start_date and end_date:
                    try:
                        start_dt = pd.to_datetime(start_date, format='%Y-%m-%d')
                        end_dt = pd.to_datetime(end_date, format='%Y-%m-%d')
                        
                        # Calculate the window 'd' (days from target to edge)
                        # Your heatmap logic uses (target_date, d) where the window is target +/- d
                        
                        final_event_data[label] = (start_dt, end_dt)
                    except Exception as e:
                        st.error(f"Error parsing row {i+1}: {e}")
        try:
            data_x = get_data(asset_ticker_x.upper(), asset_type_x)
            data_y = get_data(asset_ticker_y.upper(), asset_type_y)
        except Exception as e:
            st.write("Ticker not found. Please try again.")
            print(e)
            st.stop()
        if data_x.empty or data_y.empty:
            st.stop()
        if lvd == "Levels":
            data_x["Working"] = data_x["Close"]
            data_y["Working"] = data_y["Close"]
        elif lvd == "Difference":
            if asset_type_x == "Bond":
                # Calculate Basis Point change: (Yield_t - Yield_t-1) * 100
                # This assumes your 'Close' is already in percentage format (e.g., 3.50)
                data_x["Working"] = data_x["Close"].diff()
            else:
                # Keep standard pct_change for Equity/FX
                data_x["Working"] = data_x["pct_change"]
                
            if asset_type_y == "Bond":
                data_y["Working"] = data_y["Close"].diff()
            else:
                data_y["Working"] = data_y["pct_change"]
            data_x = data_x.dropna()
            data_y = data_y.dropna()
        
    f1, f2, f3, f4, f5 = get_figs(data_x, data_y, final_event_data, asset_ticker_x, asset_ticker_y, rolling_period, period_shown)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(f5, theme = None, width = "stretch")
    with c2: 
        st.plotly_chart(f4, theme = None, width = "stretch")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(f1, theme = None, width = "stretch")
    with c2:
        st.plotly_chart(f2, theme = None, width = "stretch")
    with c3:
        st.plotly_chart(f3, theme = None, width = "stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(get_annual_series(data_x, asset_type_x), theme = None)
        st.plotly_chart(get_monthly_series(data_x, asset_type_x), theme = None)
    with c2:
        st.plotly_chart(get_heatmap(data_x, asset_type_x))


if __name__ == "__main__":
    main()
