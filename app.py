import streamlit as st
import pandas as pd
import glob

# Page Config
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. DATA LOADING & CLEANING ---
@st.cache_data
def load_data():
    files = glob.glob("*.csv")
    if not files:
        return None
    
    all_data = []
    for f in files:
        try:
            # Standard IMDb export encoding
            temp_df = pd.read_csv(f, encoding='latin1')
            
            # CLEAN COLUMN NAMES: This removes hidden characters and spaces
            temp_df.columns = temp_df.columns.str.strip().str.replace('ï»¿', '')
            
            # Add Source
            temp_df['Source List'] = f.replace('.csv', '')
            all_data.append(temp_df)
        except Exception as e:
            st.warning(f"Could not read {f}: {e}")
            continue
    
    if not all_data:
        return None

    full_df = pd.concat(all_data, ignore_index=True)
    
    # 1. Standardize Numeric Columns
    full_df['IMDb Rating'] = pd.to_numeric(full_df['IMDb Rating'], errors='coerce').fillna(0)
    full_df['Year'] = pd.to_numeric(full_df['Year'], errors='coerce').fillna(0).astype(int)
    
    # 2. DYNAMICALLY Identify existing columns to prevent KeyErrors
    cols = full_df.columns
    group_cols = [c for c in ['Const', 'Title', 'Year', 'IMDb Rating'] if c in cols]
    
    # Ensure Title is in group_cols; if 'Const' is missing, use Title as ID
    if 'Title' not in group_cols:
        return None # Critical failure if Title is missing

    # Build the aggregation dictionary safely
    agg_dict = {}
    if 'Source List' in cols: agg_dict['Source List'] = lambda x: ", ".join(sorted(set(x.astype(str))))
    if 'Genres' in cols: agg_dict['Genres'] = 'first'
    if 'Directors' in cols: agg_dict['Directors'] = 'first'
    if 'URL' in cols: agg_dict['URL'] = 'first'
    
    # Look for the cast column
    cast_col = next((c for c in ['Stars', 'Cast', 'Starring'] if c in cols), None)
    if cast_col:
        agg_dict[cast_col] = 'first'
    
    # Add the Hype Score counter
    agg_dict['Title'] = 'count'

    # 3. Perform the Aggregation
    agg_df = full_df.groupby(group_cols).agg(agg_dict).rename(columns={'Title': 'Hype Score'})
    
    # Rename Cast/Stars to 'Actors' if found
    if cast_col:
        agg_df = agg_df.rename(columns={cast_col: 'Actors'})
    else:
        agg_df['Actors'] = "N/A"
        
    return agg_df.reset_index().sort_values('Hype Score', ascending=False)

# --- 2. SIDEBAR FILTERS ---
st.sidebar.title("🔍 Filters & Moods")

