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
            temp_df = pd.read_csv(f, encoding='latin1')
            temp_df.columns = [c.strip() for c in temp_df.columns]
            temp_df['Source File'] = f.replace('.csv', '')
            all_data.append(temp_df)
        except:
            continue
    
    if not all_data:
        return None

    full_df = pd.concat(all_data, ignore_index=True)
    full_df['IMDb Rating'] = pd.to_numeric(full_df['IMDb Rating'], errors='coerce').fillna(0)
    full_df['Year'] = pd.to_numeric(full_df['Year'], errors='coerce').fillna(0).astype(int)
    
    agg_df = full_df.groupby(['Const', 'Title', 'Year', 'IMDb Rating']).agg({
        'Source File': lambda x: ", ".join(sorted(set(x))),
        'Genres': 'first',
        'Directors': 'first',
        'URL': 'first',
        'Title': 'count' 
    }).rename(columns={'Title': 'Hype Score'}).reset_index()
    
    return agg_df.sort_values('Hype Score', ascending=False)

df = load_data()

# --- 2. SIDEBAR NAVIGATION ---
st.sidebar.title("🔍 Navigation")

if df is not None:
    # Create a list of titles for the dropdown
    movie_list = ["--- Select a Movie for Details ---"] + df['Title'].tolist()
    choice = st.sidebar.selectbox("Jump to Movie Details:", movie_list)
    
    # Simple search filter for the main table
    search = st.sidebar.text_input("Filter Table by Title:")
else:
    choice = "--- Select a Movie for Details ---"

# --- 3. PAGE LOGIC ---
if choice != "--- Select a Movie for Details ---":
    # DETAIL VIEW
    movie = df[df['Title'] == choice].iloc[0]
    
    if st.button("⬅️ Back to Table"):
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
        st.info(movie['Source File'])

    st.divider()
    st.link_button("🔥 Open on IMDb.com", movie['URL'], use_container_width=True)

else:
    # MAIN TABLE VIEW
    st.title("🎬 Master Movie Prioritizer")
    
    if df is not None:
        # Apply search filter if typed
        display_df = df.copy()
        if search:
            display_df = display_df[display_df['Title'].str.contains(search, case=False)]
        
        st.write("Use the **sidebar dropdown** to see director and actor details.")
        
        st.dataframe(
            display_df[['Title', 'Year', 'IMDb Rating', 'Hype Score']],
            column_config={
                "IMDb Rating": st.column_config.NumberColumn("Rating", format="%.1f ⭐"),
                "Hype Score": st.column_config.NumberColumn("Hype Count", format="%d 📋"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("No CSV files found in the repository. Please upload your exports!")