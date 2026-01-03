import streamlit as st
import pandas as pd
import glob

st.title("🎬 David's Movie Prioritizer")

# Load all CSVs
files = glob.glob("*.csv")
if files:
    all_data = []
    for f in files:
        temp_df = pd.read_csv(f, encoding='latin1')
        temp_df['List Source'] = f.replace('.csv', '')
        all_data.append(temp_df)
    
    df = pd.concat(all_data)
    
    # Calculate "Hype Score" (how many lists a movie appears in)
    hype = df.groupby(['Title', 'Year', 'IMDb Rating', 'Genres']).size().reset_index(name='Hype Score')
    
    # Show the table
    st.write("### Your Ranked Movies")
    st.dataframe(hype.sort_values('Hype Score', ascending=False))
else:
    st.write("Upload your CSVs to see your list!")