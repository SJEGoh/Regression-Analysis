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
            if st.button("Clear All Events"):
                # 1. FIX: Use the correct variable name
                if "event_data" in st.session_state:
                    del st.session_state.event_data

                for key in list(st.session_state.keys()):
                    if any(key.startswith(prefix) for prefix in ["label", "start", "end"]):
                        del st.session_state[key]
                        
                st.rerun()
            if "event_data" not in st.session_state:
                st.session_state.event_data = {}

            # 2. Define the update function
            def update_event(index):
                # Pull current values directly from the widget keys
                label = st.session_state[f"label{index}"]
                start = st.session_state[f"start{index}"]
                end = st.session_state[f"end{index}"]
                
                if label.strip():
                    st.session_state.event_data[index] = {
                        "label": label,
                        "data": (start, end)
                    }
                else:
                    # Cleanup if label is deleted
                    st.session_state.event_data.pop(index, None)

            # 3. Determine how many rows to show
            completed_indices = sorted(st.session_state.event_data.keys())
            num_to_show = max(1, len(completed_indices) + 1)

            # 4. Render the Rows
            for i in range(num_to_show):
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    # Load existing data for the widget defaults
                    existing = st.session_state.event_data.get(i, {"label": "", "data": (datetime.datetime.today(), datetime.datetime.today())})
                    
                    # We use on_change to trigger the save logic only when the user finishes typing
                    col1.text_input(f"Label {i+1}", key=f"label{i}", value=existing["label"], on_change=update_event, args=(i,))
                    col2.date_input(f"Start {i+1}", key=f"start{i}", value=existing["data"][0], on_change=update_event, args=(i,))
                    col3.date_input(f"Days {i+1}", key=f"end{i}", value=existing["data"][1], on_change=update_event, args=(i,))

            # 5. Final Data Construction
            final_event_data = {
                v["label"]: v["data"] 
                for v in st.session_state.event_data.values()
            }
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
        st.plotly_chart(get_annual_series(data_x, lvd), theme = None)
        st.plotly_chart(get_monthly_series(data_x), theme = None)
    with c2:
        st.plotly_chart(get_heatmap(data_x, lvd))


if __name__ == "__main__":
    main()
