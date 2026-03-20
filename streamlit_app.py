"""
🗺️ GEOSPATIAL MAPPING TOOL
==============================
This app:
- draws borough boundaries from GeoJSON files
- loads air-quality stations from the saved 3-day JSON dataset
- shows / hides station markers on the map
- shows a detailed station table below the map
- shows pollutant measurements for the selected date range
- shows borough insights and London hotspot context for presentation

Required packages:
    pip install streamlit folium streamlit-folium pandas

Run with:
    streamlit run geospatial_mapping.py
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
print("Hello World")