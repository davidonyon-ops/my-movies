import streamlit as st
import pandas as pd
import glob
import requests

# Set Page Config
st.set_page_config(page_title="David's Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. SETTINGS (ACTION REQUIRED) ---
# 1. Your Google Sheet CSV Link (ends in /export?format=csv)
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/12o_X4-184BAPYKZqzqcjv4GEsBtisVWl8bvE4Pyne64/export?format=csv&gid=2013918688#gid=2013918688"

# 2. Your Google Form Submission URL (ends in /formResponse)
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdgws-uAGliOfkv7nDXonUEIyhl9snn5-DWzl20StGpo6RrCA/formResponse"

# 3. Your Entry ID (the bit before =TEST, e.g., 'entry.123456789')
ENTRY_ID_CONST = "entry.505487716"
ENTRY_ID_TITLE = "entry.1090297045" 
ENTRY_ID_SOURCE = "entry.1247422407" 

# --- 2. DATA LOADING ---
@st.cache_data
@st.cache_data(ttl=300)
def load_imdb_data():
    # A. Load your IMDb files from GitHub
    files = glob.glob("*.csv")
    all_data = []
    for f in files:
        try:
            temp_df = pd.read_csv(f, encoding='latin1')
            temp_df.columns = temp_df.columns.str.strip().str.replace('ï»¿', '')
            temp_df['Source List'] = f.replace('.csv', '')
            all_data.append(temp_df)
        except: continue
    
    master_df = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    # B. Load Manual Entries from Google Sheet
    try:
        sheet_df = pd.read_csv(f"{SHEET_CSV_URL}&cache={int(time.time())}")
        sheet_df.columns = sheet_df.columns.str.strip()
        
                # Temporary debug line - add this inside load_imdb_data
st.sidebar.write("Columns found in Sheet:", list(sheet_df.columns))
st.sidebar.write("Rows with MANUAL:", len(sheet_df[sheet_df['Const'] == "MANUAL"]))
        
        # Look for rows marked as "MANUAL"
        if 'Const' in sheet_df.columns:
            manual_rows = sheet_df[sheet_df['Const'] == "MANUAL"].copy()
            manual_rows['Year'] = 2026 
            manual_rows['IMDb Rating'] = 0.0
            # Use 'Source' column if it exists, otherwise call it 'Manual'
            manual_rows['Source List'] = manual_rows['Source'] if 'Source' in manual_rows.columns else "Manual Entry"
            # Create a fake ID so the "Watched" button works for these too
            manual_rows['Const'] = "M_" + manual_rows['Title'].astype(str)
            
            master_df = pd.concat([master_df, manual_rows], ignore_index=True)
    except:
        pass # If sheet is empty, just use GitHub data

    # C. Grouping and Hype Score
    master_df['IMDb Rating'] = pd.to_numeric(master_df['IMDb Rating'], errors='coerce').fillna(0)
    master_df['Year'] = pd.to_numeric(master_df['Year'], errors='coerce').fillna(0).astype(int)
    
    agg_df = master_df.groupby(['Title', 'Year', 'Const']).agg({
        'Source List': lambda x: ", ".join(sorted(set(x.astype(str)))),
        'IMDb Rating': 'max'
    }).reset_index()
    
    agg_df['Hype Score'] = agg_df['Source List'].str.count(',') + 1
    return agg_df.sort_values('Hype Score', ascending=False)

def get_watched_list():
    try:
        # 1. We add a random number to the URL to force Google to give us the freshest data
        import time
        cache_buster = f"&cache_bust={int(time.time())}"
        
        # 2. Read the CSV from the sheet
        watched_df = pd.read_csv(SHEET_CSV_URL + cache_buster)
        
        # 3. Clean the data: Remove spaces and make sure everything is a string
        if 'Const' in watched_df.columns:
            # .strip() removes any accidental spaces before or after the ID
            watched_ids = watched_df['Const'].astype(str).str.strip().unique().tolist()
            return set(watched_ids)
        else:
            # This helps us debug if the header is wrong
            st.warning(f"Column 'Const' not found. Available columns: {list(watched_df.columns)}")
            return set()
    except Exception as e:
        st.error(f"Error reading watched list: {e}")
        return set()

def mark_as_watched_permanent(const_id):
    # This sends the ID to your Google Form
    form_data = {ENTRY_ID: const_id} 
    try:
        response = requests.post(FORM_URL, data=form_data)
        if response.status_code == 200:
            st.session_state.watched_ids.add(const_id)
            return True
        return False
    except:
        return False

def add_manual_movie(title, source_name):
    form_data = {
        ENTRY_ID_TITLE: title, 
        ENTRY_ID_SOURCE: source_name,
        ENTRY_ID_CONST: "MANUAL"
    }
    try:
        requests.post(FORM_URL, data=form_data)
        return True
    except:
        return False

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

st.sidebar.divider()
st.sidebar.subheader("➕ Quick Add Movie")

with st.sidebar.form("add_movie_form", clear_on_submit=True):
    new_title = st.text_input("Movie Title")
    new_source = st.text_input("Where did you hear about it?")
    
    submitted = st.form_submit_button("Add to List")
    
    if submitted and new_title:
        final_source = new_source if new_source else "Manual"
        if add_manual_movie(new_title, final_source):
            st.success(f"Added {new_title}!")
            st.cache_data.clear() # Forces the app to see the new movie
            st.rerun()

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
                # Give the sheet a second to update before refreshing
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