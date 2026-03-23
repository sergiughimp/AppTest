import streamlit as st
import pandas as pd
import json

# Try to import folium safely
try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except ModuleNotFoundError:
    FOLIUM_AVAILABLE = False

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


# ---------------------------
# Load GeoJSON
# ---------------------------
@st.cache_data
def load_geojson():
    with open("data/geo/camden.json", "r", encoding="utf-8") as f:
        return json.load(f)


# Load files safely
try:
    df = load_data()
    st.subheader("📊 Measurements Data")
    st.write(df.head())

    st.subheader("📈 Summary Statistics")
    st.write(df.describe(include="all"))
except Exception as e:
    st.error(f"Could not load CSV file: {e}")
    df = pd.DataFrame()

try:
    geo_data = load_geojson()
except Exception as e:
    st.error(f"Could not load GeoJSON file: {e}")
    geo_data = None


# ---------------------------
# Map
# ---------------------------
st.subheader("🗺️ Camden Map")

if not FOLIUM_AVAILABLE:
    st.warning("Folium is not installed, so the map cannot be displayed.")
    st.info("Add 'folium' and 'streamlit-folium' to your requirements.txt file.")
elif geo_data is None:
    st.warning("GeoJSON file could not be loaded.")
else:
    m = folium.Map(location=[51.54, -0.14], zoom_start=12)

    folium.GeoJson(
        geo_data,
        name="Camden"
    ).add_to(m)

    st_folium(m, width=700, height=500)


# ---------------------------
# Data Visualization
# ---------------------------
st.subheader("📉 Data Visualization")

if not df.empty:
    numeric_columns = df.select_dtypes(include="number").columns.tolist()

    if numeric_columns:
        selected_column = st.selectbox("Choose a numeric column to plot", numeric_columns)
        st.line_chart(df[selected_column])
    else:
        st.write("No numeric columns found in measurements.csv.")
else:
    st.write("No data available to visualize.")