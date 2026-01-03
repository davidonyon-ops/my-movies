import streamlit as st
import pandas as pd
import glob
import requests
import time  # Fixed: Moved to the top so all functions can see it
from imdb import Cinemagoer

# Set Page Config
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. SETTINGS ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/12o_X4-184BAPYKZqzqcjv4GEsBtisVWl8bvE4Pyne64/export?format=csv&gid=2013918688#gid=2013918688"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdgws-uAGliOfkv7nDXonUEIyhl9snn5-DWzl20StGpo6RrCA/formResponse"
ENTRY_ID_CONST = "entry.505487716"
ENTRY_ID_TITLE = "entry.1090297045" 
ENTRY_ID_SOURCE = "entry.1247422407" 
ia = Cinemagoer()
OMDB_API_KEY = "2035a709" 

# --- 2. DATA LOADING ---
@st.cache_data(ttl=300)
def load_imdb_data():
    files = glob.glob("*.csv")
    all_github_data = []
    for f in files:
        try:
            temp_df = pd.read_csv(f, encoding='latin1')
            temp_df.columns = temp_df.columns.str.strip().str.replace('ï»¿', '')
            temp_df['Source List'] = f.replace('.csv', '')
            all_github_data.append(temp_df)
        except: continue
    
    master_df = pd.concat(all_github_data, ignore_index=True) if all_github_data else pd.DataFrame()

    # 2. GET MANUAL DATA
    try:
        sheet_df = pd.read_csv(f"{SHEET_CSV_URL}&cache={int(time.time())}")
        sheet_df.columns = sheet_df.columns.str.strip()
        
        # Look for "MANUAL" in the 2nd column
        manual_entries = sheet_df[sheet_df.iloc[:, 1] == "MANUAL"].copy()
        
        if not manual_entries.empty:
            manual_clean = pd.DataFrame()
            
            # 1. Temporarily grab the data
            titles = manual_entries.iloc[:, 2].astype(str)
            source_col = manual_entries.iloc[:, 3].astype(str)
            
            # 2. FILTER out the header row properly
            # We use .str.lower() to check the whole column
            mask = titles.str.lower() != 'title'
            manual_clean['Title'] = titles[mask]
            
            # 3. Split the source string only for the non-header rows
            parts = source_col[mask].str.split(' | ')
            
            # 4. Extract data safely
            manual_clean['Source List'] = parts.str[0]
            
            # Use pd.to_numeric with 'coerce' to handle non-numbers safely
            years = pd.to_numeric(parts.str[1], errors='coerce')
            manual_clean['Year'] = years.fillna(2026).astype(int)
            
            ratings = pd.to_numeric(parts.str[2].str.replace('⭐', ''), errors='coerce')
            manual_clean['IMDb Rating'] = ratings.fillna(0.0).astype(float)
            
            manual_clean['Const'] = parts.str[3]
            manual_clean['Genre'] = parts.str[4].fillna("N/A")
            manual_clean['Director'] = parts.str[5].fillna("N/A")
            manual_clean['Actors'] = parts.str[6].fillna("N/A")

            # Final cleanup of any empty rows
            manual_clean = manual_clean.dropna(subset=['Title'])
            
            master_df = pd.concat([master_df, manual_clean], ignore_index=True)
            
    except Exception as e:
        st.sidebar.error(f"Sync Error: {e}")

    # 3. CLEANING & HYPE SCORE
    master_df['IMDb Rating'] = pd.to_numeric(master_df['IMDb Rating'], errors='coerce').fillna(0)
    master_df['Year'] = pd.to_numeric(master_df['Year'], errors='coerce').fillna(0).astype(int)
    
    for col in ['Genre', 'Director', 'Actors']:
        if col not in master_df.columns:
            master_df[col] = "N/A"
    
    # Grouping logic
    agg_df = master_df.groupby(['Title', 'Year', 'Const']).agg({
        'Source List': lambda x: ", ".join(sorted(set(x.astype(str)))),
        'IMDb Rating': 'max',
        'Genre': 'first',
        'Director': 'first',
        'Actors': 'first'
    }).reset_index()

    agg_df['Hype Score'] = agg_df['Source List'].str.count(',') + 1
    agg_df = agg_df.sort_values('Hype Score', ascending=False)

    # Mini-function 
    def fetch_missing_info(row):
        if pd.isna(row.get('Director')) or row.get('Director') == "N/A" or row.get('Director') == "":
            try:
                url = f"http://www.omdbapi.com/?t={row['Title']}&apikey={OMDB_API_KEY}"
                data = requests.get(url).json()
                if data.get("Response") == "True":
                    return pd.Series([data.get("Genre"), data.get("Director"), data.get("Actors")])
            except:
                pass
        return pd.Series([row.get('Genre'), row.get('Director'), row.get('Actors')])

    # Main Logic 
    agg_df[['Genre', 'Director', 'Actors']] = agg_df.apply(fetch_missing_info, axis=1)
    
    # Return     # Return 
    return agg_df

