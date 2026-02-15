import streamlit as st
from helper import get_data, get_figs, get_heatmap, get_annual_series, get_monthly_series
import pandas as pd



def main():
    st.set_page_config(page_title="Cross Sector Asset Screener", layout="wide")
    with st.expander("Query Options", expanded = True):
        c1, c2, c3 = st.columns([0.2, 0.2, 0.6])

        with c1:
            asset_type_x = st.selectbox(
                "Select First Asset Class",
                options = ["Equity", "Bond", "FX"]
            )
            asset_ticker_x = st.text_input(
                "Enter First Ticker"
            )
            lvd = st.radio(
                "Levels or Difference",
                ["Levels", "Difference"],
                horizontal = True
            )
        data_x = get_data(asset_ticker_x, asset_type_x)
        with c2:
            asset_type_y = st.selectbox(
                "Select Second Asset Class",
                options = ["Equity", "Bond", "FX"]
            )
            asset_ticker_y = st.text_input(
                "Enter Second Ticker"
            )
        data_y = get_data(asset_ticker_y, asset_type_y)

        with c3:
            if "input_rows" not in st.session_state:
                st.session_state.input_rows = 1  # Start with 1 row

            # 2. Initialize the Data Storage (The results)
            if "event_data" not in st.session_state:
                st.session_state.event_data = {} 

            # 3. Render the Rows
            # We loop based on the Counter, not the data
            for i in range(st.session_state.input_rows):
                with st.container(): # Group them visually
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    # Use key=... to make each widget unique
                    label = col1.text_input(f"Label", key=f"label_{i}", value = None)
                    start = col2.date_input(f"Start", key=f"start_{i}", value = None)
                    end   = col3.date_input(f"End", key=f"end_{i}", value = None)

                    # Store the data immediately if label is typed
                    if label and start and end:
                        st.session_state.event_data[label] = (start, end)

            # 4. The "Add Row" Logic
            # If the LAST label widget is not empty, increment the counter
            # We access the widget value directly using session_state key
            last_label_key = f"label_{st.session_state.input_rows - 1}"

            if st.session_state.get(last_label_key): 
                st.session_state.input_rows += 1
                st.rerun() # Force reload to show the new empty row

            print(st.session_state.event_data)
        
        if data_x.empty or data_y.empty:
            st.stop()
        if lvd == "Levels":
            data_x["Working"] = data_x["Close"]
            data_y["Working"] = data_y["Close"]
        elif lvd == "Difference":
            data_x["Working"] = data_x["pct_change"]
            data_y["Working"] = data_y["pct_change"]  
        

    f1, f2, f3, f4, f5 = get_figs(data_x, data_y, st.session_state.event_data)

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
        st.plotly_chart(get_annual_series(data_x), theme = None)
        st.plotly_chart(get_monthly_series(data_x), theme = None)
    with c2:
        st.plotly_chart(get_heatmap(data_x, lvd))


if __name__ == "__main__":
    main()
