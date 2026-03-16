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

# ─────────────────────────── PAGE CONFIG ───────────────────────────
st.set_page_config(
    page_title="London Borough Geospatial Mapping",
    page_icon="🗺️",
    layout="wide"
)

# ─────────────────────────── FILE PATHS ────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

DATA_FILES = {
    "Tower Hamlets": BASE_DIR / "tower_hamlets.json",
    "Camden": BASE_DIR / "camden.json",
    "Greenwich": BASE_DIR / "greenwich.json",
}

AIR_QUALITY_FILE = BASE_DIR / "camden_greenwich_tower_hamlets_air_quality_3_days.json"

# ─────────────────────────── HELPERS ───────────────────────────────
def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def get_geometry_type(geojson_data):
    if geojson_data.get("type") == "FeatureCollection":
        if geojson_data.get("features"):
            return geojson_data["features"][0].get("geometry", {}).get("type")
    elif geojson_data.get("type") == "Feature":
        return geojson_data.get("geometry", {}).get("type")
    return geojson_data.get("type")

def extract_all_coordinates(geojson_data):
    coords = []

    def walk_geometry(geometry):
        gtype = geometry.get("type")
        gcoords = geometry.get("coordinates", [])

        if gtype == "Polygon":
            for ring in gcoords:
                for lon, lat in ring:
                    coords.append((lat, lon))
        elif gtype == "MultiPolygon":
            for polygon in gcoords:
                for ring in polygon:
                    for lon, lat in ring:
                        coords.append((lat, lon))

    if geojson_data.get("type") == "FeatureCollection":
        for feature in geojson_data.get("features", []):
            walk_geometry(feature.get("geometry", {}))
    elif geojson_data.get("type") == "Feature":
        walk_geometry(geojson_data.get("geometry", {}))
    else:
        walk_geometry(geojson_data)

    return coords

def get_center_from_coords(coords):
    if not coords:
        return 51.509, -0.118
    avg_lat = sum(lat for lat, _ in coords) / len(coords)
    avg_lon = sum(lon for _, lon in coords) / len(coords)
    return avg_lat, avg_lon

def get_bounds(coords):
    if not coords:
        return None
    lats = [lat for lat, _ in coords]
    lons = [lon for _, lon in coords]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]

def make_feature_collection_if_needed(data, name):
    if data.get("type") == "FeatureCollection":
        return data
    if data.get("type") == "Feature":
        return {"type": "FeatureCollection", "features": [data]}
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": name},
                "geometry": data,
            }
        ],
    }

def clean_numeric_value(value):
    if value in ("", None):
        return pd.NA
    return pd.to_numeric(value, errors="coerce")

def extract_station_rows(air_quality_json):
    rows = []

    boroughs = air_quality_json.get("boroughs", {})
    for borough, sites in boroughs.items():
        for site in sites:
            pollutants = []
            request_statuses = []

            for pollutant in site.get("pollutants_measured", []):
                code = pollutant.get("species_code")
                name = pollutant.get("species_name")
                status = pollutant.get("request_status_code")

                if code:
                    pollutants.append(f"{code} - {name}")
                if status is not None:
                    request_statuses.append(str(status))

            rows.append({
                "borough": borough,
                "station_name": site.get("site_name"),
                "station_code": site.get("site_code"),
                "site_type": site.get("site_type"),
                "latitude": pd.to_numeric(site.get("latitude"), errors="coerce"),
                "longitude": pd.to_numeric(site.get("longitude"), errors="coerce"),
                "pollutants": ", ".join(sorted(set(pollutants))) if pollutants else "N/A",
                "num_pollutants": len(set(pollutants)),
                "request_statuses": ", ".join(sorted(set(request_statuses))) if request_statuses else "N/A",
            })

    return pd.DataFrame(rows)

