import streamlit as st
import pandas as pd
import glob
import requests
import time
import plotly.express as px

# Set Page Config
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. SETTINGS ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/12o_X4-184BAPYKZqzqcjv4GEsBtisVWl8bvE4Pyne64/export?format=csv&gid=2013918688"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdgws-uAGliOfkv7nDXonUEIyhl9snn5-DWzl20StGpo6RrCA/formResponse"
ENTRY_ID_CONST, ENTRY_ID_TITLE, ENTRY_ID_SOURCE = "entry.505487716", "entry.1090297045", "entry.1247422407"
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
            parts = source_col[mask].str.split(' \| ')
            manual_clean['Source List'] = parts.str[0]
            manual_clean['Year'] = pd.to_numeric(parts.str[1], errors='coerce').astype('Int64')
            manual_clean['IMDb Rating'] = pd.to_numeric(parts.str[2].str.replace('⭐', '', regex=False), errors='coerce')
            manual_clean['Const'] = parts.str[3]
            manual_clean['Genre'] = parts.str[4]
            manual_clean['Director'] = parts.str[5]
            manual_clean['Actors'] = parts.str[6]
            master_df = pd.concat([master_df, manual_clean], ignore_index=True)
    except: pass
    for col in ['Genre', 'Director', 'Actors', 'IMDb Rating', 'Year', 'Const']:
        if col not in master_df.columns: master_df[col] = "N/A"
    master_df['IMDb Rating'] = pd.to_numeric(master_df['IMDb Rating'], errors='coerce').fillna(0)
    master_df['Year'] = pd.to_numeric(master_df['Year'], errors='coerce').fillna(0).astype(int)
    agg_df = master_df.groupby(['Title', 'Year', 'Const']).agg({
        'Source List': lambda x: ", ".join(sorted(set(x.astype(str)))),
        'IMDb Rating': 'max', 'Genre': 'first', 'Director': 'first', 'Actors': 'first'
    }).reset_index()
    agg_df['Hype Score'] = agg_df['Source List'].str.count(',') + 1
    return agg_df.sort_values('Hype Score', ascending=False)

# --- 3. SESSION STATE INITIALIZATION ---
df = load_imdb_data()
yr_min, yr_max = int(df['Year'].min()) if not df.empty else 1900, 2026

if "p_rating" not in st.session_state: st.session_state.p_rating = 6.0
if "p_years" not in st.session_state: st.session_state.p_years = (yr_min, yr_max)
if "p_search" not in st.session_state: st.session_state.p_search = ""
if "p_hide" not in st.session_state: st.session_state.p_hide = True
if "selected_movie_id" not in st.session_state: st.session_state.selected_movie_id = None
if "watched_ids" not in st.session_state:
    try:
        w_df = pd.read_csv(SHEET_CSV_URL)
        st.session_state.watched_ids = set(w_df['Const'].astype(str).unique())
    except: st.session_state.watched_ids = set()

# --- 4. SIDEBAR (ALWAYS VISIBLE) ---
st.sidebar.title("🎮 Navigation")
page = st.sidebar.radio("Go to:", ["Movie List", "Analytics"])

st.sidebar.divider()
st.sidebar.title("🔍 Filters")

# The "Back" button now simply clears the ID
if st.sidebar.button("🏠 Back to Master Table", use_container_width=True):
    st.session_state.selected_movie_id = None
    st.rerun()

# WIDGETS (Moving these outside the 'if page' block makes them persistent)
st.sidebar.text_input("Title Search:", key="p_search")
st.sidebar.checkbox("Hide Watched Movies", key="p_hide")
st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, step=0.5, key="p_rating")
st.sidebar.slider("Release Year", yr_min, yr_max, key="p_years")

# --- 5. FILTERING LOGIC (GLOBAL) ---
filtered_df = df.copy()
filtered_df = filtered_df[filtered_df['IMDb Rating'] >= st.session_state.p_rating]
y_low, y_high = st.session_state.p_years
filtered_df = filtered_df[(filtered_df['Year'] >= y_low) & (filtered_df['Year'] <= y_high)]

if st.session_state.p_hide:
    filtered_df = filtered_df[~filtered_df['Const'].astype(str).isin(st.session_state.watched_ids)]

if st.session_state.p_search:
    filtered_df = filtered_df[filtered_df['Title'].str.contains(st.session_state.p_search, case=False)]

# --- 6. MAIN DISPLAY ---
if page == "Movie List":
    if st.session_state.selected_movie_id:
        # DETAIL VIEW
        movie = df[df['Const'] == st.session_state.selected_movie_id].iloc[0]
        st.header(f"{movie['Title']} ({movie['Year']})")
        
        # Poster Logic
        res = requests.get(f"http://www.omdbapi.com/?i={movie['Const']}&apikey={OMDB_API_KEY}").json()
        poster = res.get("Poster") if res.get("Poster") != "N/A" else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            if poster: st.image(poster)
            else: st.info("No Poster")
        with col2:
            st.metric("Rating", f"{movie['IMDb Rating']} ⭐")
            st.write(f"**Director:** {movie['Director']}")
            st.write(f"**Cast:** {movie['Actors']}")
            if st.button("👁️ Mark Watched"):
                requests.post(FORM_URL, data={ENTRY_ID_CONST: movie['Const']})
                st.session_state.watched_ids.add(str(movie['Const']))
                st.session_state.selected_movie_id = None
                st.rerun()
    else:
        # TABLE VIEW
        st.title("🎬 David's Movie Prioritizer")
        display_df = filtered_df[['Title', 'Year', 'IMDb Rating', 'Hype Score']].copy()
        display_df.insert(0, "View", False)
        
        edited_df = st.data_editor(display_df, hide_index=True, use_container_width=True, key="main_editor")
        
        # Selection Logic
        if edited_df['View'].any():
            selected_title = edited_df[edited_df['View'] == True].iloc[0]['Title']
            st.session_state.selected_movie_id = filtered_df[filtered_df['Title'] == selected_title].iloc[0]['Const']
            st.rerun()

elif page == "Analytics":
    st.title("📊 Analytics")
    fig = px.histogram(df, x="IMDb Rating", title="Rating Distribution")
    st.plotly_chart(fig)