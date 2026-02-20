import streamlit as st
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path
path_root = Path(__file__).parents[1]
sys.path.append(str(path_root))

from helper import get_data, multiple_heatmap, multiple_line_plot

def main():
    st.title("Seasonality Analysis")
    st.set_page_config(page_title="Seasonality Analysis", layout="wide")
    # heatmap + T-10 - T+10 time series
    c1, c2, c3 = st.columns([0.2, 0.2, 0.6])
    with c1:
        asset_type_x = st.selectbox(
            "Select First Asset Class",
            options = ["Equity", "Bond", "FX"]
        )
        asset_ticker_x = st.text_input(
            "Enter First Ticker"
        )
        
    with c3:
        if "input_rows_single" not in st.session_state:
            st.session_state.input_rows_single = 1  # Start with 1 row

        # 2. Initialize the Data Storage (The results)
        if "event_data_single" not in st.session_state:
            st.session_state.event_data_single = {} 

        # 3. Render the Rows
        # We loop based on the Counter, not the data
        for i in range(st.session_state.input_rows_single):
            with st.container(): # Group them visually
                col1, col2, col3 = st.columns([2, 1, 1])
                
                # Use key=... to make each widget unique
                label = col1.text_input(f"Label", key=f"label_s{i}", value = None)
                T0 = col2.date_input(f"Start", key=f"start_s{i}", value = None)
                days = col3.number_input(f"Days", key=f"end_s{i}", value = None)

                # Store the data immediately if label is typed
                if label and T0 and days:
                    st.session_state.event_data_single[label] = (T0, days)

        last_label_key = f"label_s{st.session_state.input_rows_single - 1}"

        if st.session_state.get(last_label_key): 
            st.session_state.input_rows_single += 1
            st.rerun() # Force reload to show the new empty row

        # {label: (T-0, days)}
    try:
        dat = get_data(asset_ticker_x, asset_type_x)
    except:
        st.write("Ticker not found. Please try again.")
        st.stop()
    if dat.empty:
        st.stop()

    dat["Working"] = dat["Close"]
    if not st.session_state.event_data:
        st.stop()
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(multiple_heatmap(dat, st.session_state.event_data), theme = None, width = "stretch")
    with c2:
        st.plotly_chart(multiple_line_plot(dat, st.session_state.event_data), theme = None, width = "stretch")
    pass


if __name__ == "__main__":
    main()
