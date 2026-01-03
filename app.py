import streamlit as st
import pandas as pd
import glob

# Set Page Config
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
            # IMDb uses latin1 encoding
            temp_df = pd.read_csv(f, encoding='latin1')
            
            # Clean column names (Removes hidden characters/BOM)
            temp_df.columns = temp_df.columns.str.strip().str.replace('ï»¿', '')
            
            # Identify source file (the name of the list)
            temp_df['Source List'] = f.replace('.csv', '')
            all_data.append(temp_df)
        except Exception as e:
            st.warning(f"Skipping {f}: {e}")
            continue
    
    if not all_data:
        return None

    full_df = pd.concat(all_data, ignore_index=True)
    
    # Standardize Numeric Columns
    full_df['IMDb Rating'] = pd.to_numeric(full_df['IMDb Rating'], errors='coerce').fillna(0)
    full_df['Year'] = pd.to_numeric(full_df['Year'], errors='coerce').fillna(0).astype(int)
    
    # Identify key columns dynamically
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
    
    # Hype Score calculation
    agg_dict['Title'] = 'count' 

    agg_df = full_df.groupby(group_keys).agg(agg_dict).rename(columns={'Title': 'Hype Score'})
    
    return agg_df.reset_index().sort_values('Hype Score', ascending=False)

df = load_data()

# Initialize session state
if "movie_choice" not in st.session_state:
    st.session_state.movie_choice = "--- Select a Movie ---"

# --- 2. SIDEBAR FILTERS ---
st.sidebar.title("🔍 David's Filters")

if df is not None and not df.empty:
    # 1. Show Full Master List Button
    if st.sidebar.button("🏠 Show Full Master List", use_container_width=True):
        st.session_state.movie_choice = "--- Select a Movie ---"
        st.rerun()

    # 2. Drill down for details
    movie_titles = ["--- Select a Movie ---"] + sorted(df['Title'].unique().tolist())
    st.sidebar.selectbox("Drill down for details:", movie_titles, key="movie_choice")

    # 3. Title Search
    search_query = st.sidebar.text_input("Title Search:")

    st.sidebar.divider()

    # 4. CSV File Filter
    available_lists = sorted(list(set([item.strip() for sublist in df['Source List'].str.split(',') for item in sublist])))
    selected_lists = st.sidebar.multiselect("Filter by CSV/List Name:", available_lists)

    # 5. Other Data Filters
    min_rating, max_rating = st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, (6.0, 10.0), 0.5)
    yr_min, yr_max = int(df['Year'].min()), int(df['Year'].max())
    year_range = st.sidebar.slider("Release Year", yr_min, yr_max, (yr_min, yr_max))

    all_genres = sorted(list(set([g.strip() for sublist in df['Genres'].dropna().str.split(',') for g in sublist])))
    selected_genres = st.sidebar.multiselect("Specific Genres", all_genres)

    # Apply Filtering Logic to the Table
    filtered_df = df[
        (df['IMDb Rating'] >= min_rating) & 
        (df['IMDb Rating'] <= max_rating) &
        (df['Year'] >= year_range[0]) & 
        (df['Year'] <= year_range[1])
    ]
    
    if selected_lists:
        filtered_df = filtered_df[filtered_df['Source List'].apply(lambda x: any(l in x for l in selected_lists))]

    if selected_genres:
        filtered_df = filtered_df[filtered_df['Genres'].apply(lambda x: any(g in str(x) for g in selected_genres))]
        
    if search_query:
        filtered_df = filtered_df[filtered_df['Title'].str.contains(search_query, case=False)]

else:
    st.sidebar.info("Upload CSV files to enable filters.")

# --- 3. PAGE LOGIC (DISPLAY) ---

if df is None or df.empty:
    st.title("🍿 Movie Prioritizer")
    st.error("No CSV files found!")
    st.info("Upload your IMDb .csv exports to the same GitHub folder as this app.py.")

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
            # Starring row has been removed from here
            
        with col2:
            st.metric("Hype Score", f"{movie['Hype Score']} Lists")
            st.write("**📂 Found in your lists:**")
            st.info(movie.get('Source List', 'N/A'))

        st.divider()
        st.subheader("🔗 Additional Info")
        
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
        st.error(f"Error loading details: {e}")
        if st.button("Return to Master Table"):
            st.session_state.movie_choice = "--- Select a Movie ---"
            st.rerun()
else:
    # --- MAIN TABLE VIEW ---
    st.title("🎬 David's Movie Prioritizer")
    
    if 'filtered_df' in locals() and filtered_df is not None:
        st.markdown(f"Displaying **{len(filtered_df)}** movies. Sorted by **Hype Score**.")
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