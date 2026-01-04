import streamlit as st
import pandas as pd
import glob
import requests
import time
import plotly.express as px
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
            if 'Genres' in temp_df.columns and 'Genre' not in temp_df.columns:
                temp_df['Genre'] = temp_df['Genres']
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
            parts = source_col[mask].str.split(' \| ')
            
            manual_clean['Source List'] = parts.str[0]
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

    for col in ['Genre', 'Director', 'Actors', 'IMDb Rating', 'Year', 'Const']:
        if col not in master_df.columns: master_df[col] = "N/A"

    master_df['IMDb Rating'] = pd.to_numeric(master_df['IMDb Rating'], errors='coerce').fillna(0)
    master_df['Year'] = pd.to_numeric(master_df['Year'], errors='coerce').fillna(0).astype(int)
    
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
    sources = ["Manual", "TikTok", "YouTube", "Friend"]
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

# Persistence Initialization for multiselect
if "p_selected_lists" not in st.session_state:
    st.session_state.p_selected_lists = []

# --- 4. NAVIGATION ---
st.sidebar.title("🎮 Navigation")
page = st.sidebar.radio("Go to:", ["Movie List", "Analytics"])

if page == "Movie List":
    st.sidebar.divider()
    st.sidebar.title("🔍 Filters")
    if st.sidebar.button("🏠 Back to Master Table", use_container_width=True):
        st.session_state.selected_movie_id = None
        st.rerun()

    # PERSISTENCE: Added keys to all filter widgets
    search_query = st.sidebar.text_input("Title Search:", key="p_search")
    hide_watched = st.sidebar.checkbox("Hide Watched Movies", value=True, key="p_hide")
    
    lists = sorted(list(set([i.strip() for s in df['Source List'].str.split(',') for i in s])))
    selected_lists = []
    with st.sidebar.popover("📂 Filter by CSV Name", use_container_width=True):
        st.write("Select sources to show:")
        for l in lists:
            # Check if it was previously selected in the session
            is_checked = l in st.session_state.p_selected_lists
            if st.checkbox(l, value=is_checked, key=f"filter_{l}"):
                selected_lists.append(l)
        st.session_state.p_selected_lists = selected_lists
    
    min_rating = st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, step=0.5, key="p_rating")
    
    yr_min = int(df['Year'].min()) if not df.empty else 1900
    yr_max = int(df['Year'].max()) if not df.empty else 2026
    # Persistence key for the slider
    year_range = st.sidebar.slider("Release Year", yr_min, yr_max, key="p_years")

    # Applying the persisted filters
    filtered_df = df[
        (df['IMDb Rating'] >= st.session_state.p_rating) & 
        (df['Year'] >= st.session_state.p_years[0]) & (df['Year'] <= st.session_state.p_years[1])
    ].copy()

    if st.session_state.p_hide:
        filtered_df = filtered_df[~filtered_df['Const'].astype(str).isin(st.session_state.watched_ids)]
    if st.session_state.p_selected_lists:
        filtered_df = filtered_df[filtered_df['Source List'].apply(lambda x: any(l in x for l in st.session_state.p_selected_lists))]
    if st.session_state.p_search:
        filtered_df = filtered_df[filtered_df['Title'].str.contains(st.session_state.p_search, case=False)]

    st.sidebar.divider()
    st.sidebar.subheader("➕ Quick Add Movie")

    available_sources = get_unique_sources(df)
    final_source = "Manual"
    with st.sidebar.popover("📍 Select Source", use_container_width=True):
        final_source = st.radio("Choose source:", available_sources)
        if st.checkbox("Add new custom source?"):
            custom = st.text_input("Enter source name:")
            if custom: final_source = custom

    add_search_query = st.sidebar.text_input("Search IMDb to add:", key="omdb_search")

    if st.sidebar.button("Search & Add"):
        if add_search_query:
            url = f"http://www.omdbapi.com/?t={add_search_query}&apikey={OMDB_API_KEY}"
            res = requests.get(url).json()
            if res.get("Response") == "True":
                smart_source = f"{final_source} | {res.get('Year')[:4]} | {res.get('imdbRating')}⭐ | {res.get('imdbID')} | {res.get('Genre')} | {res.get('Director')} | {res.get('Actors')}"
                if add_manual_movie(res.get("Title"), smart_source):
                    st.sidebar.success(f"Added: {res.get('Title')}")
                    st.cache_data.clear()
                    st.rerun()

    # --- MAIN DISPLAY LOGIC ---
    if st.session_state.selected_movie_id:
        movie = df[df['Const'] == st.session_state.selected_movie_id].iloc[0]
        poster_url = None
        try:
            url = f"http://www.omdbapi.com/?i={movie['Const']}&apikey={OMDB_API_KEY}"
            res = requests.get(url).json()
            poster_url = res.get("Poster") if res.get("Poster") != "N/A" else None
        except: pass

        st.header(f"{movie['Title']} ({movie['Year']})")
        col_poster, col_info = st.columns([1, 2])
        with col_poster:
            if poster_url: st.image(poster_url, use_container_width=True)
            else: st.info("No poster available")
        with col_info:
            if str(movie['Const']) in st.session_state.watched_ids:
                st.success("✅ You have watched this movie.")
            else:
                if st.button("👁️ Watched"):
                    if mark_as_watched_permanent(str(movie['Const'])): st.rerun()
            st.metric("IMDb Rating", f"{movie['IMDb Rating']} ⭐")
            st.write(f"**Director:** {movie['Director']}")
            st.write(f"**Genre:** {movie['Genre']}")
            st.write(f"**🎭 Main Cast:** {movie.get('Actors', 'N/A')}")
            st.metric("Hype Score", f"{movie['Hype Score']} Lists")
            st.info(f"**📂 Lists:** {movie['Source List']}")

        st.divider()
        b1, b2, b3 = st.columns(3)
        with b1: st.link_button("🎥 IMDb", f"https://www.imdb.com/title/{movie['Const']}/", use_container_width=True)
        with b2: st.link_button("🍅 Rotten Tomatoes", f"https://www.rottentomatoes.com/search?search={movie['Title'].replace(' ', '%20')}", use_container_width=True)
        with b3: st.link_button("📺 JustWatch", f"https://www.justwatch.com/uk/search?q={movie['Title'].replace(' ', '%20')}", use_container_width=True, type="primary")

    else:
        st.title("🎬 David's Movie Prioritizer")
        display_df = filtered_df[['Title', 'Year', 'IMDb Rating', 'Hype Score']].copy()
        display_df.insert(0, "View", False)
        edited_df = st.data_editor(
            display_df,
            column_config={
                "View": st.column_config.CheckboxColumn("View", default=False),
                "Hype Score": st.column_config.ProgressColumn("Hype Score", min_value=0, max_value=5, format="%f")
            },
            disabled=['Title', 'Year', 'IMDb Rating', 'Hype Score'],
            hide_index=True, use_container_width=True, key="main_table"
        )
        selected_rows = edited_df[edited_df['View'] == True]
        if not selected_rows.empty:
            sel_title = selected_rows.iloc[0]['Title']
            st.session_state.selected_movie_id = filtered_df[filtered_df['Title'] == sel_title].iloc[0]['Const']
            st.rerun()

elif page == "Analytics":
    st.title("📊 Movie Analytics")
    all_genres = []
    for g in df['Genre'].dropna().astype(str):
        if g not in ["N/A", "nan", "None", ""]:
            parts = [p.strip() for p in g.split(',')]
            all_genres.extend(parts)
    
    if all_genres:
        genre_df = pd.Series(all_genres).value_counts().reset_index()
        genre_df.columns = ['Genre', 'Count']
        fig = px.pie(genre_df, values='Count', names='Genre', 
                     title=f'Genre Distribution ({len(df)} Movies Total)',
                     hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
        st.write(f"**Insight:** You have {len(genre_df)} unique genres in your prioritizer.")
    else:
        st.warning("No genre data found.")