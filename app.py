import streamlit as st
import pandas as pd
import glob
import requests
import time
from imdb import Cinemagoer

# --- 1. SETTINGS & CONFIG ---
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/12o_X4-184BAPYKZqzqcjv4GEsBtisVWl8bvE4Pyne64/export?format=csv&gid=2013918688"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdgws-uAGliOfkv7nDXonUEIyhl9snn5-DWzl20StGpo6RrCA/formResponse"
ENTRY_ID_CONST = "entry.505487716"
ENTRY_ID_TITLE = "entry.1090297045" 
ENTRY_ID_SOURCE = "entry.1247422407" 
OMDB_API_KEY = "2035a709" 
ia = Cinemagoer()

# --- 2. FUNCTIONS ---

@st.cache_data(ttl=300)
def load_imdb_data():
    # 1. Load local CSV files from GitHub/Folder
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

    # 2. Load Manual Data from Google Sheets
    try:
        sheet_df = pd.read_csv(f"{SHEET_CSV_URL}&cache={int(time.time())}")
        sheet_df.columns = sheet_df.columns.str.strip()
        manual_entries = sheet_df[sheet_df.iloc[:, 1] == "MANUAL"].copy()
        
        if not manual_entries.empty:
            manual_clean = pd.DataFrame()
            titles = manual_entries.iloc[:, 2].astype(str)
            source_col = manual_entries.iloc[:, 3].astype(str)
            # Filter out header rows and empty entries
            mask = (titles.str.lower() != 'title') & (source_col.str.contains('\|'))
            
            manual_clean['Title'] = titles[mask]
            
            # PARSING THE SMART STRING: Source | Year | Rating | ID | Genre | Director | Actors
            parts = source_col[mask].str.split(' \| ')
            
            manual_clean['Source List'] = parts.str[0]
            manual_clean['Year'] = pd.to_numeric(parts.str[1], errors='coerce').fillna(2026).astype(int)
            
            raw_ratings = parts.str[2].str.replace('⭐', '', regex=False)
            manual_clean['IMDb Rating'] = pd.to_numeric(raw_ratings, errors='coerce').fillna(0.0)
            
            manual_clean['Const'] = parts.str[3]
            manual_clean['Genre'] = parts.str[4].fillna("N/A")
            manual_clean['Director'] = parts.str[5].fillna("N/A")
            manual_clean['Actors'] = parts.str[6].fillna("N/A")
            
            master_df = pd.concat([master_df, manual_clean], ignore_index=True)
    except: pass

    # Ensure columns exist and handle NAs
    for col in ['Genre', 'Director', 'Actors', 'IMDb Rating', 'Year', 'Const']:
        if col not in master_df.columns: master_df[col] = "N/A"

    master_df['IMDb Rating'] = pd.to_numeric(master_df['IMDb Rating'], errors='coerce').fillna(0)
    master_df['Year'] = pd.to_numeric(master_df['Year'], errors='coerce').fillna(0).astype(int)

    # 3. Aggregation & Hype Score
    agg_df = master_df.groupby(['Title', 'Year', 'Const']).agg({
        'Source List': lambda x: ", ".join(sorted(set(x.astype(str)))),
        'IMDb Rating': 'max',
        'Genre': 'first',
        'Director': 'first',
        'Actors': 'first'
    }).reset_index()

    agg_df['Hype Score'] = agg_df['Source List'].str.count(',') + 1
    return agg_df.sort_values('Hype Score', ascending=False)

def get_watched_list():
    try:
        watched_df = pd.read_csv(SHEET_CSV_URL + f"&cache={int(time.time())}")
        watched_df.columns = watched_df.columns.str.strip()
        return set(watched_df['Const'].astype(str).str.strip().unique().tolist())
    except: return set()

def mark_as_watched_permanent(const_id):
    try:
        requests.post(FORM_URL, data={ENTRY_ID_CONST: const_id})
        st.session_state.watched_ids.add(const_id)
        return True
    except: return False

def add_manual_movie(title, smart_string):
    try:
        requests.post(FORM_URL, data={ENTRY_ID_TITLE: title, ENTRY_ID_SOURCE: smart_string, ENTRY_ID_CONST: "MANUAL"})
        return True
    except: return False

def get_unique_sources(master_df):
    sources = ["TikTok", "YouTube", "Friend Recommendation", "Manual Entry"]
    if not master_df.empty:
        raw_sources = master_df['Source List'].unique().tolist()
        for s in raw_sources:
            parts = [p.strip() for p in str(s).split(',')]
            sources.extend(parts)
    return sorted(list(set([s for s in sources if s and s != 'nan' and s != 'N/A'])))

# --- 3. INITIALIZATION ---
df = load_imdb_data()
if "watched_ids" not in st.session_state:
    st.session_state.watched_ids = get_watched_list()
if "selected_movie_id" not in st.session_state:
    st.session_state.selected_movie_id = None

# Prep Filters
all_genres = []
for g in df['Genre'].astype(str):
    if g != "N/A":
        all_genres.extend([x.strip() for x in g.split(',')])
