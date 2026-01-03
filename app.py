import streamlit as st
import pandas as pd
import glob

st.set_page_config(page_title="Movie Prioritizer", layout="wide", page_icon="🍿")

# --- 1. DATA LOADING ---
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
            temp_df.columns = [c.strip() for c in temp_df.columns]
            # Track which list this movie came from
            temp_df['Source File'] = f.replace('.csv', '')
            all_data.append(temp_df)
        except:
            continue
    
    full_df = pd.concat(all_data, ignore_index=True)
    
    # Data Cleaning
    full_df['IMDb Rating'] = pd.to_numeric(full_df['IMDb Rating'], errors='coerce').fillna(0)
    full_df['Year'] = pd.to_numeric(full_df['Year'], errors='coerce').fillna(0).astype(int)
    
    # Grouping to calculate Hype Score
    # We keep 'Directors' and 'Genres' to show on the detail page
    agg_df = full_df.groupby(['Const', 'Title', 'Year', 'IMDb Rating']).agg({
        'Source File': lambda x: ", ".join(sorted(set(x))),
        'Genres': 'first',
        'Directors': 'first',
        'URL': 'first',
        'Title': 'count' # This counts appearances across lists
    }).rename(columns={'Title': 'Hype Score'}).reset_index()
    
    return agg_df

df = load_data()

# --- 2. SESSION STATE (Navigation) ---
if "selected_movie" not in st.session_state:
    st.session_state.selected_movie = None

# --- 3. DETAIL PAGE VIEW ---
if st.session_state.selected_movie:
    # Filter the df for the specific movie ID
    movie = df[df['Const'] == st.session_state.selected_movie].iloc[0]
    
    if st.button("⬅️ Back to Master List"):
        st.session_state.selected_movie = None
        st.rerun()
    
    st.header(f"{movie['Title']} ({movie['Year']})")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("IMDb Rating", f"{movie['IMDb Rating']} ⭐")
        st.write(f"**🎬 Director:** {movie['Directors']}")
        st.write(f"**🎭 Genres:** {movie['Genres']}")
        
    with col2:
        st.metric("Hype Score", f"{movie['Hype Score']} Lists")
        st.write(f"**📂 Found in your lists:**")
        st.code(movie['Source File'], language=None)

    st.divider()
    st.link_button("🔥 Open on IMDb.com", movie['URL'], use_container_width=True)

# --- 4. MAIN LIST VIEW ---
else:
    st.title("🎬 Master Movie Prioritizer")
    st.write("Click a row to see more details and original list sources.")

    if df is not None:
        # We display the data and catch the 'selection' event
        event = st.dataframe(
            df[['Title', 'Year', 'IMDb Rating', 'Hype Score']],
            column_config={
                "IMDb Rating": st.column_config.NumberColumn("Rating", format="%.1f ⭐"),
                "Hype Score": st.column_config.ProgressColumn("Hype Score", min_value=0, max_value=int(df['Hype Score'].max())),
            },
            hide_index=True,
            use_container_width=True,
            on_select="rerun", # This makes the app respond when you click a row
            selection_mode="single_row"
        )

        # If a user clicks a row, save that movie ID to session state
        if event and event.selection.rows:
            selected_idx = event.selection.rows[0]
            st.session_state.selected_movie = df.iloc[selected_idx]['Const']
            st.rerun()
    else:
        st.error("No CSV files found. Please upload your IMDb exports to GitHub!")