def extract_measurement_rows(air_quality_json):
    rows = []

    boroughs = air_quality_json.get("boroughs", {})
    for borough, sites in boroughs.items():
        for site in sites:
            station_name = site.get("site_name")
            station_code = site.get("site_code")
            site_type = site.get("site_type")

            for pollutant in site.get("pollutants_measured", []):
                species_code = pollutant.get("species_code")
                species_name = pollutant.get("species_name")
                request_status_code = pollutant.get("request_status_code")
                measurements = pollutant.get("measurements", [])

                for m in measurements:
                    date_value = (
                        m.get("@MeasurementDateGMT")
                        or m.get("MeasurementDateGMT")
                        or m.get("@Date")
                        or m.get("Date")
                    )
                    value = m.get("@Value") or m.get("Value")

                    rows.append({
                        "borough": borough,
                        "station_name": station_name,
                        "station_code": station_code,
                        "site_type": site_type,
                        "pollutant_code": species_code,
                        "pollutant_name": species_name,
                        "request_status_code": request_status_code,
                        "measurement_date": pd.to_datetime(date_value, errors="coerce"),
                        "value": clean_numeric_value(value),
                    })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df

def build_borough_insights(measurements_df):
    if measurements_df.empty:
        return pd.DataFrame()

    valid = measurements_df.dropna(subset=["value"]).copy()
    if valid.empty:
        return pd.DataFrame()

    summary = (
        valid.groupby(["borough", "pollutant_code"], dropna=False)
        .agg(
            avg_value=("value", "mean"),
            max_value=("value", "max"),
            min_value=("value", "min"),
            records=("value", "count"),
        )
        .reset_index()
        .sort_values(["borough", "pollutant_code"])
    )
    return summary

# ─────────────────────────── LOAD BOROUGH GEOJSON ──────────────────
borough_geojson = {}
borough_coords = {}
missing_files = []

for borough, filepath in DATA_FILES.items():
    if filepath.exists():
        raw = load_json(filepath)
        prepared = make_feature_collection_if_needed(raw, borough)
        borough_geojson[borough] = prepared
        borough_coords[borough] = extract_all_coordinates(prepared)
    else:
        missing_files.append(str(filepath))

# ─────────────────────────── LOAD AIR QUALITY DATA ─────────────────
stations_df = pd.DataFrame()
measurements_df = pd.DataFrame()
borough_insights_df = pd.DataFrame()
date_start = None
date_end = None
status_summary = {}
api_status = {}

if AIR_QUALITY_FILE.exists():
    try:
        air_quality_json = load_json(AIR_QUALITY_FILE)

        metadata = air_quality_json.get("metadata", {})
        date_start = pd.to_datetime(metadata.get("start_date"), errors="coerce")
        date_end = pd.to_datetime(metadata.get("end_date"), errors="coerce")
        if pd.notna(date_end):
            date_end = date_end + pd.Timedelta(hours=23, minutes=59, seconds=59)

        api_status = metadata.get("api_status", {})
        status_summary = air_quality_json.get("status_summary", {})

        stations_df = extract_station_rows(air_quality_json)
        measurements_df = extract_measurement_rows(air_quality_json)
        borough_insights_df = build_borough_insights(measurements_df)

    except Exception as e:
        st.error(f"Could not load air quality data: {e}")
else:
    st.warning(f"Air quality JSON file not found: {AIR_QUALITY_FILE}")

# ─────────────────────────── TITLE ─────────────────────────────────
st.title("🗺️ Geospatial Mapping Tool")
st.write(
    "Explore Camden, Greenwich, and Tower Hamlets borough boundaries, air-quality "
    "measurement towers, pollutant readings, and London hotspot context."
)

if missing_files:
    st.error("These borough files were not found: " + ", ".join(missing_files))

if not borough_geojson:
    st.stop()

# ─────────────────────────── SIDEBAR ───────────────────────────────
st.sidebar.header("🗺️ Map Settings")

tile_style = st.sidebar.selectbox(
    "Map style",
    ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"]
)

selected_borough = st.sidebar.selectbox(
    "Highlight borough",
    list(borough_geojson.keys()),
    index=0
)

show_fill = st.sidebar.checkbox("Fill polygons", value=True)
show_center_marker = st.sidebar.checkbox("Show borough centre marker", value=True)
show_all_labels = st.sidebar.checkbox("Show borough labels", value=True)

st.sidebar.subheader("Air-quality stations")
show_stations = st.sidebar.checkbox("Show measurement towers on map", value=True)
only_selected_borough_stations = st.sidebar.checkbox("Only selected borough stations", value=False)

