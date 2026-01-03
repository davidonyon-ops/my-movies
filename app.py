import streamlit as st
import pandas as pd
import glob

# Set Page Config
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. DATA LOADING ---
@st.cache_data
def load_data():
    files = glob.glob("*.csv")
    if not files: return None
    all_data = []
    for f in files:
        try:
            temp_df = pd.read_csv(f, encoding='latin1')
            temp_df.columns = temp_df.columns.str.strip().str.replace('ï»¿', '')
            temp_df['Source List'] = f.replace('.csv', '')
            all_data.append(temp_df)
        except: continue
    if not all_data: return None
    
    full_df = pd.concat(all_data, ignore_index=True)
    full_df['IMDb Rating'] = pd.to_numeric(full_df['IMDb Rating'], errors='coerce').fillna(0)
    full_df['Year'] = pd.to_numeric(full_df['Year'], errors='coerce').fillna(0).astype(int)
    
    cols = full_df.columns
    group_keys = [c for c in ['Const', 'Title', 'Year', 'IMDb Rating'] if c in cols]
    
    agg_dict = {
        'Source List': lambda x: ", ".join(sorted(set(x.astype(str)))),
        'Genres': 'first', 
        'Directors': 'first', 
        'URL': 'first', 
        'Title': 'count'
    }
    
    agg_df = full_df.groupby(group_keys).agg(agg_dict).rename(columns={'Title': 'Hype Score'})
    return agg_df.reset_index().sort_values('Hype Score', ascending=False)

df = load_data()

# --- 2. SESSION STATE ---
if "watched_ids" not in st.session_state:
    st.session_state.watched_ids = set() # Replace with your GSheet loading logic if using
if "movie_choice" not in st.session_state:
    st.session_state.movie_choice = "--- Select a Movie ---"

# --- 3. SIDEBAR ---
st.sidebar.title("🔍 David's Filters")

if df is not None:
    # Navigation
    if st.sidebar.button("🏠 Show Full Master List", use_container_width=True):
        st.session_state.movie_choice = "--- Select a Movie ---"
        st.rerun()

    # Drill down & Search
    movie_titles = ["--- Select a Movie ---"] + sorted(df['Title'].unique().tolist())
    st.sidebar.selectbox("Drill down for details:", movie_titles, key="movie_choice")
    search_query = st.sidebar.text_input("Title Search:")
    
    st.sidebar.divider()
    
    # Watched & CSV Filters
    hide_watched = st.sidebar.checkbox("Hide Watched Movies", value=False)
    available_lists = sorted(list(set([item.strip() for sublist in df['Source List'].str.split(',') for item in sublist])))
    selected_lists = st.sidebar.multiselect("Filter by CSV Name:", available_lists)
    
    # DATA FILTERS (Rating & Year)
    min_rating, max_rating = st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, (6.0, 10.0), 0.5)
    
    # Restored Year Filter
    yr_min, yr_max = int(df['Year'].min()), int(df['Year'].max())
    year_range = st.sidebar.slider("Release Year", yr_min, yr_max, (yr_min, yr_max))

    all_genres = sorted(list(set([g.strip() for sublist in df['Genres'].dropna().str.split(',') for g in sublist])))
    selected_genres = st.sidebar.multiselect("Specific Genres", all_genres)

    # Apply All Logic
    filtered_df = df[
        (df['IMDb Rating'] >= min_rating) & 
        (df['IMDb Rating'] <= max_rating) &
        (df['Year'] >= year_range[0]) & 
        (df['Year'] <= year_range[1])
    ].copy()

    if hide_watched:
        filtered_df = filtered_df[~filtered_df['Const'].astype(str).isin(st.session_state.watched_ids)]
    if selected_lists:
        filtered_df = filtered_df[filtered_df['Source List'].apply(lambda x: any(l in x for l in selected_lists))]
    if selected_genres:
        filtered_df = filtered_df[filtered_df['Genres'].apply(lambda x: any(g in str(x) for g in selected_genres))]
    if search_query:
        filtered_df = filtered_df[filtered_df['Title'].str.contains(search_query, case=False)]

# --- 4. PAGE LOGIC ---
if st.session_state.movie_choice != "--- Select a Movie ---":
    # DETAIL PAGE
    movie = df[df['Title'] == st.session_state.movie_choice].iloc[0]
    m_id = str(movie['Const'])
    
    st.header(f"{movie['Title']} ({movie['Year']})")
    
    # Watched Button
    if m_id in st.session_state.watched_ids:
        if st.button("✅ Watched (Click to unmark)"):
            st.session_state.watched_ids.remove(m_id)
            st.rerun()
    else:
        if st.button("👁️ Mark as Watched"):
            st.session_state.watched_ids.add(m_id)
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("IMDb Rating", f"{movie['IMDb Rating']} ⭐")
        st.write(f"**🎬 Director:** {movie.get('Directors', 'N/A')}")
        st.write(f"**🎭 Genres:** {movie.get('Genres', 'N/A')}")
    with col2:
        st.metric("Hype Score", f"{movie['Hype Score']} Lists")
        st.info(f"**📂 Lists:** {movie.get('Source List', 'N/A')}")

    st.divider()
    st.subheader("🔗 Additional Info")
    b1, b2, b3 = st.columns(3)
    with b1: st.link_button("🎥 IMDb", movie.get('URL', '#'), use_container_width=True)
    with b2: st.link_button("🍅 Rotten Tomatoes", f"https://www.rottentomatoes.com/search?search={movie['Title'].replace(' ', '%20')}", use_container_width=True)
    with b3: st.link_button("📺 UK Streaming", f"https://www.justwatch.com/uk/search?q={movie['Title'].replace(' ', '%20')}", use_container_width=True, type="primary")

else:
    # MAIN TABLE
    st.title("🎬 David's Movie Prioritizer")
    if 'filtered_df' in locals() and filtered_df is not None:
        st.dataframe(
            filtered_df[['Title', 'Year', 'IMDb Rating', 'Hype Score']], 
            hide_index=True, 
            use_container_width=True
        )