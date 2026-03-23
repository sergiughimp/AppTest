import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium

# Title
st.title("Hello, World! 👋")
st.write("Welcome to my first Streamlit app.")

# User input
name = st.text_input("What's your name?")
if name:
    st.success(f"Hello, {name}! 🎉")

# ---------------------------
# Load CSV data
# ---------------------------
@st.cache_data
def load_data():
    return pd.read_csv("data/processed/measurements.csv")

df = load_data()

st.subheader("📊 Measurements Data")
st.write(df.head())

# Basic stats
st.subheader("📈 Summary Statistics")
st.write(df.describe())

# ---------------------------
# Load GeoJSON
# ---------------------------
@st.cache_data
def load_geojson():
    with open("data/geo/camden.json") as f:
        return json.load(f)

geo_data = load_geojson()

# ---------------------------
# Map
# ---------------------------
st.subheader("🗺️ Camden Map")

# Center around Camden (approx coords)
m = folium.Map(location=[51.54, -0.14], zoom_start=12)

# Add GeoJSON layer
folium.GeoJson(
    geo_data,
    name="Camden"
).add_to(m)

# Display map
st_folium(m, width=700, height=500)

# ---------------------------
# Optional: Plot from CSV
# ---------------------------
st.subheader("📉 Data Visualization")

# Example: if you have columns like 'value'
if "value" in df.columns:
    st.line_chart(df["value"])
else:
    st.write("Add a 'value' column to visualize trends.")