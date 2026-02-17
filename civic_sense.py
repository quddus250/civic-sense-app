import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim

# ---------------- CONFIG ----------------
st.set_page_config(page_title="CivicSense Smart", page_icon="🏛", layout="wide")
ADMIN_PASSWORD = "Civic@2026Secure"

# ---------------- DB (SQLite) ----------------
conn = sqlite3.connect("civic.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS CivicComplaints (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    CitizenName TEXT,
    PhoneNumber TEXT,
    IssueType TEXT,
    Description TEXT,
    ImageData BLOB,
    Latitude REAL,
    Longitude REAL,
    Status TEXT DEFAULT 'Pending',
    DateReported TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# ---------------- UI STYLE ----------------
st.markdown("""
<style>
.main { background-color: #eef2f7; }
h1 { color: #003366; text-align: center; }
.stButton>button {
  background-color: #003366; color: white; border-radius: 8px; height: 3em; width: 100%;
}
</style>
""", unsafe_allow_html=True)

st.title("🏛 CivicSense Smart – Digital Civic Complaint System")

# ---------------- SIDEBAR LOGIN ----------------
st.sidebar.title("🔐 Login Panel")
role = st.sidebar.selectbox("Login As", ["Citizen", "Admin"])

if role == "Admin":
    password = st.sidebar.text_input("Enter Admin Password", type="password")
    if password != ADMIN_PASSWORD:
        st.warning("Admin access required")
        st.stop()

# =====================================================
# ================= CITIZEN PANEL =====================
# =====================================================
if role == "Citizen":
    st.header("📢 Report a Civic Issue")

    name = st.text_input("Enter Your Name")
    phone = st.text_input("Enter Phone Number")

    issue_type = st.selectbox(
        "Select Issue Type",
        ["🛣 Road Damage", "💧 Water Leakage",
         "🚰 Sewage Issue", "🐕 Street Dogs", "🗑 Garbage Problem"]
    )

    description = st.text_area("Describe the Issue (Optional)")
    uploaded_file = st.file_uploader("Upload Issue Image (max 2MB)", type=["jpg", "png", "jpeg"])

    # -------- VALIDATION HELPERS --------
    def valid_phone(p):
        return p.isdigit() and len(p) == 10

    if uploaded_file and uploaded_file.size > 2 * 1024 * 1024:
        st.error("Image must be under 2MB")

    # -------- SEARCH AREA ----------
    st.subheader("🔍 Search Area → Then Click Exact Location")
    area_name = st.text_input("Enter Area / City Name (e.g., Benz Circle Vijayawada)")
    geolocator = Nominatim(user_agent="civic_app")

    search_lat, search_lon = 16.5062, 80.6480  # default center

    if area_name:
        try:
            loc = geolocator.geocode(area_name)
            if loc:
                search_lat, search_lon = loc.latitude, loc.longitude
                st.success(f"Showing results for: {area_name}")
            else:
                st.warning("Area not found, try a different name.")
        except:
            st.warning("Location search failed. Try again.")

    # -------- MAP CLICK ----------
    m = folium.Map(location=[search_lat, search_lon], zoom_start=14)
    m.add_child(folium.LatLngPopup())
    map_data = st_folium(m, height=420, width=900)

    latitude = None
    longitude = None
    if map_data and map_data.get("last_clicked"):
        latitude = map_data["last_clicked"]["lat"]
        longitude = map_data["last_clicked"]["lng"]
        st.success(f"Selected Location: {latitude:.5f}, {longitude:.5f}")

    # -------- SUBMIT ----------
    if st.button("🚀 Submit Complaint"):
        if not name.strip():
            st.error("Name is required")
        elif not valid_phone(phone):
            st.error("Enter a valid 10 digit phone number")
        elif not uploaded_file:
            st.error("Please upload an image")
        elif uploaded_file.size > 2 * 1024 * 1024:
            st.error("Image must be under 2MB")
        elif not (latitude and longitude):
            st.error("Please select a location on the map")
        else:
            image_bytes = uploaded_file.read()
            cursor.execute("""
                INSERT INTO CivicComplaints
                (CitizenName, PhoneNumber, IssueType, Description, ImageData, Latitude, Longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, phone, issue_type, description, image_bytes, latitude, longitude))
            conn.commit()
            st.success("Complaint Submitted Successfully ✅")

# =====================================================
# ================= ADMIN PANEL =======================
# =====================================================
if role == "Admin":
    st.header("📊 Admin Control Panel")

    admin_option = st.selectbox(
        "Choose Action",
        ["View Records", "Search Complaint", "Export Data"]
    )

    df = pd.read_sql_query("SELECT * FROM CivicComplaints ORDER BY DateReported DESC", conn)

    # ---------------- VIEW RECORDS ----------------
    if admin_option == "View Records":
        for _, row in df.iterrows():
            st.markdown("---")
            st.subheader(f"Complaint ID: {row['ID']}")

            col1, col2 = st.columns([1, 2])

            with col1:
                if row["ImageData"]:
                    st.image(row["ImageData"], width=260)

            with col2:
                st.write(f"**Name:** {row['CitizenName']}")
                st.write(f"**Phone:** {row['PhoneNumber']}")
                st.write(f"**Issue:** {row['IssueType']}")
                st.write(f"**Description:** {row['Description']}")
                st.write(f"**Status:** {row['Status']}")

                # Mini map for this complaint
                single_map_df = pd.DataFrame({'lat': [row['Latitude']], 'lon': [row['Longitude']]})
                st.map(single_map_df)

                c1, c2 = st.columns(2)
                with c1:
                    if row["Status"] != "Resolved":
                        if st.button(f"Resolve {row['ID']}"):
                            cursor.execute(
                                "UPDATE CivicComplaints SET Status='Resolved' WHERE ID=?",
                                (row['ID'],)
                            )
                            conn.commit()
                            st.rerun()
                with c2:
                    if st.button(f"Delete {row['ID']}"):
                        cursor.execute("DELETE FROM CivicComplaints WHERE ID=?", (row['ID'],))
                        conn.commit()
                        st.rerun()

    # ---------------- SEARCH ----------------
    if admin_option == "Search Complaint":
        st.subheader("🔎 Search Records")
        search_by = st.selectbox("Search By", ["ID", "Issue Type", "Status", "Phone"])
        keyword = st.text_input("Enter value")

        if keyword:
            if search_by == "ID":
                result = df[df["ID"].astype(str) == keyword]
            elif search_by == "Issue Type":
                result = df[df["IssueType"].str.contains(keyword, case=False, na=False)]
            elif search_by == "Phone":
                result = df[df["PhoneNumber"].str.contains(keyword, na=False)]
            else:
                result = df[df["Status"].str.contains(keyword, case=False, na=False)]
            st.dataframe(result)

    # ---------------- EXPORT + ANALYTICS + SMART MAP ----------------
    if admin_option == "Export Data":
        st.subheader("📤 Export Complaints Data")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV File", data=csv, file_name="CivicComplaints.csv", mime="text/csv")

        st.subheader("📊 Issue Distribution")
        issue_counts = df['IssueType'].value_counts().reset_index()
        issue_counts.columns = ['IssueType', 'Count']
        fig = px.bar(issue_counts, x='IssueType', y='Count', color='Count')
        st.plotly_chart(fig)

        st.subheader("🗺 Smart Complaint Map (Color + Cluster)")
        base_map = folium.Map(location=[16.5062, 80.6480], zoom_start=12)
        marker_cluster = MarkerCluster().add_to(base_map)

        def get_color(issue):
            if "Road" in issue: return "red"
            if "Water" in issue: return "blue"
            if "Sewage" in issue: return "purple"
            if "Dog" in issue: return "orange"
            if "Garbage" in issue: return "green"
            return "gray"

        for _, row in df.iterrows():
            folium.Marker(
                location=[row["Latitude"], row["Longitude"]],
                popup=f"""
                <b>Issue:</b> {row['IssueType']}<br>
                <b>Name:</b> {row['CitizenName']}<br>
                <b>Status:</b> {row['Status']}
                """,
                icon=folium.Icon(color=get_color(row["IssueType"]))
            ).add_to(marker_cluster)

        st_folium(base_map, width=950, height=520)

conn.close()