st.sidebar.subheader("Pollutant measurements")
selected_pollutant = st.sidebar.selectbox(
    "Pollutant to inspect",
    ["All", "NO2", "O3", "PM10", "PM25", "CO", "SO2"],
    index=0
)

hide_missing_values = st.sidebar.checkbox("Hide missing values", value=True)

zoom_start = st.sidebar.slider("Zoom level", 9, 15, 11)

# ─────────────────────────── MAP SETUP ─────────────────────────────
selected_coords = borough_coords[selected_borough]
center_lat, center_lon = get_center_from_coords(selected_coords)

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=zoom_start,
    tiles=tile_style
)

# ─────────────────────────── DRAW BOROUGHS ─────────────────────────
colour_map = {
    "Tower Hamlets": "#d62728",
    "Camden": "#1f77b4",
    "Greenwich": "#2ca02c",
}

for borough, geojson_data in borough_geojson.items():
    is_selected = borough == selected_borough
    base_colour = colour_map.get(borough, "#444444")

    folium.GeoJson(
        geojson_data,
        name=borough,
        style_function=lambda feature, is_selected=is_selected, base_colour=base_colour: {
            "fillColor": base_colour if show_fill and is_selected else (
                base_colour if show_fill else "transparent"
            ),
            "color": base_colour,
            "weight": 4 if is_selected else 2,
            "fillOpacity": 0.35 if show_fill and is_selected else (0.15 if show_fill else 0.0),
        },
        tooltip=borough if show_all_labels else None,
        popup=folium.Popup(f"<b>{borough}</b>", max_width=200),
    ).add_to(m)

    if show_center_marker:
        b_lat, b_lon = get_center_from_coords(borough_coords[borough])
        folium.Marker(
            location=[b_lat, b_lon],
            tooltip=borough,
            popup=f"{borough} centre",
            icon=folium.Icon(
                color="red" if is_selected else "blue",
                icon="info-sign",
                prefix="glyphicon",
            ),
        ).add_to(m)

# ─────────────────────────── DRAW STATIONS ─────────────────────────
if show_stations and not stations_df.empty:
    station_subset = stations_df.copy()

    if only_selected_borough_stations:
        station_subset = station_subset[station_subset["borough"] == selected_borough]

    station_subset = station_subset.dropna(subset=["latitude", "longitude"])

    for _, row in station_subset.iterrows():
        popup_html = f"""
        <div style="font-family: Arial; width: 280px;">
            <h4 style="margin-bottom: 8px;">{row['station_name']}</h4>
            <table style="font-size: 12px; width: 100%;">
                <tr><td><b>Code</b></td><td>{row['station_code']}</td></tr>
                <tr><td><b>Borough</b></td><td>{row['borough']}</td></tr>
                <tr><td><b>Type</b></td><td>{row['site_type']}</td></tr>
                <tr><td><b>Latitude</b></td><td>{row['latitude']:.6f}</td></tr>
                <tr><td><b>Longitude</b></td><td>{row['longitude']:.6f}</td></tr>
                <tr><td><b>Measures</b></td><td>{row['pollutants']}</td></tr>
                <tr><td><b>Status</b></td><td>{row['request_statuses']}</td></tr>
            </table>
        </div>
        """

        marker_colour = "red" if row["borough"] == selected_borough else "blue"

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6,
            color=marker_colour,
            fill=True,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row['station_name']} ({row['station_code']})",
        ).add_to(m)

# Fit map to selected borough
bounds = get_bounds(selected_coords)
if bounds:
    m.fit_bounds(bounds)

folium.LayerControl().add_to(m)

# ─────────────────────────── RENDER MAP ────────────────────────────
st.subheader(f"Map: {selected_borough}")
st_folium(m, width=None, height=650, use_container_width=True)

# ─────────────────────────── API STATUS ────────────────────────────
st.divider()
st.subheader("🔎 API Request Status")

if api_status:
    c1, c2 = st.columns(2)
    c1.metric("Sites endpoint status", api_status.get("sites_endpoint_status", "N/A"))
    c2.metric("Species endpoint status", api_status.get("species_endpoint_status", "N/A"))

