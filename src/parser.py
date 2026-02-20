from datetime import datetime
from dateparser.search import search_dates
import streamlit as st
import urllib
import pandas as pd
from collections import Counter
import re
from dateparser.search import search_dates
import requests
import json
from gnews import GNews
from datetime import datetime

def general_event_searcher(query, start_year=None):
    # 1. Regex Bouncer: Extract Year, Month, and Quarter
    months_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    query_lower = query.lower()
    
    # Extract Year (e.g., 2023)
    year_match = re.search(r'20\d{2}', query)
    target_year = int(year_match.group()) if year_match else start_year
    
    # Extract Quarter (e.g., Q1, q2)
    quarter_match = re.search(r'q([1-4])', query_lower)
    
    # Extract Month (e.g., January)
    target_month = next((v for k, v in months_map.items() if k in query_lower), None)

    # 2. Map Quarters to Allowed Months (+1 Month Release Lag)
    allowed_months = []
    if quarter_match:
        q_num = int(quarter_match.group(1))
        # Q1: Jan(1), Feb(2), Mar(3) -> Allowed: 1, 2, 3 + April(4)
        base_months = [(q_num - 1) * 3 + 1, (q_num - 1) * 3 + 2, (q_num - 1) * 3 + 3]
        allowed_months = base_months + [(base_months[-1] % 12) + 1]
    elif target_month:
        # Standard Month + 1 month lag
        allowed_months = [target_month, (target_month % 12) + 1]

    # 3. Initialize GNews
    search_start = datetime(target_year, 1, 1) if target_year else datetime(2015, 1, 1)
    search_end = datetime(target_year, 12, 31) if target_year else datetime.today()
    
    # Q4 Adjustment: If searching Q4, we must extend end date to Jan of next year
    if (quarter_match and int(quarter_match.group(1)) == 4) or target_month == 12:
        search_end = datetime(target_year + 1, 1, 31)

    google_news = GNews(
        language='en', country='US', 
        start_date=search_start, end_date=search_end, 
        max_results=40
    )
    
    results = google_news.get_news(query)
    hits = []
    
    for res in results:
        try:
            raw_date = datetime.strptime(res['published date'], '%a, %d %b %Y %H:%M:%S %Z')
            found_date = raw_date.date()
        except: continue

        # --- STRICT FILTERING ---
        year_ok = (found_date.year == target_year) if target_year else True
        month_ok = (found_date.month in allowed_months) if allowed_months else True
        
        # Exception: Q4/December reports often published in January next year
        is_q4_overflow = (quarter_match and int(quarter_match.group(1)) == 4 and 
                         found_date.year == target_year + 1 and found_date.month == 1)
        
        if (year_ok and month_ok) or is_q4_overflow:
            hits.append({
                "date": found_date,
                "title": res['title'],
                "snippet": res['description'],
                "source": res['url']
            })

    # 4. Process for Consensus
    if not hits: return pd.DataFrame()
    df = pd.DataFrame(hits)
    counts = Counter(df['date'])
    df['Consensus'] = df['date'].apply(lambda x: f"★ {counts[x]} sources agree" if counts[x] > 1 else "")
    
    df['freq'] = df['date'].map(counts)
    df = df.sort_values(by=['freq', 'date'], ascending=False).drop(columns=['freq'])
    return df.drop_duplicates(subset=['date', 'title'])

def process_search_results(raw_hits):
    if not raw_hits:
        return None

    for hit in raw_hits:
        if 'uddg=' in hit['source']:
            hit['source'] = urllib.parse.unquote(hit['source'].split('uddg=')[1].split('&')[0])

    date_counts = Counter([h['date'] for h in raw_hits])
    df = pd.DataFrame(raw_hits)
    df['Consensus'] = df['date'].apply(lambda x: f"★ {date_counts[x]} sources agree" if date_counts[x] > 1 else "")
    df = df.sort_values(by='date', ascending=False)
    
    return df[df["Consensus"]!=""]

def main():
    # Example usage
    print(general_event_searcher("CPI Report Release 2025 Q3"))


if __name__ == "__main__":
    main()
