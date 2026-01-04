import streamlit as st
import pandas as pd
import glob
import requests
import time
from imdb import Cinemagoer

# Set Page Config
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. SETTINGS ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/12o_X4-184BAPYKZqzqcjv4GEsBtisVWl8bvE4Pyne64/export?format=csv&gid=2013918688"
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

    try:
        sheet_df = pd.read_csv(f"{SHEET_CSV_URL}&cache={int(time.time())}")
        sheet_df.columns = sheet_df.columns.str.strip()
        manual_entries = sheet_df[sheet_df.iloc[:, 1] == "MANUAL"].copy()
        
        if not manual_entries.empty:
            manual_clean = pd.DataFrame()
            titles = manual_entries.iloc[:, 2].astype(str)
            source_col = manual_entries.iloc[:, 3].astype(str)
            
            mask = (titles.str.lower() != 'title') & (source_col.str.contains('\|'))
            manual_clean['Title'] = titles[mask]
            
            # FIX: Use ' | ' with spaces to split correctly
            parts = source_col[mask].str.split(' \| ')
            
            manual_clean['Source List'] = parts.str[0]
            
            # FIX: Properly parse Year and Rating to avoid 2026/1999 defaults
            manual_clean['Year'] = pd.to_numeric(parts.str[1], errors='coerce').astype('Int64')
            
            raw_ratings = parts.str[2].str.replace('⭐', '', regex=False)
            manual_clean['IMDb Rating'] = pd.to_numeric(raw_ratings, errors='coerce')
            
            manual_clean['Const'] = parts.str[3]
            manual_clean['Genre'] = parts.str[4]
            manual_clean['Director'] = parts.str[5]
            manual_clean['Actors'] = parts.str[6]
            
            master_df = pd.concat([master_df, manual_clean], ignore_index=True)
            
    except Exception as e:
        st.sidebar.error(f"Sync Error: {e}")

    master_df['IMDb Rating'] = pd.to_numeric(master_df['IMDb Rating'], errors='coerce').fillna(0)
    master_df['Year'] = pd.to_numeric(master_df['Year'], errors='coerce').fillna(0).astype(int)
    
    for col in ['Genre', 'Director', 'Actors']:
        if col not in master_df.columns: master_df[col] = "N/A"

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

def add_manual_movie(title, smart_source):
    try:
        requests.post(FORM_URL, data={ENTRY_ID_TITLE: title, ENTRY_ID_SOURCE: smart_source, ENTRY_ID_CONST: "MANUAL"})
        return True
    except: return False

def get_unique_sources(master_df):
    sources = ["Manual", "TikTok", "YouTube", "Friend Recommendation"]
    if not master_df.empty:
        raw_sources = master_df['Source List'].unique().tolist()
        for s in raw_sources:
            parts = [p.strip() for p in str(s).split(',')]
            sources.extend(parts)
    return sorted(list(set([s for s in sources if s and s != 'nan'])))

# --- 3. INITIALIZATION ---
df = load_imdb_data()
if "watched_ids" not in st.session_state:
    st.session_state.watched_ids = get_watched_list()
if "selected_movie_id" not in st.session_state:
    st.session_state.selected_movie_id = None

# --- 4. SIDEBAR ---
st.sidebar.title("🔍 David's Filters")
if df is not None:
    if st.sidebar.button("🏠 Back to Master Table", use_container_width=True):
        st.session_state.selected_movie_id = None
        st.rerun()

    search_query = st.sidebar.text_input("Title Search:")
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

available_sources = get_unique_sources(df)
st.sidebar.divider()
st.sidebar.subheader("➕ Quick Add Movie")

selected_source = st.sidebar.selectbox("Where did you hear about it?", available_sources)
if st.sidebar.checkbox("Add a new source?"):
    custom_source = st.sidebar.text_input("Type new source name:")
    final_source = custom_source if custom_source else selected_source
else:
    final_source = selected_source

add_search_query = st.sidebar.text_input("Search IMDb to add:", key="omdb_search")

if st.sidebar.button("Search & Add"):
    if add_search_query:
        url = f"http://www.omdbapi.com/?t={add_search_query}&apikey={OMDB_API_KEY}"
        res = requests.get(url).json()
        if res.get("Response") == "True":
            # PACKING THE STRING: Source | Year | Rating | ID | Genre | Director | Actors
            smart_source = f"{final_source} | {res.get('Year')[:4]} | {res.get('imdbRating')}⭐ | {res.get('imdbID')} | {res.get('Genre')} | {res.get('Director')} | {res.get('Actors')}"
            if add_manual_movie(res.get("Title"), smart_source):
                st.sidebar.success(f"Added: {res.get('Title')}")
                st.cache_data.clear()
                st.rerun()

# --- 5. PAGE LOGIC ---
if st.session_state.selected_movie_id:
    # DETAIL PAGE
    movie = df[df['Const'] == st.session_state.selected_movie_id].iloc[0]
    st.header(f"{movie['Title']} ({movie['Year']})")
    
    if str(movie['Const']) in st.session_state.watched_ids:
        st.success("✅ You have watched this movie.")
    else:
        if st.button("👁️ Watched"):
            if mark_as_watched_permanent(str(movie['Const'])):
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("IMDb Rating", f"{movie['IMDb Rating']} ⭐")
        st.write(f"**Director:** {movie['Director']}")
        st.write(f"**Genre:** {movie['Genre']}")
        # FIX: Added Main Cast
        st.write(f"**🎭 Main Cast:** {movie.get('Actors', 'N/A')}")
    with col2:
        st.metric("Hype Score", f"{movie['Hype Score']} Lists")
        st.info(f"**📂 Lists:** {movie['Source List']}")

    st.divider()
    b1, b2, b3 = st.columns(3)
    with b1: st.link_button("🎥 IMDb", f"https://www.imdb.com/title/{movie['Const']}/", use_container_width=True)
    with b2: st.link_button("🍅 Rotten Tomatoes", f"https://www.rottentomatoes.com/search?search={movie['Title'].replace(' ', '%20')}", use_container_width=True)
    with b3: st.link_button("📺 JustWatch", f"https://www.justwatch.com/uk/search?q={movie['Title'].replace(' ', '%20')}", use_container_width=True, type="primary")

else:
    # MAIN TABLE
    st.title("🎬 David's Movie Prioritizer")
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