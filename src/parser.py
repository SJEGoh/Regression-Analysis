from ddgs import DDGS
from dateparser.search import search_dates
import re
from collections import Counter

def google_lite_date(event_name, specific_site = "bloomberg.com"):
    """
    Mimics Google's 'Direct Answer' feature.
    1. Searches the web for the query.
    2. Scans the snippets for date-like text.
    3. Returns the most likely date object.
    """
    query = f"site:{specific_site} {event_name}"
    print(f"🔍 Googling: '{query}'...")
    
    # 1. Get Top 3 Search Results
    # We look at multiple results to increase confidence
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))
        
    if not results:
        return None, "No results found."

    # 2. Heuristic: Look for the date in the text
    # We combine titles and snippets into one big block of text
    potential_dates = []
    
    for r in results:
        text = f"{r['title']} . {r['body']}"
        
        # 'dateparser' is smart. It finds specific dates in messy text.
        # We assume the date is in the past (e.g. "last friday")
        extracted = search_dates(
            text, 
            languages=['en'], 
            settings={'PREFER_DATES_FROM': 'past'}
        )
        
        if extracted:
            for date_str, date_obj in extracted:
                # Filter out noise: Google doesn't care about dates 20 years ago or in the future
                # for a typical "past event" query
                if date_obj.year > 2000 and date_obj.year <= 2026:
                    potential_dates.append(date_obj)

    if not potential_dates:
        return None, "No dates found in snippets."

    print(potential_dates)
    # 3. The "Consensus" Algorithm (Simplest Version)
    # If we found multiple dates, pick the one that appears most often,
    # or just the very first one found (usually the most relevant in search).
    vote_counts = Counter(potential_dates)
    winner, count = vote_counts.most_common(1)[0]
    # For a simple project, the first valid date from the #1 result is usually the answer.
    
    return winner, f"Found in {count} results"

# --- Usage ---
event = "trump elected"
date, source = google_lite_date(event)

if date:
    print(f"✅ Event: {event}")
    print(f"📅 Date: {date.strftime('%Y-%m-%d')}")
    print(f"🔗 Source: {source}")
else:
    print("❌ Could not find date.")
