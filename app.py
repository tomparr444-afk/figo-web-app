import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from math import radians, cos, sin, asin, sqrt
import pandas as pd
from supabase import create_client, Client
import time
from datetime import datetime, date, timedelta
import requests

# --- CONFIGURATION ---
APP_NAME = "Figo"
LOGO_FILENAME = "Figo Logo.png"
ADMIN_PASSWORD = "admin123"

# ⚠️ YOUR LIVE KEYS
SUPABASE_URL = "https://sryvcuplpagtcnrnwsjz.supabase.co"
SUPABASE_KEY = "sb_publishable_sz-4L9e9jjvksF_YpJGAlw_ThCUzA7N"
GOOGLE_MAPS_API_KEY = "AIzaSyCZAKScxLoEkydVfa-a5XAqFIoAl-UNuP4"

# --- PAGE SETUP ---
st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📍")

# --- 🎨 STARLINK STYLE CSS ---
st.markdown("""
<style>
    /* Main Background - Deep Space Black */
    .stApp {
        background-color: #050505;
        color: #ffffff;
    }
    
    /* Sidebar - Slightly Lighter */
    [data-testid="stSidebar"] {
        background-color: #0b0c0e;
        border-right: 1px solid #222;
    }
    
    /* Text Inputs */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
        background-color: #16181c;
        color: white;
        border: 1px solid #333;
        border-radius: 4px;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #00ADB5; /* Cyan Glow */
    }
    
    /* Buttons - High Contrast White */
    .stButton button {
        background-color: #ffffff;
        color: #000000;
        font-weight: bold;
        border-radius: 4px;
        border: none;
        transition: all 0.2s;
    }
    .stButton button:hover {
        background-color: #cccccc;
        color: black;
        transform: scale(1.02);
    }
    
    /* Expander Cards */
    .streamlit-expanderHeader {
        background-color: #16181c;
        border-radius: 4px;
        color: white;
    }
    
    /* Calendar Card Style */
    .schedule-card {
        background-color: #1e1e1e;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
        border-left: 4px solid #00ADB5;
    }
    .schedule-card.install {
        border-left: 4px solid #9b59b6; /* Purple for installs */
    }
    .schedule-card.note {
        border-left: 4px solid #f1c40f; /* Yellow for notes */
        background-color: #2c2c20;
    }
    
    /* Fonts */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        letter-spacing: -0.5px;
    }
    
    /* Hide Default Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# --- DB CONNECTION ---
@st.cache_resource
def init_connection():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except: return None
supabase = init_connection()

# --- AUTH ---
def check_login(username, password):
    if not supabase: return False
    if username.lower() == "admin" and password == ADMIN_PASSWORD: return "ADMIN"
    try:
        res = supabase.table("clients").select("*").eq("company_id", username).eq("password", password).execute()
        return username if res.data else None
    except: return None

# --- HELPER FUNCTIONS ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    return c * 3956

def decode_polyline(polyline_str):
    '''Decodes a Google Maps encoded polyline string.'''
    index, lat, lng = 0, 0, 0
    coordinates = []
    length = len(polyline_str)
    while index < length:
        b, shift, result = 0, 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20: break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        
        shift, result = 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20: break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        
        coordinates.append((lat / 100000.0, lng / 100000.0))
    return coordinates

def get_google_route(start_lat, start_lon, end_lat, end_lon):
    """Fetches driving route points, distance, and duration from Google Directions API"""
    if not GOOGLE_MAPS_API_KEY: return None
    # Added &units=imperial to force miles
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={start_lat},{start_lon}&destination={end_lat},{end_lon}&mode=driving&units=imperial&key={GOOGLE_MAPS_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if data['status'] == 'OK':
            route = data['routes'][0]
            points = route['overview_polyline']['points']
            leg = route['legs'][0]
            dist_text = leg['distance']['text']
            dur_text = leg['duration']['text']
            return decode_polyline(points), dist_text, dur_text
        else:
            print(f"Google Maps API Error: {data['status']} - {data.get('error_message', 'No message')}")
            return None
    except Exception as e:
        print(f"Google Maps Request Failed: {e}")
        return None

def optimize_route(start_coords, stops):
    """
    Simple Nearest Neighbor Algorithm
    start_coords: (lat, lon)
    stops: list of dicts {'addr': str, 'lat': float, 'lon': float}
    """
    route = []
    current_loc = start_coords
    unvisited = stops.copy()
    
    while unvisited:
        nearest = None
        min_dist = float('inf')
        
        for stop in unvisited:
            dist = haversine(current_loc[1], current_loc[0], stop['lon'], stop['lat'])
            if dist < min_dist:
                min_dist = dist
                nearest = stop
        
        if nearest:
            route.append(nearest)
            current_loc = (nearest['lat'], nearest['lon'])
            unvisited.remove(nearest)
            
    return route

def get_engineer_color(name, status, custom_color=None):
    # Only gray out for Sick or Holiday. Other statuses show color.
    if status in ["Sick", "Holiday"]: return "gray"
    
    # Valid Folium colors
    valid_colors = {'red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray'}
    
    # Check if custom_color is valid (handles potential emoji suffix if passed raw)
    # Ensure lower case for matching
    clean_color = custom_color.split()[0].lower() if custom_color else None
    
    if clean_color and clean_color in valid_colors: 
        return clean_color
        
    # Simplify default to just blue
    return "blue"

def get_job_color(severity):
    # Safe handling of None
    if not severity: severity = 'Low'
    severity = str(severity).lower()
    
    if "critical" in severity or "high" in severity: return "red"
    if "medium" in severity: return "orange" 
    if "low" in severity: return "green"
    return "blue" 

def get_start_of_week(dt):
    start = dt - timedelta(days=dt.weekday())
    return start

def find_nearest_engineer_text(lat, lon, engineers_list):
    """Helper to find nearest engineer and return display text"""
    # Consider active working statuses for nearest calculation
    working_statuses = ["Active", "Driving", "On Site", "In Office", "Home"]
    active_engs = [e for e in engineers_list if e['status'] in working_statuses]
    
    if not active_engs: return "No active engineers found."
    
    for e in active_engs:
        e['temp_dist'] = haversine(lon, lat, e['lon'], e['lat'])
    
    active_engs.sort(key=lambda x: x['temp_dist'])
    nearest = active_engs[0]
    return f"Nearest Engineer: {nearest['name']} ({nearest['temp_dist']:.1f} miles away)"

# --- DATABASE FETCHERS ---
def get_engineers(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Engineers").select("*").eq("Company_ID", company_id).order('id').execute()
        return [{
            'id': r['id'],
            'name': r.get('Name') or r.get('name'), 
            'lat': r['Latitude'], 
            'lon': r['Longitude'],
            'status': r.get('status', 'Active'),
            'pin_color': r.get('pin_color') or 'blue' # Default to blue if None
        } for r in res.data]
    except: return []

def get_jobs(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Jobs").select("*").eq("Company_ID", company_id).execute()
        cleaned_jobs = []
        for r in res.data:
            lat = r.get('Latitude')
            lon = r.get('Longitude')
            ref = r.get('Job_Ref')
            desc = r.get('Description', '')
            director = r.get('Director_Name', '')
            severity = r.get('severity') or 'Low' # Force default if None
            
            if lat and lon:
                cleaned_jobs.append({
                    'id': r['id'], 
                    'ref': ref, 
                    'lat': lat, 
                    'lon': lon,
                    'desc': desc,
                    'director': director,
                    'severity': severity
                })
        return cleaned_jobs
    except: return []

def get_installs(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Installs").select("*").eq("Company_ID", company_id).execute()
        cleaned_installs = []
        for r in res.data:
            lat = r.get('Latitude')
            lon = r.get('Longitude')
            if lat and lon: 
                # Try 'Install_Ref' first, fall back to 'Job_Ref' to be safe
                ref_val = r.get('Install_Ref') or r.get('Job_Ref')
                
                cleaned_installs.append({
                    'id': r['id'],
                    'ref': ref_val,  
                    'status': r.get('status') or 'Not passed Finance', # Force default if None
                    'postcode': r.get('Postcode'),
                    'lat': lat,
                    'lon': lon,
                    'desc': r.get('Description', ''),
                    'director': r.get('Director_Name', '')
                })
        return cleaned_installs
    except: return []

# --- SCHEDULE FUNCTIONS ---
def get_schedule(company_id, start_date=None, end_date=None):
    if not supabase: return []
    try:
        query = supabase.table("job_schedule").select("*").eq("company_id", company_id)
        
        # Filter range if provided
        if start_date:
            query = query.gte("scheduled_date", str(start_date))
        if end_date:
            query = query.lte("scheduled_date", str(end_date))
            
        res = query.order("scheduled_date", desc=False).execute()
        return res.data
    except: return []

def add_schedule_item(company_id, engineer, job, date_obj, notes, job_type="Maintenance"):
    if not supabase: return False
    try:
        # Assuming you add a 'type' column to 'job_schedule' in Supabase. 
        # If not, remove the 'type': job_type line below.
        payload = {
            "company_id": company_id,
            "engineer_name": engineer,
            "job_ref": job,
            "scheduled_date": str(date_obj),
            "notes": notes,
            # "type": job_type  # Uncomment this after adding column to Supabase
        }
        
        # Note: If saving to a column that doesn't exist, Supabase API might error or ignore it.
        # For now, we will just save it as notes prefix if type col missing
        if job_type == "Install":
             payload["notes"] = f"[INSTALL] {notes}"
        elif job_type == "Note":
             payload["notes"] = f"[NOTE] {notes}"
        
        supabase.table("job_schedule").insert(payload).execute()
        return True
    except Exception as e:
        print(f"Schedule Error: {e}")
        return False

# --- DATABASE WRITERS ---
def update_engineer_status_color(engineer_id, new_status, new_color):
    try:
        payload = {"status": new_status}
        if new_color: payload["pin_color"] = new_color
        supabase.table("Engineers").update(payload).eq("id", engineer_id).execute()
        return True
    except: return False

def update_install_status(install_id, new_status):
    try:
        supabase.table("Installs").update({"status": new_status}).eq("id", install_id).execute()
        return True
    except: return False

def delete_record(table, record_id, record_ref=None, ref_col=None):
    """
    Deletes a record from the main table AND removes associated schedule entries from diary.
    """
    try:
        # 1. If we have the reference string, delete from Schedule first
        if record_ref and ref_col:
            # Note: job_schedule stores the reference in 'job_ref' column regardless of type
            supabase.table("job_schedule").delete().eq("job_ref", record_ref).execute()
            
        # 2. Delete from the Main Table (Jobs or Installs)
        supabase.table(table).delete().eq("id", record_id).execute()
        return True
    except Exception as e:
        print(f"Delete Error: {e}")
        return False

def add_entry(table, name_col, name_val, postcode, company_id, desc=None, director=None, severity=None, pin_color=None, install_status=None):
    geolocator = Nominatim(user_agent="figo_adder_v18")
    try:
        loc = geolocator.geocode(postcode)
        if loc:
            payload = {
                name_col: name_val,
                "Company_ID": company_id,
                "Latitude": loc.latitude,
                "Longitude": loc.longitude
            }
            if table == "Engineers": 
                payload["status"] = "Active"
                if pin_color: payload["pin_color"] = pin_color
            elif table == "Jobs":
                if desc: payload["Description"] = desc 
                if director: payload["Director_Name"] = director
                if severity: payload["severity"] = severity
            elif table == "Installs":
                payload["Postcode"] = postcode 
                if install_status: payload["status"] = install_status
                if desc: payload["Description"] = desc
                if director: payload["Director_Name"] = director

            supabase.table(table).insert(payload).execute()
            # Return coordinates for nearest engineer calculation
            return True, f"Added {name_val}", (loc.latitude, loc.longitude)
        return False, "Postcode not found", None
    except Exception as e: 
        print(f"Add Entry Error: {e}")
        return False, "Error", None

def process_bulk_upload(df, type_flag, company_id):
    geolocator = Nominatim(user_agent=f"figo_bulk_v18")
    progress_bar = st.progress(0)
    success_count = 0
    total = len(df)
    df.columns = [c.lower() for c in df.columns]
    for index, row in df.iterrows():
        try:
            if type_flag == "user":
                name_val = row['name']
                table_target = "Engineers"
                col_target = "Name"
            else:
                name_val = row['ref']
                table_target = "Jobs"
                col_target = "Job_Ref"
            pcode = row['postcode']
            location = geolocator.geocode(pcode)
            if location:
                payload = {
                    col_target: name_val,
                    "Company_ID": company_id,
                    "Latitude": location.latitude,
                    "Longitude": location.longitude
                }
                if type_flag == "user": payload["status"] = "Active"
                supabase.table(table_target).insert(payload).execute()
                success_count += 1
                time.sleep(1)
        except: pass
        progress_bar.progress((index + 1) / total)
    return success_count

def get_all_companies():
    if not supabase: return []
    try:
        res = supabase.table("Engineers").select("Company_ID").execute()
        return sorted(list(set([r['Company_ID'] for r in res.data if r['Company_ID']])))
    except: return []

# --- STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'company_id' not in st.session_state: st.session_state.company_id = None
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
if 'search_result' not in st.session_state: st.session_state.search_result = None
if 'search_active' not in st.session_state: st.session_state.search_active = False
if 'route_stops' not in st.session_state: st.session_state.route_stops = []
# New state to cache route calculations so map doesn't refresh constantly
if 'cached_routes' not in st.session_state: st.session_state.cached_routes = []

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    login_holder = st.empty() # Create a placeholder to clear later
    with login_holder.container():
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown(f"<h1 style='text-align: center; color: white;'>🔐 {APP_NAME} Login</h1>", unsafe_allow_html=True)
            with st.form("login"):
                user = st.text_input("Username", key="login_username_input")
                pw = st.text_input("Password", type="password", key="login_password_input")
                
                if st.form_submit_button("Connect"): 
                    res = check_login(user, pw)
                    if res:
                        st.session_state.logged_in = True
                        st.session_state.is_admin = (res == "ADMIN")
                        st.session_state.company_id = "demo" if res == "ADMIN" else res
                        login_holder.empty() # Clear form instantly
                        st.rerun()
                    else: st.error("Access Denied")
    st.stop()

# --- LOAD DATA ---
engineers = get_engineers(st.session_state.company_id)
jobs = get_jobs(st.session_state.company_id)
installs = get_installs(st.session_state.company_id)

# --- SIDEBAR ---
with st.sidebar:
    try: st.image(LOGO_FILENAME, width=200)
    except: st.header(APP_NAME)
    st.caption(f"CONNECTED: {st.session_state.company_id.upper()}")
    if st.button("LOGOUT"): 
        st.session_state.logged_in = False
        st.rerun()
    st.markdown("---")
    if st.session_state.is_admin:
        st.warning("ADMIN OVERRIDE")
        comps = get_all_companies()
        if comps: st.session_state.company_id = st.selectbox("TARGET:", comps)

    with st.expander("🚦 Single Eng. Manager"):
        if engineers:
            eng_map = {e['name']: e['id'] for e in engineers}
            s_name = st.selectbox("Select Engineer", list(eng_map.keys()))
            curr = next((e for e in engineers if e['name'] == s_name), None)
            
            # Status Logic
            stat = curr['status'] if curr else "Active"
            status_options = ["Active", "Home", "Driving", "On Site", "In Office", "Sick", "Holiday"]
            try:
                stat_index = status_options.index(stat)
            except ValueError:
                stat_index = 0 
                
            new_stat = st.radio("Status:", status_options, index=stat_index)
            
            # Pin Color
            color_opts = ["blue", "green", "red", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen", "cadetblue", "darkpurple", "white", "pink", "lightblue", "lightgreen", "gray", "black", "lightgray"]
            curr_color = curr.get('pin_color')
            # Handle mixed case or spaces in DB if manually edited
            if curr_color: curr_color = curr_color.split()[0].lower()
            
            if not curr_color or curr_color not in color_opts: curr_color = "blue"
            new_color = st.selectbox("Pin Color:", color_opts, index=color_opts.index(curr_color))
            if st.button("Update Single Engineer"):
                update_engineer_status_color(eng_map[s_name], new_stat, new_color)
                st.rerun()

    with st.expander("➕ Add Data / Bulk Upload", expanded=False):
        tab_single, tab_bulk = st.tabs(["Single", "Excel"])
        with tab_single:
            st.caption("New User")
            u_n = st.text_input("Name", key="u1")
            u_p = st.text_input("Postcode", key="u2")
            u_color = st.selectbox("Pin Color", ["blue", "green", "red", "purple", "orange", "darkred", "cadetblue"], key="u3")
            if st.button("Add User"):
                ok, m, coords = add_entry("Engineers", "Name", u_n, u_p, st.session_state.company_id, pin_color=u_color)
                if ok: st.success(m); time.sleep(1); st.rerun()
            st.divider()
            st.caption("New Job")
            j_r = st.text_input("Ref", key="j1")
            j_p = st.text_input("Postcode", key="j2")
            j_desc = st.text_input("Description (Optional)", key="j3")
            j_dir = st.text_input("Director Name (Optional)", key="j4")
            j_sev = st.select_slider("Severity", options=["Low", "Medium", "Critical"], value="Low")
            if st.button("Add Job"):
                ok, m, coords = add_entry("Jobs", "Job_Ref", j_r, j_p, st.session_state.company_id, desc=j_desc, director=j_dir, severity=j_sev)
                if ok: 
                    st.success(m)
                    # Show nearest engineer immediately
                    if coords:
                        near_msg = find_nearest_engineer_text(coords[0], coords[1], engineers)
                        st.info(near_msg)
                    time.sleep(3)
                    st.rerun()

        with tab_bulk:
            st.caption("Upload .xlsx")
            u_file = st.file_uploader("File", type=['xlsx'])
            u_type = st.radio("Content", ["Users", "Jobs"])
            if u_file and st.button("Upload"):
                try:
                    df = pd.read_excel(u_file)
                    cols = [c.lower() for c in df.columns]
                    has_name = 'name' in cols if u_type == "Users" else 'ref' in cols
                    if has_name and 'postcode' in cols:
                        t_flag = "user" if u_type == "Users" else "job"
                        cnt = process_bulk_upload(df, t_flag, st.session_state.company_id)
                        st.success(f"Uploaded {cnt}")
                        time.sleep(1); st.rerun()
                    else: st.error("Cols: 'Name' (or Ref) & 'Postcode'")
                except: st.error("File Error")

# --- MAIN UI ---
tab_map, tab_list, tab_jobs, tab_installs, tab_schedule = st.tabs(["🌍 DISPATCH MAP", "📋 FLEET LIST", "🔧 MAINTENANCE", "🛠️ INSTALLS", "📅 SCHEDULE"])

# --- TAB 1: MAP ---
with tab_map:
    # 1. Search Single
    with st.expander("🔍 Single Visit", expanded=True):
        with st.form("search"):
            col1, col2 = st.columns([3,1], vertical_alignment="bottom")
            with col1: p_code = st.text_input("Postcode")
            with col2: search = st.form_submit_button("Scan", type="primary")
        
        # When Scan is clicked, update state and calculate routes ONCE
        if search and p_code:
            geo = Nominatim(user_agent="figo_search_v18", timeout=10)
            try:
                l = geo.geocode(p_code)
                if l:
                    st.session_state.search_result = {'lat': l.latitude, 'lon': l.longitude, 'addr': l.address}
                    st.session_state.search_active = True
                    
                    # --- CALCULATE ROUTES & CACHE THEM ---
                    st.session_state.cached_routes = [] # Clear old routes
                    working_statuses = ["Active", "Driving", "On Site", "In Office", "Home"]
                    active_engineers = [e for e in engineers if e['status'] in working_statuses]
                    
                    # 1. Calculate haversine distance for sorting
                    for e in active_engineers:
                        e['temp_dist'] = haversine(l.longitude, l.latitude, e['lon'], e['lat'])
                    active_engineers.sort(key=lambda x: x['temp_dist'])
                    top3 = active_engineers[:3]
                    
                    # 2. Get Real Google Routes for Top 3
                    for eng in top3:
                        route_data = get_google_route(eng['lat'], eng['lon'], l.latitude, l.longitude)
                        if route_data:
                            pts, d_text, dur_text = route_data
                            st.session_state.cached_routes.append({
                                'name': eng['name'],
                                'points': pts,
                                'dist_text': d_text,
                                'dur_text': dur_text,
                                'color': "blue"
                            })
                        else:
                            # Fallback if API fails: store basic info but NO straight line points
                            st.session_state.cached_routes.append({
                                'name': eng['name'],
                                'points': None, # Don't draw line
                                'dist_text': f"{eng['temp_dist']:.1f} miles (Direct)",
                                'dur_text': "N/A",
                                'color': "orange"
                            })
                    
                else: st.error("Not Found")
            except: st.error("Search Failed")

    # 2. Route Planner
    with st.expander("🚚 Multiple Visits", expanded=False):
        c1, c2 = st.columns([3, 1])
        new_stop = c1.text_input("Add Stop (Postcode)", key="route_input")
        if c2.button("Add Stop") and new_stop:
            geo_r = Nominatim(user_agent="figo_route_v1")
            l_r = geo_r.geocode(new_stop)
            if l_r:
                st.session_state.route_stops.append({'addr': new_stop, 'lat': l_r.latitude, 'lon': l_r.longitude})
                st.rerun()
            else: st.error("Invalid Postcode")
        
        if st.session_state.route_stops:
            st.write(f"Stops added: {len(st.session_state.route_stops)}")
            st.dataframe(pd.DataFrame(st.session_state.route_stops)[['addr']], hide_index=True, use_container_width=True)
            # Start Point Selection
            start_opts = ["Custom..."] + [e['name'] for e in engineers]
            start_sel = st.selectbox("Start From:", start_opts)
            
            start_coords = None
            if start_sel == "Custom...":
                start_txt = st.text_input("Custom Start Postcode")
                if start_txt:
                    geo_s = Nominatim(user_agent="figo_start")
                    ls = geo_s.geocode(start_txt)
                    if ls: start_coords = (ls.latitude, ls.longitude)
            else:
                eng = next((e for e in engineers if e['name'] == start_sel), None)
                if eng: start_coords = (eng['lat'], eng['lon'])

            if st.button("Optimize Route") and start_coords:
                optimized = optimize_route(start_coords, st.session_state.route_stops)
                st.session_state.optimized_route = {'start': start_coords, 'path': optimized}
            
            if st.button("Clear Route"):
                st.session_state.route_stops = []
                if 'optimized_route' in st.session_state: del st.session_state.optimized_route
                st.rerun()

    m = folium.Map(location=[54.5, -4.0], zoom_start=6, tiles="CartoDB dark_matter")

    # ENGINEERS LAYER
    for eng in engineers:
        color = get_engineer_color(eng['name'], eng['status'], eng.get('pin_color'))
        folium.Marker(
            [eng['lat'], eng['lon']],
            tooltip=f"{eng['name']} ({eng['status']})", 
            popup=f"USER: {eng['name']}\nSTATUS: {eng['status']}",
            icon=folium.Icon(color=color, icon="user")
        ).add_to(m)

    # JOBS LAYER
    for job in jobs:
        popup_content = f"JOB: {job.get('ref')}\n"
        if job.get('desc'): popup_content += f"DESC: {job.get('desc')}\n"
        if job.get('director'): popup_content += f"DIR: {job.get('director')}\n"
        popup_content += f"SEVERITY: {job.get('severity')}\n"
        
        job_color = get_job_color(job.get('severity', 'Low'))
        folium.Marker(
            [job['lat'], job['lon']],
            tooltip=f"JOB: {job.get('ref')}",
            popup=popup_content,
            icon=folium.Icon(color=job_color, icon="briefcase", prefix='fa')
        ).add_to(m)

    # INSTALLS LAYER
    for inst in installs:
        popup_content = f"INSTALL: {inst.get('ref')}\nSTATUS: {inst.get('status')}\n"
        folium.Marker(
            [inst['lat'], inst['lon']],
            tooltip=f"INSTALL: {inst.get('ref')}",
            popup=popup_content,
            icon=folium.Icon(color='purple', icon="wrench", prefix='fa') 
        ).add_to(m)

    # ROUTE LAYER (UPDATED: Use Google Roads)
    if 'optimized_route' in st.session_state:
        rt = st.session_state.optimized_route
        current_pos = rt['start']
        
        # Add Start Marker
        folium.Marker(rt['start'], popup="Start", icon=folium.Icon(color="green", icon="play", prefix='fa')).add_to(m)
        
        # Iterate through stops and fetch real road paths
        for idx, stop in enumerate(rt['path']):
            stop_pos = (stop['lat'], stop['lon'])
            
            # 1. Fetch real geometry from Google
            path_points = get_google_route(current_pos[0], current_pos[1], stop_pos[0], stop_pos[1])
            
            # 2. Draw Polyline (Blue for road, Cyan dashed fallback)
            if path_points and path_points[0]: # Ensure route valid
                folium.PolyLine(
                    path_points[0], # Points
                    color="#4dabf7", weight=5, opacity=0.8, tooltip=f"Leg {idx+1}: {path_points[1]} ({path_points[2]})"
                ).add_to(m)
            else:
                folium.PolyLine(
                    [current_pos, stop_pos], 
                    color="cyan", weight=3, opacity=0.6, dash_array='5, 10', tooltip=f"Leg {idx+1} (Direct)"
                ).add_to(m)
            
            # 3. Add stop number marker
            label = str(idx + 1)
            folium.Marker(
                stop_pos, 
                icon=folium.DivIcon(html=f"<div style='font-size: 16pt; color: #4dabf7; font-weight: 900; text-shadow: 2px 2px #000;'>{label}</div>")
            ).add_to(m)
            
            current_pos = stop_pos

    # SEARCH RESULT & ROUTE DRAWING
    if st.session_state.search_active and st.session_state.search_result:
        t = st.session_state.search_result
        st.success(f"Target: {t['addr']}")
        folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="red", icon="crosshairs", prefix='fa')).add_to(m)
        
        # Display Info & Draw Cached Routes
        if st.session_state.cached_routes:
            with st.container():
                st.markdown("### 👷 Nearest Active Engineers")
                cols = st.columns(3)
                for i, r_data in enumerate(st.session_state.cached_routes):
                    # 1. Show Info
                    col = cols[i] if i < 3 else None
                    if col:
                        col.info(f"**{r_data['name']}**\n\n🛣️ {r_data['dist_text']} \n\n⏱️ {r_data['dur_text']}")
                    
                    # 2. Draw Route on Map (Only if points exist)
                    if r_data['points']:
                        folium.PolyLine(
                            r_data['points'], 
                            color=r_data['color'], weight=4, opacity=0.7, 
                            tooltip=f"To {r_data['name']}: {r_data['dist_text']} ({r_data['dur_text']})"
                        ).add_to(m)
        
        m.fit_bounds([[t['lat'], t['lon']]])

    # IMPORTANT: returned_objects=[] stops map interaction from reloading app
    st_folium(m, width=None, height=600, key="map_main", returned_objects=[])

# --- TAB 2: LIST (UPDATED: EDITABLE) ---
with tab_list:
    st.subheader("📋 Fleet Management")
    
    if engineers:
        # 1. Fetch Today's Schedule to find "Current Job"
        today_str = str(date.today())
        todays_jobs = get_schedule(st.session_state.company_id, today_str, today_str)
        
        # Create map: Engineer Name -> Job Ref(s)
        job_map = {}
        for j in todays_jobs:
            eng = j['engineer_name']
            ref = j['job_ref']
            if eng in job_map:
                job_map[eng].append(ref)
            else:
                job_map[eng] = [ref]
        
        # 2. Build DataFrame for Editor
        df_data = []
        for e in engineers:
            current_job = ", ".join(job_map.get(e['name'], ["Available"]))
            # No pin_color here anymore
            
            df_data.append({
                'id': e['id'],
                'name': e['name'],
                'status': e['status'],
                'current_job': current_job
            })
        
        df = pd.DataFrame(df_data)
        
        # 3. Define Column Configs
        status_options = ["Active", "Home", "Driving", "On Site", "In Office", "Sick", "Holiday"]
        
        # 4. Display Data Editor
        edited_df = st.data_editor(
            df,
            column_config={
                "id": None, # Hide ID
                "name": st.column_config.TextColumn("Name", required=True),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=status_options,
                    required=True
                ),
                "current_job": st.column_config.TextColumn(
                    "Current Job (Today)",
                    disabled=True # Read-only
                )
            },
            use_container_width=True,
            num_rows="fixed",
            key="fleet_editor"
        )
        
        # 5. Save Button
        if st.button("Save Fleet Changes"):
            # Prepare updates list
            updates = []
            # Compare rows or just update all (safest for small datasets)
            for index, row in edited_df.iterrows():
                updates.append({
                    'id': int(row['id']),
                    'name': row['name'],
                    'status': row['status']
                })
            
            # Perform Batch Update
            success_count = 0
            
            # Since we defined update_engineer_batch earlier (or we can loop here)
            # Let's loop here to be explicit and safe
            try:
                for u in updates:
                    supabase.table("Engineers").update({
                        "Name": u['name'],
                        "status": u['status']
                    }).eq("id", u['id']).execute()
                    success_count += 1
                st.success(f"Updated {success_count} engineers successfully!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Update failed: {e}")

    else:
        st.info("No engineers found.")

# --- TAB 3: JOBS ---
with tab_jobs:
    with st.expander("➕ Add New Job", expanded=False):
        st.caption("New Job Entry")
        with st.form("new_job_form_tab"):
            c1, c2 = st.columns(2)
            j_r = c1.text_input("Job Ref")
            j_p = c2.text_input("Postcode")
            # Changed key to avoid duplicate ID error
            j_desc = st.text_input("Description (Optional)", key="j3_tab")
            j_dir = st.text_input("Director Name (Optional)", key="j4_tab")
            j_sev = st.select_slider("Severity", options=["Low", "Medium", "Critical"], value="Low")
            if st.form_submit_button("Add Job", type="primary"):
                ok, m, coords = add_entry("Jobs", "Job_Ref", j_r, j_p, st.session_state.company_id, desc=j_desc, director=j_dir, severity=j_sev)
                if ok: 
                    st.success(m)
                    # Show nearest engineer immediately
                    if coords:
                        near_msg = find_nearest_engineer_text(coords[0], coords[1], engineers)
                        st.info(near_msg)
                    time.sleep(3)
                    st.rerun()
    st.divider()
    if jobs:
        h1, h2, h3, h4, h5 = st.columns([2, 3, 2, 2, 1])
        h1.markdown("**Ref**")
        h2.markdown("**Description**")
        h3.markdown("**Director**")
        h4.markdown("**Severity**")
        h5.markdown("**Action**")
        st.divider()
        for j in jobs:
            c1, c2, c3, c4, c5 = st.columns([2, 3, 2, 2, 1])
            c1.write(j['ref'])
            c2.write(j.get('desc', '-'))
            c3.write(j.get('director', '-'))
            sev = j.get('severity') or 'Low'
            color = "green" if "low" in sev.lower() else "orange" if "medium" in sev.lower() else "red"
            c4.markdown(f":{color}[{sev}]")
            if c5.button("Delete", key=f"del_{j['id']}", help="Cancels job and removes from diary"):
                if delete_record("Jobs", j['id'], j['ref'], "job_ref"):
                    st.success("Deleted & Cancelled!")
                    time.sleep(0.5)
                    st.rerun()
    else: st.info("No active jobs found.")

# --- TAB 4: INSTALLS ---
with tab_installs:
    with st.expander("➕ Add New Install", expanded=False):
        st.caption("New Install Entry")
        with st.form("new_install_form"):
            i_c1, i_c2 = st.columns(2)
            i_ref = i_c1.text_input("Job/Install Ref")
            i_pc = i_c2.text_input("Postcode")
            i_desc = st.text_input("Description (Optional)") 
            i_dir = st.text_input("Director Name (Optional)") 
            i_stat = st.select_slider("Status", options=["Not passed Finance", "Passed Finance", "Kit Ordered", "Kit Arrived"], value="Not passed Finance")
            if st.form_submit_button("Add Install", type="primary"):
                # Changed Job_Ref to Install_Ref as requested
                ok, m, coords = add_entry("Installs", "Install_Ref", i_ref, i_pc, st.session_state.company_id, install_status=i_stat, desc=i_desc, director=i_dir)
                if ok:
                    st.success(m)
                    # Show nearest engineer immediately
                    if coords:
                        near_msg = find_nearest_engineer_text(coords[0], coords[1], engineers)
                        st.info(near_msg)
                    time.sleep(3)
                    st.rerun()
    st.divider()
    if installs:
        ih1, ih2, ih3, ih4 = st.columns([2, 2, 4, 1])
        ih1.markdown("**Reference**")
        ih2.markdown("**Details**") 
        ih3.markdown("**Status**")
        ih4.markdown("**Action**")
        st.divider()
        for inst in installs:
            ic1, ic2, ic3, ic4 = st.columns([2, 2, 4, 1])
            ic1.write(inst['ref'])
            details = f"📍 {inst['postcode']}"
            if inst.get('desc'): details += f"\n📝 {inst['desc']}"
            if inst.get('director'): details += f"\n👤 {inst['director']}"
            ic2.text(details)
            current_status = inst.get('status', 'Not passed Finance')
            options = ["Not passed Finance", "Passed Finance", "Kit Ordered", "Kit Arrived"]
            if current_status not in options: options.insert(0, current_status)
            new_status = ic3.select_slider("Status", options=options, value=current_status, key=f"sl_inst_{inst['id']}", label_visibility="collapsed")
            if new_status != current_status:
                update_install_status(inst['id'], new_status)
                st.toast(f"Updated {inst['ref']}")
                time.sleep(0.5)
                st.rerun()
            if ic4.button("Delete", key=f"del_inst_{inst['id']}", help="Cancels install and removes from diary"):
                if delete_record("Installs", inst['id'], inst['ref'], "job_ref"):
                    st.success("Deleted & Cancelled!")
                    time.sleep(0.5)
                    st.rerun()
    else: st.info("No installs active.")

# --- TAB 5: SCHEDULE ---
with tab_schedule:
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        st.subheader("📅 Assign Work")
        eng_names = [e['name'] for e in engineers] if engineers else []
        sel_date = st.date_input("Date", min_value=datetime.today())
        
        # 1. Maintenance Form (Multi-select enabled)
        with st.expander("Assign Maintenance", expanded=True):
            with st.form("schedule_maint_form"):
                m_eng = st.selectbox("Engineer", eng_names, key="m_eng")
                maint_options = [j['ref'] for j in jobs] if jobs else []
                m_ref = st.selectbox("Maintenance Ref", maint_options, index=None, placeholder="Select Job...", key="m_ref")
                m_notes = st.text_area("Notes", key="m_notes")
                
                if st.form_submit_button("Assign Maintenance", type="primary"):
                    if m_eng and m_ref:
                        ok = add_schedule_item(st.session_state.company_id, m_eng, m_ref, sel_date, m_notes, "Maintenance")
                        if ok:
                            st.success(f"Assigned {m_eng} to {m_ref}")
                            time.sleep(1)
                            st.rerun()
                        else: st.error("Failed")
                    else: st.warning("Select Engineer and Job")

        # 2. Install Form (Multi-select enabled)
        with st.expander("Assign Install", expanded=False):
            with st.form("schedule_install_form"):
                i_eng = st.selectbox("Engineer", eng_names, key="i_eng")
                inst_options = [i['ref'] for i in installs] if installs else []
                i_ref = st.selectbox("Install Ref", inst_options, index=None, placeholder="Select Install...", key="i_ref")
                i_notes = st.text_area("Notes", key="i_notes")
                
                if st.form_submit_button("Assign Install", type="primary"):
                    if i_eng and i_ref:
                        ok = add_schedule_item(st.session_state.company_id, i_eng, i_ref, sel_date, i_notes, "Install")
                        if ok:
                            st.success(f"Assigned {i_eng} to {i_ref}")
                            time.sleep(1)
                            st.rerun()
                        else: st.error("Failed")
                    else: st.warning("Select Engineer and Install")

        # 3. Add Message/Note (New Requirement)
        with st.expander("Add Diary Note / Message", expanded=False):
            with st.form("diary_note_form"):
                n_eng = st.selectbox("For Engineer (Optional)", ["All"] + eng_names, key="n_eng")
                n_date = st.date_input("Date", value=datetime.today(), key="n_date")
                n_msg = st.text_area("Message / Special Request")
                
                if st.form_submit_button("Add Note", type="primary"):
                    if n_msg:
                        target = "ALL STAFF" if n_eng == "All" else n_eng
                        add_schedule_item(st.session_state.company_id, target, "NOTE", n_date, n_msg, "Note")
                        st.success("Note Added")
                        time.sleep(1)
                        st.rerun()

    with col_b:
        c_head, c_filt = st.columns([3, 1])
        c_head.subheader("📆 Weekly Schedule")
        focus_date = c_filt.date_input("Week of:", value=datetime.today())
        start_of_week = get_start_of_week(focus_date)
        end_of_week = start_of_week + timedelta(days=6)
        schedule_items = get_schedule(st.session_state.company_id, start_of_week, end_of_week)
        days_cols = st.columns(7)
        days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        for i, col in enumerate(days_cols):
            current_day = start_of_week + timedelta(days=i)
            col.markdown(f"**{days_names[i]}**")
            col.caption(f"{current_day.strftime('%d/%m')}")
            col.divider()
            day_str = current_day.strftime('%Y-%m-%d')
            day_items = [item for item in schedule_items if item['scheduled_date'] == day_str]
            
            for item in day_items:
                note_text = str(item.get('notes', ''))
                if "[INSTALL]" in note_text: css_class = "install"
                elif "[NOTE]" in note_text: css_class = "note"
                else: css_class = "job"
                
                content = item['job_ref']
                if css_class == "note":
                    content = note_text.replace("[NOTE]", "").strip()
                
                col.markdown(f"""
                <div class="schedule-card {css_class}">
                    <small><b>{item['engineer_name']}</b></small><br>
                    {content}
                </div>
                """, unsafe_allow_html=True)