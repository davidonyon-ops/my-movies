import streamlit as st
import pandas as pd
import glob

# Set Page Config
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. BULLETPROOF DATA LOADING ---
@st.cache_data
def load_data():
    files = glob.glob("*.csv")
    if not files:
        return None
    
    all_data = []
    for f in files:
        try:
            # IMDb uses latin1 encoding for their CSV exports
            temp_df = pd.read_csv(f, encoding='latin1')
            
            # Clean column names (Removes hidden characters/BOM)
            temp_df.columns = temp_df.columns.str.strip().str.replace('ï»¿', '')
            
            # Identify source file
            temp_df['Source List'] = f.replace('.csv', '')
            all_data.append(temp_df)
        except Exception as e:
            st.warning(f"Skipping {f} due to error: {e}")
            continue
    
    if not all_data:
        return None

    full_df = pd.concat(all_data, ignore_index=True)
    
    # Standardize Numeric Columns
    full_df['IMDb Rating'] = pd.to_numeric(full_df['IMDb Rating'], errors='coerce').fillna(0)
    full_df['Year'] = pd.to_numeric(full_df['Year'], errors='coerce').fillna(0).astype(int)
    
    # Identify key columns dynamically to prevent KeyErrors
    cols = full_df.columns
    group_keys = [c for c in ['Const', 'Title', 'Year', 'IMDb Rating'] if c in cols]
    
    if 'Title' not in group_keys:
        return None

    # Aggregation mapping
    agg_dict = {}
    if 'Source List' in cols: agg_dict['Source List'] = lambda x: ", ".join(sorted(set(x.astype(str))))
    if 'Genres' in cols: agg_dict['Genres'] = 'first'
    if 'Directors' in cols: agg_dict['Directors'] = 'first'
    if 'URL' in cols: agg_dict['URL'] = 'first'
    
    # Identify Cast/Stars column
    cast_col = next((c for c in ['Stars', 'Cast', 'Starring'] if c in cols), None)
    if cast_col:
        agg_dict[cast_col] = 'first'
    
    # Add Hype Score (count of occurrences across CSVs)
    agg_dict['Title'] = 'count'

    # Perform Grouping
    agg_df = full_df.groupby(group_keys).agg(agg_dict).rename(columns={'Title': 'Hype Score'})
    
    # Rename Cast to Actors if found
    if cast_col:
        agg_df = agg_df.rename(columns={cast_col: 'Actors'})
    else:
        agg_df['Actors'] = "N/A"
        
    return agg_df.reset_index().sort_values('Hype Score', ascending=False)

# --- EXECUTE DATA LOAD ---
df = load_data()

# Initialize filtered_df and session state
filtered_df = None
if "movie_choice" not in st.session_state:
    st.session_state.movie_choice = "--- Select a Movie ---"

# --- 2. SIDEBAR FILTERS ---
st.sidebar.title("🔍 David's Filters")

if df is not None and not df.empty:
    # Navigation: Reset to Master Table
    if st.sidebar.button("🏠 Show Full Master List", use_container_width=True):
        st.session_state.movie_choice = "--- Select a Movie ---"
        st.rerun()

    st.sidebar.divider()

    # Mood Presets
    mood = st.sidebar.selectbox("Vibe Check", 
                                ["Any", "Chill / Comedy", "Intense / Thriller", "Scary / Horror", "Action Packed"])
    
    mood_map = {
        "Chill / Comedy": ["Comedy", "Romance", "Animation", "Family"],
        "Intense / Thriller": ["Thriller", "Crime", "Mystery", "Drama"],
        "Scary / Horror": ["Horror"],
        "Action Packed": ["Action", "Adventure", "Sci-Fi"]
    }

    # Range Filters
    min_rating, max_rating = st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, (6.0, 10.0), 0.5)
    yr_min, yr_max = int(df['Year'].min()), int(df['Year'].max())
    year_range = st.sidebar.slider("Release Year", yr_min, yr_max, (yr_min, yr_max))

    # Search & Genre
    all_genres = sorted(list(set([g.strip() for sublist in df['Genres'].dropna().str.split(',') for g in sublist])))
    selected_genres = st.sidebar.multiselect("Specific Genres", all_genres)
    search_query = st.sidebar.text_input("Title Search:")

    # Apply Logic
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
    
    # Detail Dropdown
    movie_titles = ["--- Select a Movie ---"] + filtered_df['Title'].tolist()
    st.sidebar.selectbox("Drill down for details:", movie_titles, key="movie_choice")

# --- 3. PAGE LOGIC (DISPLAY) ---

if df is None or df.empty:
    st.title("🍿 Movie Prioritizer")
    st.error("No CSV files found in the repository!")
    st.info("Please upload your IMDb .csv exports to the same GitHub folder as this app.py.")

elif st.session_state.movie_choice != "--- Select a Movie ---":
    # --- DETAIL PAGE VIEW ---
    try:
        movie = df[df['Title'] == st.session_state.movie_choice].iloc[0]
        
        st.header(f"{movie['Title']} ({movie['Year']})")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("IMDb Rating", f"{movie['IMDb Rating']} ⭐")
            st.write(f"**🎬 Director:** {movie.get('Directors', 'N/A')}")
            st.write(f"**🎭 Genres:** {movie.get('Genres', 'N/A')}")
            st.write(f"**🌟 Starring:** {movie.get('Actors', 'N/A')}")
            
        with col2:
            st.metric("Hype Score", f"{movie['Hype Score']} Lists")
            st.write("**📂 Found in your lists:**")
            st.info(movie.get('Source List', 'N/A'))

        st.divider()
        st.subheader("🇬🇧 Where to Watch in the UK")
        
        btn1, btn2, btn3 = st.columns(3)
        with btn1:
            st.link_button("🎥 IMDb Page", movie.get('URL', '#'), use_container_width=True)
        with btn2:
            rt_url = f"https://www.rottentomatoes.com/search?search={movie['Title'].replace(' ', '%20')}"
            st.link_button("🍅 Rotten Tomatoes", rt_url, use_container_width=True)
        with btn3:
            jw_url = f"https://www.justwatch.com/uk/search?q={movie['Title'].replace(' ', '%20')}"
            st.link_button("📺 Check UK Streaming", jw_url, use_container_width=True, type="primary")
            
    except Exception as e:
        st.error(f"Error loading movie details: {e}")
        if st.button("Return to Master Table"):
            st.session_state.movie_choice = "--- Select a Movie ---"
            st.rerun()

else:
    # --- MAIN TABLE VIEW ---
    st.title("🎬 David's Movie Prioritizer")
    
    if filtered_df is not None:
        st.markdown(f"Displaying **{len(filtered_df)}** movies matching your filters. Sorted by **Hype Score**.")
        
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