if df is not None:
    # 🔁 Reset Navigation
    if st.sidebar.button("🏠 Show Full Master List", use_container_width=True):
        st.session_state.movie_choice = "--- Select a Movie ---"
        st.rerun()

    st.sidebar.divider()

    # 🎭 Mood Filter (Custom mapping for quick decisions)
    mood = st.sidebar.selectbox("What's the vibe?", 
                                ["Any", "Chill / Comedy", "Intense / Thriller", "Scary / Horror", "Action Packed"])
    
    mood_map = {
        "Chill / Comedy": ["Comedy", "Romance", "Animation", "Family"],
        "Intense / Thriller": ["Thriller", "Crime", "Mystery", "Drama"],
        "Scary / Horror": ["Horror"],
        "Action Packed": ["Action", "Adventure", "Sci-Fi"]
    }

    # ⭐ Rating Slider
    min_rating, max_rating = st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, (6.0, 10.0), 0.5)
    
    # 📅 Year Slider
    yr_min, yr_max = int(df['Year'].min()), int(df['Year'].max())
    year_range = st.sidebar.slider("Release Year", yr_min, yr_max, (yr_min, yr_max))

    # 📑 Genre Multiselect
    all_genres = sorted(list(set([g.strip() for sublist in df['Genres'].dropna().str.split(',') for g in sublist])))
    selected_genres = st.sidebar.multiselect("Specific Genres", all_genres)

    # ⌨️ Title Search
    search_query = st.sidebar.text_input("Search Title:")

    # Apply All Filters
    filtered_df = df[
        (df['IMDb Rating'] >= min_rating) & 
        (df['IMDb Rating'] <= max_rating) &
        (df['Year'] >= year_range[0]) & 
        (df['Year'] <= year_range[1])
    ]
    
    if mood != "Any":
        filtered_df = filtered_df[filtered_df['Genres'].apply(lambda x: any(m in str(x) for m in mood_map[mood]))]
    
    if selected_genres:
        filtered_df = filtered_df[filtered_df['Genres'].apply(lambda x: any(g in str(x) for g in selected_genres))]
        
    if search_query:
        filtered_df = filtered_df[filtered_df['Title'].str.contains(search_query, case=False)]

    st.sidebar.divider()
    
    # 🎬 Movie Selection
    if "movie_choice" not in st.session_state:
        st.session_state.movie_choice = "--- Select a Movie ---"

    selected_movie_title = st.sidebar.selectbox(
        "Drill down into movie:", 
        ["--- Select a Movie ---"] + filtered_df['Title'].tolist(),
        key="movie_choice"
    )

# --- 3. PAGE LOGIC ---

if df is None:
    st.error("No CSV files found. Please upload your IMDb exports to your GitHub repository.")
    st.info("Make sure the files are in the same folder as this app.py file.")

elif st.session_state.movie_choice != "--- Select a Movie ---":
    # --- DETAIL PAGE ---
    movie = df[df['Title'] == st.session_state.movie_choice].iloc[0]
    
    st.header(f"{movie['Title']} ({movie['Year']})")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("IMDb Rating", f"{movie['IMDb Rating']} ⭐")
        st.write(f"**🎬 Director:** {movie['Directors']}")
        st.write(f"**🎭 Genres:** {movie['Genres']}")
        st.write(f"**🌟 Starring:** {movie['Actors']}")
        
    with col2:
        st.metric("Hype Score", f"{movie['Hype Score']} Lists")
        st.write("**📂 Appears in your lists:**")
        st.info(movie['Source List'])

    st.divider()
    
    st.subheader("🇬🇧 Where to Watch in the UK")
    st.write("Check if it's on Netflix, Disney+, or available to rent on Prime/Apple.")
    
    btn1, btn2, btn3 = st.columns(3)
    with btn1:
        st.link_button("🎥 IMDb Page", movie['URL'], use_container_width=True)
    with btn2:
        rt_url = f"https://www.rottentomatoes.com/search?search={movie['Title'].replace(' ', '%20')}"
        st.link_button("🍅 Rotten Tomatoes", rt_url, use_container_width=True)
    with btn3:
        # Direct JustWatch UK Search
        jw_url = f"https://www.justwatch.com/uk/search?q={movie['Title'].replace(' ', '%20')}"
        st.link_button("📺 Check UK Streaming", jw_url, use_container_width=True, type="primary")

else:
    # --- MAIN TABLE PAGE ---
    st.title("🎬 David's Movie Prioritizer")
    st.markdown(f"Showing **{len(filtered_df)}** movies based on your filters. Sorted by **Hype Score** (how many of your lists the movie is in).")
    
    st.dataframe(
        filtered_df[['Title', 'Year', 'IMDb Rating', 'Hype Score']],
        column_config={
            "IMDb Rating": st.column_config.NumberColumn("Rating", format="%.1f ⭐"),
            "Hype Score": st.column_config.NumberColumn("Hype Count", format="%d 📋"),
            "Title": st.column_config.TextColumn("Movie Title", width="large")
        },
        hide_index=True,
        use_container_width=True
    )