if status_summary:
    status_rows = []
    for borough, summary in status_summary.items():
        status_rows.append({
            "Borough": borough,
            "Total Requests": summary.get("total_requests"),
            "Successful (200)": summary.get("successful_requests"),
            "Failed / Other": summary.get("failed_requests"),
            "Status Codes": str(summary.get("status_codes")),
        })
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True)

# ─────────────────────────── SUMMARY BELOW MAP ─────────────────────
st.divider()
st.subheader("📍 Measurement Towers Summary")

if stations_df.empty:
    st.info("No station data available.")
else:
    total_stations = len(stations_df)

    borough_counts = (
        stations_df.groupby("borough")["station_code"]
        .count()
        .reset_index(name="number_of_stations")
        .sort_values("borough")
    )

    col1, col2 = st.columns(2)
    col1.metric("Total measurement towers", total_stations)
    col2.metric(
        f"{selected_borough} towers",
        len(stations_df[stations_df["borough"] == selected_borough])
    )

    st.write("**Stations by borough**")
    st.dataframe(borough_counts, use_container_width=True)

    detail_df = stations_df.copy().rename(columns={
        "borough": "Borough",
        "station_name": "Station Name",
        "station_code": "Code",
        "site_type": "Site Type",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "pollutants": "What They Measure",
        "num_pollutants": "No. of Pollutants",
        "request_statuses": "Request Status Codes",
    })

    detail_df = detail_df[
        [
            "Borough",
            "Station Name",
            "Code",
            "Site Type",
            "Latitude",
            "Longitude",
            "No. of Pollutants",
            "What They Measure",
            "Request Status Codes",
        ]
    ].sort_values(["Borough", "Station Name"])

    st.write("**All measurement towers**")
    st.dataframe(detail_df, use_container_width=True)

# ─────────────────────────── POLLUTANT DATA ────────────────────────
st.divider()
st.subheader("🧪 Pollutant Measurements")

if date_start is not None and date_end is not None:
    st.write(
        f"Selected data range: **{date_start.strftime('%d %b %Y')} to {date_end.strftime('%d %b %Y')}**"
    )

if measurements_df.empty:
    st.info("No measurement data available.")
else:
    filtered_measurements = measurements_df.copy()

    if date_start is not None and date_end is not None:
        filtered_measurements = filtered_measurements[
            (filtered_measurements["measurement_date"] >= date_start) &
            (filtered_measurements["measurement_date"] <= date_end)
        ]

    if selected_pollutant != "All":
        filtered_measurements = filtered_measurements[
            filtered_measurements["pollutant_code"] == selected_pollutant
        ]

    if only_selected_borough_stations:
        filtered_measurements = filtered_measurements[
            filtered_measurements["borough"] == selected_borough
        ]

    if hide_missing_values:
        filtered_measurements = filtered_measurements.dropna(subset=["value"])

    filtered_measurements = filtered_measurements.sort_values(
        ["pollutant_code", "borough", "station_name", "measurement_date"]
    )

    if filtered_measurements.empty:
        st.warning("No measurements found for the selected filters.")
    else:
        pollutant_summary = (
            filtered_measurements.groupby(
                ["borough", "pollutant_code", "pollutant_name"], dropna=False
            )
            .agg(
                measurements_count=("value", "count"),
                average_value=("value", "mean"),
                min_value=("value", "min"),
                max_value=("value", "max"),
            )
            .reset_index()
            .sort_values(["borough", "pollutant_code"])
        )

        st.write("**Pollutant summary by borough**")
        st.dataframe(pollutant_summary, use_container_width=True)

        display_df = filtered_measurements.rename(columns={
            "borough": "Borough",
            "station_name": "Station Name",
            "station_code": "Code",
            "site_type": "Site Type",
            "pollutant_code": "Pollutant Code",
            "pollutant_name": "Pollutant Name",
            "request_status_code": "Request Status Code",
            "measurement_date": "Measurement Date",
            "value": "Value",
        })

        display_df = display_df[
            [
                "Borough",
                "Station Name",
                "Code",
                "Site Type",
                "Pollutant Code",
                "Pollutant Name",
                "Request Status Code",
                "Measurement Date",
                "Value",
            ]
        ]

        st.write("**Measurement data**")
        st.dataframe(display_df, use_container_width=True)

