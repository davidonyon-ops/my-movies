import streamlit as st
import pandas as pd
import glob
from streamlit_gsheets import GSheetsConnection

# Set Page Config
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. DATA LOADING (IMDb CSVs) ---
@st.cache_data
def load_imdb_data():
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
    agg_dict = {'Source List': lambda x: ", ".join(sorted(set(x.astype(str)))),
                'Genres': 'first', 'Directors': 'first', 'URL': 'first', 'Title': 'count'}
    
    agg_df = full_df.groupby(group_keys).agg(agg_dict).rename(columns={'Title': 'Hype Score'}).reset_index()
    return agg_df.sort_values('Hype Score', ascending=False)

# --- 2. GOOGLE SHEETS CONNECTION (Watched List) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_watched_list():
    try:
        # Read the 'Const' column from the Google Sheet
        data = conn.read(ttl=0) # ttl=0 ensures it doesn't cache old data
        return set(data['Const'].astype(str).tolist())
    except:
        return set()

def update_watched_sheet(new_watched_set):
    # Convert set back to DataFrame and update the Google Sheet
    new_df = pd.DataFrame(list(new_watched_set), columns=['Const'])
    conn.update(data=new_df)
    st.cache_data.clear() # Clear cache to show changes immediately

# --- 3. SESSION STATE ---
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
    st.sidebar.divider()
    
    hide_watched = st.sidebar.checkbox("Hide Watched Movies", value=True)
    
    # List & Data Filters
    lists = sorted(list(set([i.strip() for s in df['Source List'].str.split(',') for i in s])))
    selected_lists = st.sidebar.multiselect("Filter by CSV Name:", lists)
    min_rating = st.sidebar.slider("Min IMDb Rating", 0.0, 10.0, 6.0, 0.5)
    yr_min, yr_max = int(df['Year'].min()), int(df['Year'].max())
    year_range = st.sidebar.slider("Release Year", yr_min, yr_max, (yr_min, yr_max))

    # Apply Filtering
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

# --- 5. PAGE LOGIC ---
if st.session_state.selected_movie_id:
    # DETAIL PAGE
    movie = df[df['Const'] == st.session_state.selected_movie_id].iloc[0]
    m_id = str(movie['Const'])
    
    st.header(f"{movie['Title']} ({movie['Year']})")
    
    if m_id in st.session_state.watched_ids:
        if st.button("✅ Watched (Click to unmark)"):
            st.session_state.watched_ids.remove(m_id)
            update_watched_sheet(st.session_state.watched_ids)
            st.rerun()
    else:
        if st.button("👁️ Mark as Watched"):
            st.session_state.watched_ids.add(m_id)
            update_watched_sheet(st.session_state.watched_ids)
            st.rerun()

    # Information Display
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
    st.write("💡 **Check the 'View' box** to see details.")
    
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