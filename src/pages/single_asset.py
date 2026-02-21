import streamlit as st
import sys
import os
from pathlib import Path
import datetime

# Add the parent directory to sys.path
path_root = Path(__file__).parents[1]
sys.path.append(str(path_root))

from helper import get_data, multiple_heatmap, multiple_line_plot

def main():
    st.title("Seasonality Analysis")
    st.set_page_config(page_title="Seasonality Analysis", layout="wide")
    # heatmap + T-10 - T+10 time series
    c1, c2, c3 = st.columns([0.2, 0.5, 0.3])
    with c1:
        asset_type_x = st.selectbox(
            "Select First Asset Class",
            options = ["Equity", "Bond", "FX"]
        )
        if asset_type_x == "Bond":
            st.write("Eg. USA 3Y")
        if asset_type_x == "FX":
            st.write("Eg. SGDUSD")
        asset_ticker_x = st.text_input(
            "Enter First Ticker"
        )
        
    with c2:
        if st.button("Clear All Events"):
    # Delete the data storage
            if "event_data_indexed" in st.session_state:
                del st.session_state.event_data_indexed
            
            # Delete the widget keys to prevent 'value' conflicts
            # We find all keys starting with label_s, start_s, or end_s
            for key in list(st.session_state.keys()):
                if any(key.startswith(prefix) for prefix in ["label_s", "start_s", "end_s"]):
                    del st.session_state[key]
                    
            st.rerun()
        if "event_data_indexed" not in st.session_state:
            st.session_state.event_data_indexed = {}

        # 2. Define the update function
        def update_event(index):
            # Pull current values directly from the widget keys
            label = st.session_state[f"label_s{index}"]
            t0 = st.session_state[f"start_s{index}"]
            days = st.session_state[f"end_s{index}"]
            
            if label.strip():
                st.session_state.event_data_indexed[index] = {
                    "label": label,
                    "data": (t0, days)
                }
            else:
                # Cleanup if label is deleted
                st.session_state.event_data_indexed.pop(index, None)

        # 3. Determine how many rows to show
        completed_indices = sorted(st.session_state.event_data_indexed.keys())
        num_to_show = max(1, len(completed_indices) + 1)

        # 4. Render the Rows
        for i in range(num_to_show):
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 1])
                
                # Load existing data for the widget defaults
                existing = st.session_state.event_data_indexed.get(i, {"label": "", "data": (datetime.datetime.today(), 5)})
                
                # We use on_change to trigger the save logic only when the user finishes typing
                col1.text_input(f"Label {i+1}", key=f"label_s{i}", value=existing["label"], on_change=update_event, args=(i,))
                col2.date_input(f"Start {i+1}", key=f"start_s{i}", value=existing["data"][0], on_change=update_event, args=(i,))
                col3.number_input(f"Days {i+1}", key=f"end_s{i}", value=existing["data"][1], on_change=update_event, args=(i,))

        # 5. Final Data Construction
        final_event_data = {
            v["label"]: v["data"] 
            for v in st.session_state.event_data_indexed.values()
        }
    try:
        dat = get_data(asset_ticker_x, asset_type_x)
    except:
        st.write("Ticker not found. Please try again.")
        st.stop()
    if dat.empty:
        st.stop()

    dat["Working"] = dat["Close"]
    print(final_event_data)
    if not final_event_data:
        st.stop()
    st.space()
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(multiple_heatmap(dat, final_event_data), theme = None, width = "stretch")
    with c2:
        st.plotly_chart(multiple_line_plot(dat, final_event_data), theme = None, width = "stretch")
    pass


if __name__ == "__main__":
    main()