# ─────────────────────────── BOROUGH INSIGHTS ──────────────────────
st.divider()
st.subheader("📊 Borough Insights for Presentation")

if borough_insights_df.empty:
    st.info("No borough insight data available.")
else:
    st.write(
        "These summaries help explain how air quality differs across Camden, Greenwich, "
        "and Tower Hamlets over the selected analysis period."
    )
    st.dataframe(borough_insights_df, use_container_width=True)

# ─────────────────────────── PRESENTATION CONTEXT ──────────────────
st.divider()
st.subheader("🧭 London Hotspots and Project Relevance")

st.markdown(
    """
### Air Pollution Hotspots in London

Air pollution in London is strongly influenced by **traffic density, urban congestion, and major road corridors**.  
The highest pollution levels are often recorded near **busy transport routes in central London**.

#### Key hotspots
- **Marylebone Road**  
  One of the most polluted roads in the UK, especially for **NO₂**, due to heavy traffic and diesel vehicles.

- **Euston Road**  
  A major transport corridor directly relevant to **Camden**. It is associated with high **NO₂**, **PM10**, and **PM2.5** levels.

- **Oxford Street**  
  A high-density commercial corridor with intense bus and taxi activity, historically linked with high nitrogen dioxide concentrations.

- **Tower Hamlets major roads**  
  Routes such as **Mile End Road** and nearby traffic corridors experience elevated pollution from commuter traffic, freight movement, and urban congestion.

- **Central London traffic corridors**  
  Links between **Camden, Westminster, City of London, and Tower Hamlets** create continuous high-pressure transport zones where **NO₂**, **PM2.5**, and **PM10** are especially important.

### Relevance to this project

The boroughs analysed in this project contain important monitoring stations near these pollution corridors.

#### Camden
- Euston Road monitoring station
- Bloomsbury monitoring station
- Swiss Cottage monitoring station

#### Tower Hamlets
- Mile End Road monitoring station
- Bethnal Green monitoring station
- Blackwall monitoring station

#### Greenwich
- Trafalgar Road monitoring station
- Woolwich Flyover monitoring station
- Tunnel Avenue monitoring station

These monitoring points are useful because they capture the effect of:
- commuter traffic
- commercial vehicle activity
- urban congestion
- roadside exposure
"""
)

# ─────────────────────────── SHORT SLIDE VERSION ───────────────────
st.divider()
st.subheader("🎤 Short Slide Text for Presentation")

st.markdown(
    """
**London Pollution Hotspots**
- Marylebone Road – one of the most polluted roads in the UK
- Euston Road – major traffic corridor in Camden
- Oxford Street – high NO₂ levels due to buses and taxis
- Mile End Road (Tower Hamlets) – heavy commuter traffic
- Central London corridors – high concentrations of NO₂, PM2.5 and PM10

**Why these boroughs matter**
- **Camden** captures central-road pollution through stations such as Euston Road and Bloomsbury
- **Tower Hamlets** captures east-London roadside and commuter pollution through Mile End Road and Blackwall
- **Greenwich** captures major corridor and flyover exposure through Trafalgar Road, Tunnel Avenue, and Woolwich Flyover
"""
)

# ─────────────────────────── BOROUGH DETAIL ────────────────────────
st.divider()
st.subheader("📌 Borough Detail")

geom_type = get_geometry_type(borough_geojson[selected_borough])
num_points = len(borough_coords[selected_borough])
selected_station_count = 0 if stations_df.empty else len(
    stations_df[stations_df["borough"] == selected_borough]
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Selected Borough", selected_borough)
c2.metric("Geometry Type", geom_type if geom_type else "Unknown")
c3.metric("Boundary Points", f"{num_points:,}")
c4.metric("Measurement Towers", selected_station_count)

st.caption(f"GeoJSON folder: {BASE_DIR}")
st.caption(f"Air quality file: {AIR_QUALITY_FILE}")