def get_watched_list():
    try:
        cache_buster = f"&cache_bust={int(time.time())}"
        watched_df = pd.read_csv(SHEET_CSV_URL + cache_buster)
        watched_df.columns = watched_df.columns.str.strip()
        
        if 'Const' in watched_df.columns:
            watched_ids = watched_df['Const'].astype(str).str.strip().unique().tolist()
            return set(watched_ids)
        return set()
    except:
        return set()

def mark_as_watched_permanent(const_id):
    # Fixed: Updated to use ENTRY_ID_CONST instead of ENTRY_ID
    form_data = {ENTRY_ID_CONST: const_id} 
    try:
        response = requests.post(FORM_URL, data=form_data)
        if response.status_code == 200:
            st.session_state.watched_ids.add(const_id)
            return True
        return False
    except:
        return False

def add_manual_movie(title, source_name):
    # 1. LIVE SEARCH IMDB
    try:
        search = ia.search_movie(title)
        if search:
            movie_id = search[0].movieID
            live_movie = ia.get_movie(movie_id)
            live_rating = live_movie.get('rating', 0.0)
            live_year = live_movie.get('year', 2026)
        else:
            live_rating = 0.0
            live_year = 2026
    except:
        live_rating = 0.0
        live_year = 2026

    # 2. SEND TO GOOGLE FORM
    # Note: Ensure your form has spots for these!
    form_data = {
        ENTRY_ID_TITLE: title, 
        ENTRY_ID_SOURCE: source_name,
        ENTRY_ID_CONST: "MANUAL",
        "entry.RATING_ID": live_rating,  # Add your Entry ID for Rating
        "entry.YEAR_ID": live_year      # Add your Entry ID for Year
    }
    
    try:
        requests.post(FORM_URL, data=form_data)
        return True
    except:
        return False

def get_unique_sources(master_df):
    # 1. Start with your core manual categories
    sources = ["Manual", "TikTok", "YouTube", "Friend Recommendation"]
    
    if not master_df.empty:
        # 2. Get all entries from the Source column
        raw_sources = master_df['Source List'].unique().tolist()
        
        for s in raw_sources:
            # 3. If a row says "Action, TikTok", split it into ["Action", "TikTok"]
            # We split by the comma and strip out any extra spaces
            parts = [p.strip() for p in str(s).split(',')]
            sources.extend(parts)
    
    # 4. Remove duplicates, remove empty strings, and sort
    # This ensures "TikTok" only appears once even if it was in a combo
    sources = sorted(list(set([s for s in sources if s and s != 'nan'])))
    return sources

# --- 3. INITIALIZATION ---
df = load_imdb_data()
if "watched_ids" not in st.session_state:
    st.session_state.watched_ids = get_watched_list()
if "selected_movie_id" not in st.session_state:
    st.session_state.selected_movie_id = None

if 'Genre' in df.columns:
    all_genres = []
    for g in df['Genre'].dropna().unique():
        all_genres.extend([x.strip() for x in str(g).split(',')])
    genre_options = sorted(list(set([g for g in all_genres if g != "N/A"])))
else:
    genre_options = []

# --- 4. SIDEBAR ---
st.sidebar.title("🔍 David's Filters")
if df is not None:
    if st.sidebar.button("🏠 Back to Master Table", use_container_width=True):
        st.session_state.selected_movie_id = None
        st.rerun()

    search_query = st.sidebar.text_input("Title Search:")
    
    # 2. Sidebar Genre Filter
    selected_genres = st.sidebar.multiselect(
    "Filter by Genre:",
    options=genre_options,
    default=[]
)

# 3. Apply the Filters to your dataframe
    # 1. Start with the full list
filtered_df = df.copy()

# 2. Title Filter
if search_query:
    filtered_df = filtered_df[filtered_df['Title'].str.contains(search_query, case=False, na=False)]

# 3. Genre Filter (The "Robust" Version)
if selected_genres:
    genre_pattern = '|'.join(selected_genres)
    filtered_df = filtered_df[filtered_df['Genre'].str.contains(genre_pattern, case=False, na=False)]

# 4. Final Display
st.write(f"🔍 Found **{len(filtered_df)}** movies matching your criteria")
st.dataframe(filtered_df)
    
st.sidebar.divider()
    
    hide_watched = st.sidebar.checkbox("Hide Watched Movies", value=True)
    
    lists = sorted(list(set([i.strip() for s in df['Source List'].str.split(',') for i in s])))
    selected_lists = st.sidebar.multiselect("Filter by CSV Name:", lists)
    min_rating = st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, 6.0, 0.5)
    yr_min, yr_max = int(df['Year'].min()), int(df['Year'].max())
    year_range = st.sidebar.slider("Release Year", yr_min, yr_max, (yr_min, yr_max))

    filtered_df = df[
        (df['IMDb Rating'] >= min_rating) & 
        (df['Year'] >= year_range[0]) & (df['Year'] <= year_range[1])
    ].copy()

    if hide_watched:
        filtered_df = filtered_df[~filtered_df['Const'].astype(str).isin(st.session_state.watched_ids)]
    if selected_lists:
        filtered_df = filtered_df[filtered_df['Source List'].apply(lambda x: any(l in x for l in selected_lists))]
    if search_query:
        filtered_df = filtered_df[filtered_df['Title'].str.contains(search_query, case=False)]