genre_options = sorted(list(set(all_genres)))

available_sources = get_unique_sources(df)

# --- 4. SIDEBAR ---
st.sidebar.title("🔍 David's Filters")

if st.sidebar.button("🏠 Reset to Master Table"):
    st.session_state.selected_movie_id = None
    st.rerun()

search_query = st.sidebar.text_input("Search by Title:")
selected_genres = st.sidebar.multiselect("Filter by Genre:", options=genre_options)
min_rating = st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, 5.0, 0.5)
hide_watched = st.sidebar.checkbox("Hide Watched Movies", value=True)

# Apply Filter Logic
filtered_df = df[(df['IMDb Rating'] >= min_rating)].copy()
if hide_watched:
    filtered_df = filtered_df[~filtered_df['Const'].astype(str).isin(st.session_state.watched_ids)]
if search_query:
    filtered_df = filtered_df[filtered_df['Title'].str.contains(search_query, case=False, na=False)]
if selected_genres:
    pattern = '|'.join(selected_genres)
    filtered_df = filtered_df[filtered_df['Genre'].str.contains(pattern, case=False, na=False)]

st.sidebar.divider()
st.sidebar.subheader("➕ Add New Movie")
sel_source = st.sidebar.selectbox("Where from?", available_sources)
custom_source = st.sidebar.text_input("OR Type New Source:")
final_source = custom_source if custom_source else sel_source

add_title = st.sidebar.text_input("Movie Title:", key="add_search")
if st.sidebar.button("Search & Add"):
    if add_title:
        url = f"http://www.omdbapi.com/?t={add_title}&apikey={OMDB_API_KEY}"
        res = requests.get(url).json()
        if res.get("Response") == "True":
            # Build the Smart String correctly
            smart = f"{final_source} | {res.get('Year')[:4]} | {res.get('imdbRating')}⭐ | {res.get('imdbID')} | {res.get('Genre')} | {res.get('Director')} | {res.get('Actors')}"
            if add_manual_movie(res.get("Title"), smart):
                st.sidebar.success(f"Added {res.get('Title')}!")
                st.cache_data.clear()
                st.rerun()

# --- 5. MAIN DISPLAY ---
if st.session_state.selected_movie_id:
    # DETAIL PAGE
    movie = df[df['Const'] == st.session_state.selected_movie_id].iloc[0].to_dict()
    
    # Auto-backfill N/A if viewing
    if movie['Genre'] == "N/A":
        url = f"http://www.omdbapi.com/?i={movie['Const']}&apikey={OMDB_API_KEY}"
        res = requests.get(url).json()
        if res.get("Response") == "True":
            movie['Genre'], movie['Director'], movie['Actors'] = res.get("Genre"), res.get("Director"), res.get("Actors")

    st.header(f"{movie['Title']} ({movie['Year']})")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Rating", f"{movie['IMDb Rating']} ⭐")
        st.write(f"**🎬 Director:** {movie['Director']}")
        st.write(f"**🏷️ Genre:** {movie['Genre']}")
        st.write(f"**🎭 Main Cast:** {movie['Actors']}")
    with col2:
        st.metric("Hype Score", f"{movie['Hype Score']} Lists")
        st.info(f"**📂 Source:** {movie['Source List']}")
        if st.button("👁️ Mark as Watched"):
            if mark_as_watched_permanent(movie['Const']):
                st.rerun()

    st.divider()
    b1, b2, b3 = st.columns(3)
    with b1: st.link_button("🎥 IMDb", f"https://www.imdb.com/title/{movie['Const']}/", use_container_width=True)
    with b2: st.link_button("🍅 Rotten Tomatoes", f"https://www.rottentomatoes.com/search?search={movie['Title'].replace(' ', '%20')}", use_container_width=True)
    with b3: st.link_button("📺 JustWatch", f"https://www.justwatch.com/uk/search?q={movie['Title'].replace(' ', '%20')}", use_container_width=True, type="primary")

    if st.button("⬅️ Back to List"):
        st.session_state.selected_movie_id = None
        st.rerun()
else:
    # MASTER TABLE
    st.title("🎬 David's Movie Prioritizer")
    display_df = filtered_df[['Title', 'Year', 'Genre', 'IMDb Rating', 'Hype Score']].copy()
    display_df.insert(0, "View", False)
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "View": st.column_config.CheckboxColumn("View", default=False),
            "IMDb Rating": st.column_config.NumberColumn(format="%.1f ⭐"),
            "Hype Score": st.column_config.ProgressColumn(min_value=0, max_value=5)
        },
        disabled=['Title', 'Year', 'Genre', 'IMDb Rating', 'Hype Score'],
        hide_index=True, use_container_width=True, key="main_table"
    )
    
    selected_rows = edited_df[edited_df['View'] == True]
    if not selected_rows.empty:
        sel_title = selected_rows.iloc[0]['Title']
        st.session_state.selected_movie_id = filtered_df[filtered_df['Title'] == sel_title].iloc[0]['Const']
        st.rerun()