# First, get the list of available sources from the data we already loaded
available_sources = get_unique_sources(df)

st.sidebar.divider()
st.sidebar.subheader("➕ Quick Add Movie")

# Dropdown for Source
# We use "index=0" to default to the first item (usually "Friend" or "Manual")
selected_source = st.sidebar.selectbox("Where did you hear about it?", available_sources)

# Add a "New Source" option if it's not in the list
if st.sidebar.checkbox("Add a new source?"):
    custom_source = st.sidebar.text_input("Type new source name:")
    final_source = custom_source if custom_source else selected_source
else:
    final_source = selected_source

# 2. Search Box
search_query = st.sidebar.text_input("Search IMDb to add:", key="omdb_search")

if st.sidebar.button("Search & Add"):
    if search_query and OMDB_API_KEY != "YOUR_API_KEY_HERE":
        url = f"http://www.omdbapi.com/?t={search_query}&apikey={OMDB_API_KEY}"
        response = requests.get(url).json()
        
        if response.get("Response") == "True":
            title = response.get("Title")
            year = response.get("Year")[:4]
            rating = response.get("imdbRating", "0.0")
            imdb_id = response.get("imdbID")
            
            # NEW: Get the extra details
            genre = response.get("Genre", "N/A")
            director = response.get("Director", "N/A")
            actors = response.get("Actors", "N/A")
            
            # We pack it all into the Source field using a divider like '||'
            # Format: Source | Year | Rating | ID | Genre | Director | Actors
            smart_source = f"{final_source} | {year} | {rating}⭐ | {imdb_id} | {genre} | {director} | {actors}"
            
            if add_manual_movie(title, smart_source):
                st.sidebar.success(f"Added: {title}")
                st.cache_data.clear()
                st.rerun()
        else:
            st.sidebar.error("Movie not found in OMDb database.")
    else:
        st.sidebar.warning("Please enter a title and your API Key.")

# --- 5. PAGE LOGIC ---
if st.session_state.selected_movie_id:
    # DETAIL PAGE
    movie = df[df['Const'] == st.session_state.selected_movie_id].iloc[0]
    m_id = str(movie['Const'])
    
    st.header(f"{movie['Title']} ({movie['Year']})")
    
    if m_id in st.session_state.watched_ids:
        st.success("✅ You have watched this movie. Lets keep it goin!")
    else:
        if st.button("👁️ Watched"):
            if mark_as_watched_permanent(m_id):
                st.toast("Saved to Google Sheets!")
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("IMDb Rating", f"{movie['IMDb Rating']} ⭐")
        st.write(f"**Director:** {movie['Director']}")
        st.write(f"**Genre:** {movie['Genre']}")
        st.write(f"🎭 **Main Cast:** {movie.get('Actors', 'N/A')}")
    with col2:
        st.metric("Hype Score", f"{movie['Hype Score']} Lists")
        st.info(f"**📂 Lists:** {movie.get('Source List', 'N/A')}")

    st.divider()
    st.subheader("🔗 Additional Info")
    b1, b2, b3 = st.columns(3)
    with b1: 
        # This creates a proper link using the 'Const' ID we just extracted
        imdb_url = f"https://www.imdb.com/title/{movie['Const']}/"
        st.link_button("🎥 IMDb", imdb_url, use_container_width=True)
    with b2: st.link_button("🍅 Rotten Tomatoes", f"https://www.rottentomatoes.com/search?search={movie['Title'].replace(' ', '%20')}", use_container_width=True)
    with b3: st.link_button("📺 UK Streaming", f"https://www.justwatch.com/uk/search?q={movie['Title'].replace(' ', '%20')}", use_container_width=True, type="primary")

else:
    # MAIN TABLE
    st.title("🎬 David's Movie Prioritizer")
    if filtered_df is not None:
        display_df = filtered_df[['Title', 'Year', 'IMDb Rating', 'Hype Score']].copy()
        display_df.insert(0, "View", False)
        
        edited_df = st.data_editor(
            display_df,
            column_config={"View": st.column_config.CheckboxColumn("View", default=False)},
            disabled=['Title', 'Year', 'IMDb Rating', 'Hype Score'],
            hide_index=True, use_container_width=True, key="main_table"
        )
        
        selected_rows = edited_df[edited_df['View'] == True]
        if not selected_rows.empty:
            sel_title = selected_rows.iloc[0]['Title']
            st.session_state.selected_movie_id = filtered_df[filtered_df['Title'] == sel_title].iloc[0]['Const']
            st.rerun()