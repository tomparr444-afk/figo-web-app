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
import json
import random

# --- CONFIGURATION ---
APP_NAME = "Micro CRM"
LOGO_FILENAME = "Micro CRM Logo.png"
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

# ⚠️ YOUR LIVE KEYS
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GOOGLE_MAPS_API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# --- PAGE SETUP ---
st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="💼", initial_sidebar_state="expanded")

# --- DB CONNECTION ---
@st.cache_resource
def init_connection():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except: return None
supabase = init_connection()

# --- STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'company_id' not in st.session_state: st.session_state.company_id = None
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
if 'search_result' not in st.session_state: st.session_state.search_result = None
if 'search_active' not in st.session_state: st.session_state.search_active = False
if 'route_stops' not in st.session_state: st.session_state.route_stops = []
if 'cached_routes' not in st.session_state: st.session_state.cached_routes = []
if 'selected_customer' not in st.session_state: st.session_state.selected_customer = None
if 'recent_customers' not in st.session_state: st.session_state.recent_customers = []
if 'main_menu' not in st.session_state: st.session_state.main_menu = "🏠 Dashboard"
if 'cust_draft' not in st.session_state: 
    st.session_state.cust_draft = {"name": "", "pc": "", "email": "", "phone": "", "directors": "", "reg_no": "", "offices": "", "notes": "", "voip": 0, "handsets": 0, "software": 0, "total_lic": 0}

# Theme State (Decoupled from widget to prevent unmount reset issues)
if 'is_light_mode' not in st.session_state: 
    st.session_state.is_light_mode = False 

def toggle_theme():
    st.session_state.is_light_mode = not st.session_state.is_light_mode

# --- AUTH ---
def check_login(username, password):
    if not supabase: return False
    if username.lower() == "admin" and password == ADMIN_PASSWORD: return "ADMIN"
    try:
        res = supabase.table("clients").select("*").eq("company_id", username).eq("password", password).execute()
        return username if res.data else None
    except: return None

# --- THEME CONFIGURATION & CSS ---
is_light = st.session_state.is_light_mode

if is_light:
    # Modern Light Mode (Salesforce/Hubspot style)
    bg_color, text_color, sidebar_bg, card_bg, border_color = "#f9fafb", "#111827", "#ffffff", "#ffffff", "#e5e7eb"
    button_bg, button_text, primary_btn = "#f3f4f6", "#111827", "#2563eb"
    tiles_style = "CartoDB positron"
else:
    # Modern Slate Dark Mode
    bg_color, text_color, sidebar_bg, card_bg, border_color = "#0f172a", "#f8fafc", "#1e293b", "#1e293b", "#334155"
    button_bg, button_text, primary_btn = "#334155", "#f8fafc", "#3b82f6"
    tiles_style = "CartoDB dark_matter"

# Global CSS Injection (Applied instantly to whole app)
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Apply font safely without breaking Streamlit icons */
    html, body, p, h1, h2, h3, h4, h5, h6, label, div[data-testid="stMarkdownContainer"] {{
        font-family: 'Inter', sans-serif !important;
    }}
    /* Specifically protect Streamlit's material icons from being overwritten */
    .material-symbols-rounded, .material-icons, span[class*="icon"] {{
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }}

    /* Main Backgrounds */
    .stApp, [data-testid="stHeader"] {{ background-color: {bg_color} !important; }}
    [data-testid="stSidebar"] {{ background-color: {sidebar_bg} !important; border-right: 1px solid {border_color} !important; }}
    
    /* Make Sidebar Text Professional */
    [data-testid="stSidebar"] .stRadio label p {{ font-size: 1.05rem !important; font-weight: 500; padding: 6px 0px; color: {text_color}; }}
    
    /* Metrics Cards */
    [data-testid="stMetric"] {{
        background-color: {card_bg}; border: 1px solid {border_color}; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    [data-testid="stMetricValue"] > div {{ color: {text_color} !important; }}
    [data-testid="stMetricLabel"] > div > p {{ color: {text_color} !important; opacity: 0.8; }}
    
    /* Inputs */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea, .stNumberInput input {{
        background-color: {card_bg} !important; color: {text_color} !important; border: 1px solid {border_color} !important; border-radius: 6px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02); -webkit-text-fill-color: {text_color} !important;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{ 
        border-color: {primary_btn} !important; box-shadow: 0 0 0 1px {primary_btn} !important;
    }}
    
    /* Standard Buttons */
    .stButton > button {{ 
        background-color: {button_bg} !important; border: 1px solid {border_color} !important; border-radius: 6px; font-weight: 500; transition: all 0.2s ease; 
    }}
    .stButton > button p {{ color: {button_text} !important; font-weight: 500; font-family: 'Inter', sans-serif !important; }}
    .stButton > button:hover {{ border-color: {primary_btn} !important; transform: translateY(-1px); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
    .stButton > button:hover p {{ color: {primary_btn} !important; }}

    /* Primary Form Submit Buttons */
    .stButton > button[kind="primary"] {{ background-color: {primary_btn} !important; border-color: {primary_btn} !important; }}
    .stButton > button[kind="primary"] p {{ color: #ffffff !important; font-weight: 600; }}
    .stButton > button[kind="primary"]:hover {{ opacity: 0.9; transform: translateY(-1px); }}
    .stButton > button[kind="primary"]:hover p {{ color: #ffffff !important; }}

    /* Expander Cards */
    .streamlit-expanderHeader {{ background-color: {card_bg} !important; border-radius: 6px; color: {text_color} !important; border: 1px solid {border_color} !important; font-weight: 600; }}
    [data-testid="stExpander"] {{ border: none !important; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-radius: 6px; background-color: {card_bg} !important; }}

    /* Calendar Card Style */
    .schedule-card {{ 
        background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 6px; padding: 12px; margin-bottom: 12px; 
        border-left: 4px solid {primary_btn}; color: {text_color}; 
    }}
    .schedule-card.install {{ border-left: 4px solid #8b5cf6; }}
    .schedule-card.note {{ border-left: 4px solid #f59e0b; }}
    
    /* Fonts overrides for legibility */
    h1, h2, h3, h4, h5, h6, label {{ color: {text_color} !important; font-weight: 600 !important; }}
    div[data-testid="stMarkdownContainer"] > p {{ color: {text_color}; }}
    
    /* Hide Default Branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}

    /* 📱 MOBILE RESPONSIVE FIXES */
    @media (max-width: 768px) {{
        .block-container {{ padding-top: 2rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }}
        div[data-testid="metric-container"] {{ margin-bottom: 10px; }}
        div[data-testid="stDataFrame"] {{ overflow-x: auto; }}
        .stButton button {{ min-height: 44px; }}
    }}
</style>
""", unsafe_allow_html=True)

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    login_holder = st.empty() 
    with login_holder.container():
        col1, col2, col3 = st.columns([1, 8, 1])
        with col2:
            st.markdown(f"<h1 style='text-align: center; margin-top: 100px;'>💼 {APP_NAME} Access</h1>", unsafe_allow_html=True)
            with st.form("login"):
                user = st.text_input("Username", key="login_username_input")
                pw = st.text_input("Password", type="password", key="login_password_input")
                
                if st.form_submit_button("Secure Login", type="primary"): 
                    res = check_login(user, pw)
                    if res:
                        st.session_state.logged_in = True
                        st.session_state.is_admin = (res == "ADMIN")
                        st.session_state.company_id = "demo" if res == "ADMIN" else res
                        login_holder.empty() 
                        st.rerun()
                    else: st.error("Access Denied")
    st.stop()

# --- TOP BAR / THEME TOGGLE ---
c1, c2 = st.columns([9, 1])
with c2:
    st.button("☀️ Light" if not is_light else "🌙 Dark", on_click=toggle_theme, use_container_width=True)

# --- HELPER FUNCTIONS ---
def generate_ticket(job_type):
    """Generates unique ticket strings. MC1 for installs, MC2 for Maintenance."""
    prefix = "MC1" if job_type == "Install" else "MC2"
    return f"{prefix}{random.randint(10000, 99999)}"

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    return c * 3956

def decode_polyline(polyline_str):
    index, lat, lng, coordinates, length = 0, 0, 0, [], len(polyline_str)
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
    if not GOOGLE_MAPS_API_KEY: return None
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={start_lat},{start_lon}&destination={end_lat},{end_lon}&mode=driving&units=imperial&key={GOOGLE_MAPS_API_KEY}"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            pts = res['routes'][0]['overview_polyline']['points']
            leg = res['routes'][0]['legs'][0]
            return decode_polyline(pts), leg['distance']['text'], leg['duration']['text']
    except: pass
    return None

def fetch_company_info_ai(company_name, postcode):
    if not GEMINI_API_KEY:
        st.error("GEMINI_API_KEY missing from secrets. Auto-find disabled.")
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""
    Find public business information for a UK company named '{company_name}' near postcode '{postcode}'. 
    Return ONLY a JSON object with these exact keys:
    "directors" (string, comma separated names),
    "email" (string, best guess generic contact email),
    "phone" (string, best guess contact number),
    "registration_number" (string, UK Companies House number),
    "offices" (string, list of addresses or locations),
    "voip" (int, best guess or 0),
    "handsets" (int, best guess or 0),
    "software" (int, best guess or 0),
    "total_lic" (int, best guess or 0).
    If you don't know a field, leave it as an empty string or 0 for ints. DO NOT include markdown backticks around the JSON.
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    try:
        res = requests.post(url, json=payload).json()
        text = res['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text)
    except Exception as e:
        print(f"AI Fetch Error: {e}")
        return None

def optimize_route(start_coords, stops):
    route, current_loc, unvisited = [], start_coords, stops.copy()
    while unvisited:
        nearest, min_dist = None, float('inf')
        for stop in unvisited:
            dist = haversine(current_loc[1], current_loc[0], stop['lon'], stop['lat'])
            if dist < min_dist: min_dist, nearest = dist, stop
        if nearest:
            route.append(nearest)
            current_loc = (nearest['lat'], nearest['lon'])
            unvisited.remove(nearest)
    return route

def get_engineer_color(name, status, custom_color=None):
    if status in ["Sick", "Holiday"]: return "gray"
    valid_colors = {'red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray'}
    clean_color = custom_color.split()[0].lower() if custom_color else None
    if clean_color and clean_color in valid_colors: return clean_color
    return "blue"

def get_job_color(severity):
    severity = str(severity).lower() if severity else 'low'
    if "critical" in severity or "high" in severity: return "red"
    if "medium" in severity: return "orange" 
    return "green"

def find_nearest_engineer_text(lat, lon, engineers_list):
    working_statuses = ["Active", "Driving", "On Site", "In Office", "Home"]
    active_engs = [e for e in engineers_list if e['status'] in working_statuses]
    if not active_engs: return "No active engineers found."
    for e in active_engs: e['temp_dist'] = haversine(lon, lat, e['lon'], e['lat'])
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
            'pin_color': r.get('pin_color') or 'blue',
            'email': r.get('email', ''),
            'mobile': r.get('mobile', '')
        } for r in res.data]
    except: return []

def get_jobs(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Jobs").select("*").eq("Company_ID", company_id).execute()
        return [{'id': r['id'], 'ref': r.get('Job_Ref'), 'lat': r['Latitude'], 'lon': r['Longitude'], 'desc': r.get('Description', ''), 'director': r.get('Director_Name', ''), 'severity': r.get('severity') or 'Low', 'customer': r.get('Customer_Name', ''), 'status': r.get('status', 'Pending')} for r in res.data if r.get('Latitude') and r.get('Longitude')]
    except: return []

def get_installs(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Installs").select("*").eq("Company_ID", company_id).execute()
        return [{'id': r['id'], 'ref': r.get('Install_Ref') or r.get('Job_Ref'), 'status': r.get('status') or 'Not passed Finance', 'postcode': r.get('Postcode'), 'lat': r['Latitude'], 'lon': r['Longitude'], 'desc': r.get('Description', ''), 'director': r.get('Director_Name', ''), 'customer': r.get('Customer_Name', '')} for r in res.data if r.get('Latitude') and r.get('Longitude')]
    except: return []

def get_customers(company_id):
    if not supabase: return []
    try:
        res = supabase.table("Customers").select("*").eq("Company_ID", company_id).execute()
        return res.data
    except: return []

def get_schedule(company_id, start_date=None, end_date=None):
    if not supabase: return []
    try:
        query = supabase.table("job_schedule").select("*").eq("company_id", company_id)
        if start_date: query = query.gte("scheduled_date", str(start_date))
        if end_date: query = query.lte("scheduled_date", str(end_date))
        res = query.order("scheduled_date", desc=False).execute()
        return res.data
    except: return []

def add_schedule_item(company_id, engineer, job, date_obj, notes, job_type="Maintenance"):
    if not supabase: return False
    try:
        payload = {
            "company_id": company_id,
            "engineer_name": engineer,
            "job_ref": job,
            "scheduled_date": str(date_obj),
            "notes": notes,
        }
        if job_type == "Install": payload["notes"] = f"[INSTALL] {notes}"
        elif job_type == "Note": payload["notes"] = f"[NOTE] {notes}"
        
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
    try:
        if record_ref and ref_col:
            supabase.table("job_schedule").delete().eq("job_ref", record_ref).execute()
        supabase.table(table).delete().eq("id", record_id).execute()
        return True
    except Exception as e:
        return False

def add_entry(table, name_col, name_val, postcode, company_id, desc=None, director=None, severity=None, pin_color=None, install_status=None, customer_name=None):
    geolocator = Nominatim(user_agent="microcrm_adder_v1")
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
                payload["status"] = "Pending"
                if desc: payload["Description"] = desc 
                if director: payload["Director_Name"] = director
                if severity: payload["severity"] = severity
                if customer_name and customer_name != "None": payload["Customer_Name"] = customer_name
            elif table == "Installs":
                payload["Postcode"] = postcode 
                if install_status: payload["status"] = install_status
                if desc: payload["Description"] = desc
                if director: payload["Director_Name"] = director
                if customer_name and customer_name != "None": payload["Customer_Name"] = customer_name

            supabase.table(table).insert(payload).execute()
            return True, f"Added {name_val}", (loc.latitude, loc.longitude)
        return False, "Postcode not found", None
    except Exception as e: 
        return False, "Error", None

def process_bulk_upload(df, type_flag, company_id):
    geolocator = Nominatim(user_agent=f"microcrm_bulk_v1")
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

# --- LOAD DATA ---
engineers = get_engineers(st.session_state.company_id)
jobs = get_jobs(st.session_state.company_id)
installs = get_installs(st.session_state.company_id)
customers = get_customers(st.session_state.company_id)
all_schedule = get_schedule(st.session_state.company_id)

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    try: st.image(LOGO_FILENAME, width=220)
    except: st.header(APP_NAME)
    st.caption(f"CONNECTED: {st.session_state.company_id.upper() if st.session_state.company_id else 'NONE'}")
    
    if st.button("Logout", use_container_width=True): 
        st.session_state.logged_in = False
        st.rerun()
    st.markdown("---")
    
    # Quick Customer Search
    def quick_search_callback():
        val = st.session_state.quick_search_val
        if val:
            st.session_state.selected_customer = val
            st.session_state.main_menu = "👥 Customers"
            if val in st.session_state.recent_customers:
                st.session_state.recent_customers.remove(val)
            st.session_state.recent_customers.insert(0, val)
            st.session_state.recent_customers = st.session_state.recent_customers[:3]

    if customers:
        search_options = [""] + [c['Name'] for c in customers]
        st.selectbox("🔍 Quick Search", search_options, key="quick_search_val", on_change=quick_search_callback, help="Instantly open a customer profile")

    st.markdown("---")
    
    page = st.radio("MAIN MENU", [
        "🏠 Dashboard", 
        "📋 Fleet List", 
        "🔧 Maintenance", 
        "🛠️ Installations", 
        "👥 Customers",
        "📅 Schedule Work",
        "⬆️ Data Upload"
    ], label_visibility="collapsed", key="main_menu")
    
    # Override page if a customer is selected via quick search
    if st.session_state.selected_customer:
        page = "👥 Customers"
    
    st.markdown("---")
    if st.session_state.is_admin:
        try:
            res = supabase.table("Engineers").select("Company_ID").execute()
            comps = sorted(list(set([r['Company_ID'] for r in res.data if r['Company_ID']])))
            if comps: st.session_state.company_id = st.selectbox("Admin Target:", comps)
        except: pass

# --- PAGE: DASHBOARD ---
if page == "🏠 Dashboard":
    st.title("Overview")
    
    # Top Metrics
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("Active Engineers", len([e for e in engineers if e['status'] in ["Active", "Driving", "On Site"]]))
    mc2.metric("Open Maintenance", len([j for j in jobs if j.get('status') != 'Completed']))
    mc3.metric("Pending Installs", len([i for i in installs if i.get('status') != 'Completed']))
    
    today_str = str(date.today())
    todays_jobs = [s for s in all_schedule if s.get('scheduled_date') == today_str]
    mc4.metric("Jobs Today", len(todays_jobs))
    mc5.metric("Total Customers", len(customers))
    
    st.divider()
    
    col_map, col_sched = st.columns([5, 3])
    
    with col_map:
        st.subheader("Dispatch Map")
        
        # 1. Search Single
        with st.expander("🔍 Single Visit Routing", expanded=False):
            with st.form("search"):
                c1, c2 = st.columns([3,1], vertical_alignment="bottom")
                with c1: p_code = st.text_input("Target Postcode")
                with c2: search = st.form_submit_button("Scan", type="primary")
            
            if search and p_code:
                geo = Nominatim(user_agent="microcrm_search_v1", timeout=10)
                try:
                    l = geo.geocode(p_code)
                    if l:
                        st.session_state.search_result = {'lat': l.latitude, 'lon': l.longitude, 'addr': l.address}
                        st.session_state.search_active = True
                        
                        st.session_state.cached_routes = [] 
                        working_statuses = ["Active", "Driving", "On Site", "In Office", "Home"]
                        active_engineers = [e for e in engineers if e['status'] in working_statuses]
                        
                        for e in active_engineers:
                            e['temp_dist'] = haversine(l.longitude, l.latitude, e['lon'], e['lat'])
                        active_engineers.sort(key=lambda x: x['temp_dist'])
                        top3 = active_engineers[:3]
                        
                        for eng in top3:
                            route_data = get_google_route(eng['lat'], eng['lon'], l.latitude, l.longitude)
                            if route_data:
                                pts, d_text, dur_text = route_data
                                st.session_state.cached_routes.append({'name': eng['name'], 'points': pts, 'dist_text': d_text, 'dur_text': dur_text, 'color': primary_btn})
                            else:
                                st.session_state.cached_routes.append({'name': eng['name'], 'points': None, 'dist_text': f"{eng['temp_dist']:.1f} miles (Direct)", 'dur_text': "N/A", 'color': "orange"})
                    else: st.error("Location not found")
                except: st.error("Search Failed")

        # 2. Route Planner
        with st.expander("🚚 Multiple Visit Routing", expanded=False):
            c1, c2 = st.columns([3, 1])
            new_stop = c1.text_input("Add Stop (Postcode)", key="route_input")
            if c2.button("Add Stop") and new_stop:
                geo_r = Nominatim(user_agent="microcrm_route_v1")
                l_r = geo_r.geocode(new_stop)
                if l_r:
                    st.session_state.route_stops.append({'addr': new_stop, 'lat': l_r.latitude, 'lon': l_r.longitude})
                    st.rerun()
                else: st.error("Invalid Postcode")
            
            if st.session_state.route_stops:
                st.write(f"Stops configured: {len(st.session_state.route_stops)}")
                st.dataframe(pd.DataFrame(st.session_state.route_stops)[['addr']], hide_index=True, use_container_width=True)
                start_opts = ["Custom..."] + [e['name'] for e in engineers]
                start_sel = st.selectbox("Start Point:", start_opts)
                
                start_coords = None
                if start_sel == "Custom...":
                    start_txt = st.text_input("Custom Start Postcode")
                    if start_txt:
                        geo_s = Nominatim(user_agent="microcrm_start")
                        ls = geo_s.geocode(start_txt)
                        if ls: start_coords = (ls.latitude, ls.longitude)
                else:
                    eng = next((e for e in engineers if e['name'] == start_sel), None)
                    if eng: start_coords = (eng['lat'], eng['lon'])

                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("Optimize Route", type="primary", use_container_width=True) and start_coords:
                    optimized = optimize_route(start_coords, st.session_state.route_stops)
                    st.session_state.optimized_route = {'start': start_coords, 'path': optimized}
                
                if col_btn2.button("Clear Route", use_container_width=True):
                    st.session_state.route_stops = []
                    if 'optimized_route' in st.session_state: del st.session_state.optimized_route
                    st.rerun()

        # Render Map
        m = folium.Map(location=[54.5, -4.0], zoom_start=6, tiles=tiles_style)

        for eng in engineers:
            folium.Marker(
                [eng['lat'], eng['lon']],
                tooltip=f"{eng['name']} ({eng['status']})", 
                popup=f"USER: {eng['name']}\nSTATUS: {eng['status']}",
                icon=folium.Icon(color=get_engineer_color(eng['name'], eng['status'], eng.get('pin_color')), icon="user")
            ).add_to(m)

        for job in jobs:
            if job.get('status') == 'Completed': continue
            popup_content = f"TICKET: {job.get('ref')}\nDESC: {job.get('desc', '')}\nSEVERITY: {job.get('severity')}"
            folium.Marker(
                [job['lat'], job['lon']],
                tooltip=f"JOB: {job.get('ref')}", popup=popup_content,
                icon=folium.Icon(color=get_job_color(job.get('severity', 'Low')), icon="briefcase", prefix='fa')
            ).add_to(m)

        for inst in installs:
            if inst.get('status') == 'Completed': continue
            folium.Marker(
                [inst['lat'], inst['lon']],
                tooltip=f"INSTALL: {inst.get('ref')}", popup=f"TICKET: {inst.get('ref')}\nSTATUS: {inst.get('status')}",
                icon=folium.Icon(color='purple', icon="wrench", prefix='fa') 
            ).add_to(m)

        if 'optimized_route' in st.session_state:
            rt = st.session_state.optimized_route
            current_pos = rt['start']
            folium.Marker(rt['start'], popup="Start", icon=folium.Icon(color="green", icon="play", prefix='fa')).add_to(m)
            
            for idx, stop in enumerate(rt['path']):
                stop_pos = (stop['lat'], stop['lon'])
                path_points = get_google_route(current_pos[0], current_pos[1], stop_pos[0], stop_pos[1])
                
                if path_points and path_points[0]:
                    folium.PolyLine(path_points[0], color=primary_btn, weight=5, opacity=0.8, tooltip=f"Leg {idx+1}: {path_points[1]} ({path_points[2]})").add_to(m)
                else:
                    folium.PolyLine([current_pos, stop_pos], color="cyan", weight=3, opacity=0.6, dash_array='5, 10', tooltip=f"Leg {idx+1} (Direct)").add_to(m)
                
                folium.Marker(stop_pos, icon=folium.DivIcon(html=f"<div style='font-size: 16pt; color: {primary_btn}; font-weight: 900; text-shadow: 2px 2px #fff;'>{str(idx + 1)}</div>")).add_to(m)
                current_pos = stop_pos

        if st.session_state.search_active and st.session_state.search_result:
            t = st.session_state.search_result
            folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="red", icon="crosshairs", prefix='fa')).add_to(m)
            
            if st.session_state.cached_routes:
                with st.container():
                    st.markdown("##### Nearest Active Engineers")
                    cc1, cc2, cc3 = st.columns(3)
                    for i, r_data in enumerate(st.session_state.cached_routes):
                        col = [cc1, cc2, cc3][i] if i < 3 else None
                        if col:
                            col.info(f"**{r_data['name']}**\n\n🛣️ {r_data['dist_text']} \n\n⏱️ {r_data['dur_text']}")
                        if r_data['points']:
                            folium.PolyLine(r_data['points'], color=r_data['color'], weight=4, opacity=0.7, tooltip=f"To {r_data['name']}: {r_data['dist_text']} ({r_data['dur_text']})").add_to(m)
            m.fit_bounds([[t['lat'], t['lon']]])

        st_folium(m, use_container_width=True, height=500, key="map_dashboard", returned_objects=[])

    with col_sched:
        c_head, c_filt = st.columns([3, 2])
        c_head.subheader("Week Schedule")
        focus_date = c_filt.date_input("Week of:", value=datetime.today(), label_visibility="collapsed", key="dash_date")
        
        start_of_week = focus_date - timedelta(days=focus_date.weekday())
        
        days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        for i in range(7):
            current_day = start_of_week + timedelta(days=i)
            day_str = current_day.strftime('%Y-%m-%d')
            day_items = [item for item in all_schedule if item.get('scheduled_date') == day_str]
            
            with st.expander(f"{days_names[i]} - {current_day.strftime('%d/%m')}", expanded=(current_day == date.today() or bool(day_items))):
                if not day_items:
                    st.caption("No appointments.")
                for item in day_items:
                    note_text = str(item.get('notes', ''))
                    if "[INSTALL]" in note_text: css_class = "install"
                    elif "[NOTE]" in note_text: css_class = "note"
                    else: css_class = "job"
                    
                    content = item['job_ref']
                    if css_class == "note": content = note_text.replace("[NOTE]", "").strip()
                    
                    st.markdown(f"""
                    <div class="schedule-card {css_class}">
                        <small style="opacity: 0.8;"><b>{item['engineer_name']}</b></small><br>
                        <span style="font-size: 0.95em;">{content}</span>
                    </div>
                    """, unsafe_allow_html=True)

# --- PAGE: FLEET LIST ---
elif page == "📋 Fleet List":
    st.title("Fleet Management")
    if engineers:
        today_str = str(date.today())
        todays_jobs = [s for s in all_schedule if s.get('scheduled_date') == today_str]
        job_map = {}
        for j in todays_jobs:
            eng = j['engineer_name']
            if eng in job_map: job_map[eng].append(j['job_ref'])
            else: job_map[eng] = [j['job_ref']]
        
        df_data = []
        for e in engineers:
            df_data.append({
                'id': str(e['id']), 
                'name': e['name'],
                'status': e['status'],
                'email': e.get('email', ''),
                'mobile': e.get('mobile', ''),
                'current_job': ", ".join(job_map.get(e['name'], ["Available"]))
            })
        
        df = pd.DataFrame(df_data)
        status_options = ["Active", "Home", "Driving", "On Site", "In Office", "Sick", "Holiday"]
        
        edited_df = st.data_editor(
            df,
            column_config={
                "id": None,
                "name": st.column_config.TextColumn("Name", required=True),
                "status": st.column_config.SelectboxColumn("Status", options=status_options, required=True),
                "email": st.column_config.TextColumn("Email Address"),
                "mobile": st.column_config.TextColumn("Mobile Number"),
                "current_job": st.column_config.TextColumn("Current Assignment", disabled=True)
            },
            use_container_width=True, num_rows="fixed", key="fleet_editor"
        )
        
        if st.button("Save Roster Changes", type="primary"):
            try:
                for index, row in edited_df.iterrows():
                    payload = {"Name": row['name'], "status": row['status']}
                    if 'email' in row: payload['email'] = row['email']
                    if 'mobile' in row: payload['mobile'] = row['mobile']
                    
                    supabase.table("Engineers").update(payload).eq("id", str(row['id'])).execute()
                st.success(f"Roster updated successfully.")
                time.sleep(1)
                st.rerun()
            except Exception as e: 
                st.error(f"Update failed: {e}")
    else: st.info("No engineers found in roster.")

# --- PAGE: MAINTENANCE ---
elif page == "🔧 Maintenance":
    st.title("Maintenance Tickets")

    with st.expander("➕ Create Maintenance Ticket", expanded=False):
        c_opts = ["None"] + [c['Name'] for c in customers] if customers else ["None"]
        j_cust = st.selectbox("Assign Customer", c_opts, key="maint_add_cust")
        
        default_pc, default_dir = "", ""
        if j_cust != "None":
            cust_data = next((c for c in customers if c['Name'] == j_cust), None)
            if cust_data:
                default_pc = cust_data.get('Postcode', '')
                default_dir = cust_data.get('Directors', '')

        c1, c2 = st.columns(2)
        j_p = c1.text_input("Postcode", value=default_pc, key="maint_add_pc")
        j_desc = c2.text_input("Description / Notes", key="maint_add_desc")
        
        j_dir = st.text_input("Contact Person", value=default_dir, key="maint_add_dir")
        j_sev = st.select_slider("Priority Level", options=["Low", "Medium", "Critical"], value="Low", key="maint_add_sev")
        
        if st.button("Generate Ticket", type="primary"):
            if not j_p:
                st.error("Postcode is required for routing.")
            else:
                ticket_num = generate_ticket("Maintenance")
                ok, m, coords = add_entry("Jobs", "Job_Ref", ticket_num, j_p, st.session_state.company_id, desc=j_desc, director=j_dir, severity=j_sev, customer_name=j_cust)
                if ok: 
                    st.success(f"Ticket Created: {ticket_num}")
                    if coords: st.info(find_nearest_engineer_text(coords[0], coords[1], engineers))
                    time.sleep(3); st.rerun()
                else: st.error("Failed to generate ticket.")

    active_jobs = [j for j in jobs if j.get('status') != 'Completed']
    comp_jobs = [j for j in jobs if j.get('status') == 'Completed']

    st.subheader("Active Workflow")
    if active_jobs:
        h1, h2, h3, h4, h5 = st.columns([2, 3, 2, 2, 2])
        h1.markdown("**Ticket ID**")
        h2.markdown("**Details**")
        h3.markdown("**Contact**")
        h4.markdown("**Priority**")
        h5.markdown("**Manage**")
        st.divider()
        for j in active_jobs:
            c1, c2, c3, c4, c5 = st.columns([2, 3, 2, 2, 2])
            c1.write(f"`{j['ref']}`")
            desc_text = j.get('desc', '')
            if j.get('customer'): desc_text += f" *(Client: {j['customer']})*"
            c2.markdown(desc_text if desc_text else '-')
            c3.write(j.get('director', '-'))
            sev = j.get('severity') or 'Low'
            color = "green" if "low" in sev.lower() else "orange" if "medium" in sev.lower() else "red"
            c4.markdown(f":{color}[**{sev.upper()}**]")
            
            with c5:
                btn_col1, btn_col2 = st.columns(2)
                if btn_col1.button("✅", key=f"comp_m_{j['id']}", help="Mark as Completed"):
                    supabase.table("Jobs").update({"status": "Completed"}).eq("id", j['id']).execute()
                    st.rerun()
                if btn_col2.button("🗑️", key=f"del_m_{j['id']}", help="Delete Ticket entirely"):
                    if delete_record("Jobs", j['id'], j['ref'], "job_ref"): st.rerun()
    else: st.info("No active maintenance tickets in queue.")

    st.divider()
    with st.expander("📦 Archived / Completed", expanded=False):
        if comp_jobs:
            for j in comp_jobs:
                c1, c2, c3 = st.columns([2, 5, 1])
                c1.write(f"`{j['ref']}`")
                c2.write(f"*{j.get('customer', 'Unknown')}* - **Completed**")
                if c3.button("Purge", key=f"del_comp_m_{j['id']}"):
                    if delete_record("Jobs", j['id'], j['ref'], "job_ref"): st.rerun()
        else: st.caption("No archived records.")

# --- PAGE: INSTALLATIONS ---
elif page == "🛠️ Installations":
    st.title("Installation Pipeline")
    
    with st.expander("➕ Create Installation Ticket", expanded=False):
        c_opts = ["None"] + [c['Name'] for c in customers] if customers else ["None"]
        i_cust = st.selectbox("Assign Customer", c_opts, key="inst_add_cust")
        
        default_pc, default_dir = "", ""
        if i_cust != "None":
            cust_data = next((c for c in customers if c['Name'] == i_cust), None)
            if cust_data:
                default_pc = cust_data.get('Postcode', '')
                default_dir = cust_data.get('Directors', '')

        i_c1, i_c2 = st.columns(2)
        i_pc = i_c1.text_input("Postcode", value=default_pc, key="inst_add_pc")
        i_desc = i_c2.text_input("Project Scope / Notes", key="inst_add_desc") 
        
        i_dir = st.text_input("Project Lead", value=default_dir, key="inst_add_dir") 
        i_stat = st.select_slider("Initial Stage", options=["Not passed Finance", "Passed Finance", "Kit Ordered", "Kit Arrived"], value="Not passed Finance", key="inst_add_stat")
        
        if st.button("Generate Ticket", type="primary"):
            if not i_pc:
                st.error("Postcode is required.")
            else:
                ticket_num = generate_ticket("Install")
                ok, m, coords = add_entry("Installs", "Install_Ref", ticket_num, i_pc, st.session_state.company_id, install_status=i_stat, desc=i_desc, director=i_dir, customer_name=i_cust)
                if ok:
                    st.success(f"Ticket Created: {ticket_num}")
                    if coords: st.info(find_nearest_engineer_text(coords[0], coords[1], engineers))
                    time.sleep(3); st.rerun()
                else: st.error("Failed to generate ticket.")

    active_inst = [i for i in installs if i.get('status') != 'Completed']
    comp_inst = [i for i in installs if i.get('status') == 'Completed']

    st.subheader("Active Projects")
    if active_inst:
        ih1, ih2, ih3, ih4 = st.columns([2, 3, 3, 2])
        ih1.markdown("**Ticket ID**")
        ih2.markdown("**Project Details**") 
        ih3.markdown("**Pipeline Stage**")
        ih4.markdown("**Manage**")
        st.divider()
        for inst in active_inst:
            ic1, ic2, ic3, ic4 = st.columns([2, 3, 3, 2])
            ic1.write(f"`{inst['ref']}`")
            details = f"📍 {inst['postcode']}"
            if inst.get('customer'): details += f" | 🏢 {inst['customer']}"
            if inst.get('desc'): details += f" | 📝 {inst['desc']}"
            ic2.caption(details)
            
            current_status = inst.get('status', 'Not passed Finance')
            options = ["Not passed Finance", "Passed Finance", "Kit Ordered", "Kit Arrived"]
            if current_status not in options and current_status != 'Completed': options.insert(0, current_status)
                
            new_status = ic3.select_slider("Stage", options=options, value=current_status if current_status in options else options[0], key=f"sl_inst_{inst['id']}", label_visibility="collapsed")
            if new_status != current_status and current_status in options:
                update_install_status(inst['id'], new_status)
                st.toast(f"Pipeline updated for {inst['ref']}")
                time.sleep(0.5); st.rerun()
            
            with ic4:
                btn_col1, btn_col2 = st.columns(2)
                if btn_col1.button("✅", key=f"comp_i_{inst['id']}", help="Mark as Completed"):
                    update_install_status(inst['id'], "Completed")
                    st.rerun()
                if btn_col2.button("🗑️", key=f"del_inst_{inst['id']}", help="Delete Project"):
                    if delete_record("Installs", inst['id'], inst['ref'], "job_ref"): st.rerun()
    else: st.info("No active installation projects.")

    st.divider()
    with st.expander("📦 Archived / Completed", expanded=False):
        if comp_inst:
            for inst in comp_inst:
                c1, c2, c3 = st.columns([2, 5, 1])
                c1.write(f"`{inst['ref']}`")
                c2.write(f"*{inst.get('customer', 'Unknown')}* - **Completed**")
                if c3.button("Purge", key=f"del_comp_i_{inst['id']}"):
                    if delete_record("Installs", inst['id'], inst['ref'], "job_ref"): st.rerun()
        else: st.caption("No archived records.")

# --- PAGE: CUSTOMERS ---
elif page == "👥 Customers":
    if st.session_state.selected_customer:
        cust_name = st.session_state.selected_customer
        st.title(f"🏢 {cust_name}")
        
        c_left, c_right = st.columns([5, 1])
        with c_right:
            if st.button("⬅️ Directory", type="primary", use_container_width=True):
                st.session_state.selected_customer = None
                st.rerun()
                
        c_data = next((c for c in customers if c['Name'] == cust_name), None)
        
        if c_data:
            with st.container():
                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**📍 Main Postcode:** `{c_data.get('Postcode', '-')}`")
                col1.markdown(f"**📋 Registration No:** `{c_data.get('Registration_Number', '-')}`")
                col2.markdown(f"**✉️ Email:** `{c_data.get('Email', '-')}`")
                col2.markdown(f"**📞 Phone:** `{c_data.get('Phone', '-')}`")
                col3.markdown(f"**👔 Directors:** {c_data.get('Directors', '-')}")
                col3.markdown(f"**🏢 Branches:** {c_data.get('Offices', '-')}")
                if c_data.get('Notes'):
                    st.info(f"**Notes:** {c_data.get('Notes')}")
            
            st.divider()
            st.subheader("Service Subscriptions")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("VoIP Lines", c_data.get('VoIP_Lines', 0))
            s2.metric("Handsets", c_data.get('Handsets', 0))
            s3.metric("Software Licenses", c_data.get('Software_Licenses', 0))
            s4.metric("Total Licenses", c_data.get('Total_Licenses', 0))
            
            st.divider()
            
            st.subheader("Ticket History")
            c_jobs = [j for j in jobs if j.get('customer') == cust_name]
            c_inst = [i for i in installs if i.get('customer') == cust_name]
            c_tickets = [j['ref'] for j in c_jobs] + [i['ref'] for i in c_inst]
            c_sched = [s for s in all_schedule if s.get('job_ref') in c_tickets]
            
            tab_maint, tab_inst, tab_diary = st.tabs(["Maintenance Logs", "Installation Logs", "Scheduling Events"])
            
            with tab_maint:
                if c_jobs: st.dataframe(pd.DataFrame(c_jobs)[['ref', 'status', 'desc', 'severity']], hide_index=True, use_container_width=True)
                else: st.caption("No maintenance logs.")
                
            with tab_inst:
                if c_inst: st.dataframe(pd.DataFrame(c_inst)[['ref', 'status', 'desc']], hide_index=True, use_container_width=True)
                else: st.caption("No installation logs.")
                
            with tab_diary:
                if c_sched: st.dataframe(pd.DataFrame(c_sched)[['scheduled_date', 'engineer_name', 'job_ref', 'notes']], hide_index=True, use_container_width=True)
                else: st.caption("No scheduling events attached to this account.")
        else: st.error("Account not found.")

    else:
        st.title("Customer Accounts")
        
        if customers:
            def profile_select_callback():
                val = st.session_state.profile_select_val
                if val and val != "-- Select Account --":
                    st.session_state.selected_customer = val
                    if val in st.session_state.recent_customers: st.session_state.recent_customers.remove(val)
                    st.session_state.recent_customers.insert(0, val)
                    st.session_state.recent_customers = st.session_state.recent_customers[:3]

            c1, c2 = st.columns([3, 1])
            with c1:
                cust_opts = ["-- Select Account --"] + [c['Name'] for c in customers]
                st.selectbox("Search Directory", cust_opts, key="profile_select_val", on_change=profile_select_callback)
            
            if st.session_state.recent_customers:
                st.markdown("**Recently Viewed**")
                r_cols = st.columns(3)
                for i, rc in enumerate(st.session_state.recent_customers):
                    if r_cols[i].button(f"🏢 {rc}", key=f"rec_{rc}", use_container_width=True):
                        st.session_state.selected_customer = rc
                        if rc in st.session_state.recent_customers: st.session_state.recent_customers.remove(rc)
                        st.session_state.recent_customers.insert(0, rc)
                        st.session_state.recent_customers = st.session_state.recent_customers[:3]
                        st.rerun()
            st.divider()
        
        st.subheader("🤖 AI Account Enrichment")
        st.caption("Auto-fetch corporate data using Gemini AI via Name and Postcode.")
        with st.form("ai_find_form"):
            c1, c2 = st.columns([3, 1])
            search_name = c1.text_input("Registered Entity Name")
            search_pc = c2.text_input("Primary Postcode")
            
            if st.form_submit_button("Fetch Data", type="primary"):
                if not search_name: st.warning("Please enter a business name to search.")
                else:
                    with st.spinner("Querying registry..."):
                        ai_data = fetch_company_info_ai(search_name, search_pc)
                        if ai_data:
                            st.session_state.cust_draft['name'] = search_name
                            st.session_state.cust_draft['pc'] = search_pc
                            st.session_state.cust_draft['email'] = ai_data.get('email', '')
                            st.session_state.cust_draft['phone'] = ai_data.get('phone', '')
                            st.session_state.cust_draft['directors'] = ai_data.get('directors', '')
                            st.session_state.cust_draft['reg_no'] = ai_data.get('registration_number', '')
                            st.session_state.cust_draft['offices'] = ai_data.get('offices', '')
                            st.success("Data retrieved. Please verify and save below.")
                        else: st.warning("Automated retrieval failed. Please input manually.")

        st.subheader("New Account Registration")
        with st.form("new_customer_form"):
            c1, c2 = st.columns(2)
            c_name = c1.text_input("Account Name *", value=st.session_state.cust_draft.get('name', ''))
            c_pc = c2.text_input("Main Postcode *", value=st.session_state.cust_draft.get('pc', ''))
            
            c3, c4 = st.columns(2)
            c_email = c3.text_input("Corporate Email", value=st.session_state.cust_draft.get('email', ''))
            c_phone = c4.text_input("Contact Number", value=st.session_state.cust_draft.get('phone', ''))
            
            c5, c6 = st.columns(2)
            c_directors = c5.text_input("Directors / Key Personnel", value=st.session_state.cust_draft.get('directors', ''))
            c_reg = c6.text_input("Registry Number", value=st.session_state.cust_draft.get('reg_no', ''))
            
            c_offices = st.text_area("Branch Network", value=st.session_state.cust_draft.get('offices', ''))
            
            st.markdown("##### Assigned Services")
            s1, s2, s3, s4 = st.columns(4)
            s_voip = s1.number_input("VoIP Lines", min_value=0, value=int(st.session_state.cust_draft.get('voip', 0)))
            s_handsets = s2.number_input("Handsets", min_value=0, value=int(st.session_state.cust_draft.get('handsets', 0)))
            s_soft = s3.number_input("Software Lic.", min_value=0, value=int(st.session_state.cust_draft.get('software', 0)))
            s_total = s4.number_input("Total Lic.", min_value=0, value=int(st.session_state.cust_draft.get('total_lic', 0)))

            c_notes = st.text_area("Internal Notes", value=st.session_state.cust_draft.get('notes', ''))
            
            if st.form_submit_button("Register Account", type="primary"):
                if not c_name or not c_pc: st.error("Account Name and Postcode are strictly required.")
                else:
                    try:
                        supabase.table("Customers").insert({
                            "Company_ID": st.session_state.company_id,
                            "Name": c_name, "Postcode": c_pc, "Email": c_email, "Phone": c_phone,
                            "Directors": c_directors, "Registration_Number": c_reg, "Offices": c_offices, 
                            "VoIP_Lines": s_voip, "Handsets": s_handsets, "Software_Licenses": s_soft, "Total_Licenses": s_total,
                            "Notes": c_notes
                        }).execute()
                        st.success("Account registered.")
                        st.session_state.cust_draft = {"name": "", "pc": "", "email": "", "phone": "", "directors": "", "reg_no": "", "offices": "", "notes": "", "voip": 0, "handsets": 0, "software": 0, "total_lic": 0}
                        time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Registry Error: {e}")

# --- PAGE: SCHEDULE WORK ---
elif page == "📅 Schedule Work":
    st.title("Workforce Allocation")
    eng_names = [e['name'] for e in engineers] if engineers else []
    sel_date = st.date_input("Target Date", min_value=datetime.today())
    
    col_forms, col_sched = st.columns([1, 1])
    
    with col_forms:
        st.subheader("Dispatch Orders")
        
        with st.expander("🔧 Maintenance Dispatch", expanded=True):
            with st.form("schedule_maint_form"):
                m_eng = st.selectbox("Assignee", eng_names, key="m_eng")
                maint_options = [j['ref'] for j in jobs if j.get('status') != 'Completed'] if jobs else []
                m_ref = st.selectbox("Select Ticket", maint_options, index=None, key="m_ref")
                m_notes = st.text_area("Dispatch Notes", key="m_notes")
                if st.form_submit_button("Confirm Dispatch", type="primary"):
                    if m_eng and m_ref:
                        if add_schedule_item(st.session_state.company_id, m_eng, m_ref, sel_date, m_notes, "Maintenance"):
                            st.success("Dispatch confirmed."); time.sleep(1); st.rerun()
                    else: st.warning("Requires Assignee and Ticket.")
                    
        with st.expander("🛠️ Installation Dispatch", expanded=False):
            with st.form("schedule_install_form"):
                i_eng = st.selectbox("Assignee", eng_names, key="i_eng")
                inst_options = [i['ref'] for i in installs if i.get('status') != 'Completed'] if installs else []
                i_ref = st.selectbox("Select Ticket", inst_options, index=None, key="i_ref")
                i_notes = st.text_area("Dispatch Notes", key="i_notes")
                if st.form_submit_button("Confirm Dispatch", type="primary"):
                    if i_eng and i_ref:
                        if add_schedule_item(st.session_state.company_id, i_eng, i_ref, sel_date, i_notes, "Install"):
                            st.success("Dispatch confirmed."); time.sleep(1); st.rerun()
                    else: st.warning("Requires Assignee and Ticket.")
                    
        with st.expander("📝 General Memo", expanded=False):
            with st.form("diary_note_form"):
                n_eng = st.selectbox("Recipient", ["All"] + eng_names, key="n_eng")
                n_msg = st.text_area("Memo Content")
                if st.form_submit_button("Broadcast Memo", type="primary"):
                    if n_msg:
                        target = "ALL STAFF" if n_eng == "All" else n_eng
                        add_schedule_item(st.session_state.company_id, target, "NOTE", sel_date, n_msg, "Note")
                        st.success("Memo broadcasted."); time.sleep(1); st.rerun()

    with col_sched:
        c_head, c_filt = st.columns([3, 2])
        c_head.subheader("Master Calendar")
        focus_date = c_filt.date_input("Week Origin:", value=datetime.today(), label_visibility="collapsed", key="sch_date")
        
        start_of_week = focus_date - timedelta(days=focus_date.weekday())
        
        days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        for i in range(7):
            current_day = start_of_week + timedelta(days=i)
            day_str = current_day.strftime('%Y-%m-%d')
            day_items = [item for item in all_schedule if item.get('scheduled_date') == day_str]
            
            with st.expander(f"{days_names[i]} - {current_day.strftime('%d/%m')}", expanded=(current_day == date.today() or bool(day_items))):
                if not day_items: st.caption("No events block.")
                for item in day_items:
                    note_text = str(item.get('notes', ''))
                    if "[INSTALL]" in note_text: css_class = "install"
                    elif "[NOTE]" in note_text: css_class = "note"
                    else: css_class = "job"
                    
                    content = item['job_ref']
                    if css_class == "note": content = note_text.replace("[NOTE]", "").strip()
                    
                    st.markdown(f"""
                    <div class="schedule-card {css_class}">
                        <small style="opacity: 0.7;"><b>{item['engineer_name']}</b></small><br>
                        <span style="font-size: 0.95em;">{content}</span>
                    </div>
                    """, unsafe_allow_html=True)

# --- PAGE: DATA UPLOAD ---
elif page == "⬆️ Data Upload":
    st.title("System Integration")
    
    with st.expander("🚦 Quick Admin Overrides", expanded=False):
        if engineers:
            eng_map = {e['name']: e['id'] for e in engineers}
            s_name = st.selectbox("Select Target", list(eng_map.keys()), key="se_upload")
            curr = next((e for e in engineers if e['name'] == s_name), None)
            
            stat = curr['status'] if curr else "Active"
            status_options = ["Active", "Home", "Driving", "On Site", "In Office", "Sick", "Holiday"]
            try: stat_index = status_options.index(stat)
            except: stat_index = 0 
            new_stat = st.radio("Override Status:", status_options, index=stat_index, key="se_stat")
            
            color_opts = ["blue", "green", "red", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen", "cadetblue", "darkpurple", "white", "pink", "lightblue", "lightgreen", "gray", "black", "lightgray"]
            curr_color = curr.get('pin_color')
            if curr_color: curr_color = curr_color.split()[0].lower()
            if not curr_color or curr_color not in color_opts: curr_color = "blue"
            new_color = st.selectbox("Map Pin Hash:", color_opts, index=color_opts.index(curr_color), key="se_col")
            
            if st.button("Apply Overrides", type="primary"):
                try:
                    supabase.table("Engineers").update({"status": new_stat, "pin_color": new_color}).eq("id", eng_map[s_name]).execute()
                    st.success("Override applied.")
                    time.sleep(1); st.rerun()
                except: pass
    
    st.divider()

    tab_single, tab_bulk = st.tabs(["Manual Provisioning", "Batch Ingestion (.xlsx)"])
    
    with tab_single:
        st.subheader("Provision New Personnel")
        with st.form("add_user_form"):
            c1, c2 = st.columns(2)
            u_n = c1.text_input("Full Name")
            u_p = c2.text_input("Base Postcode")
            u_color = st.selectbox("Initial Map Hash", ["blue", "green", "red", "purple", "orange", "darkred", "cadetblue"])
            if st.form_submit_button("Provision Personnel", type="primary"):
                if not u_n or not u_p: st.error("Name and Postcode mandatory.")
                else:
                    ok, m, coords = add_entry("Engineers", "Name", u_n, u_p, st.session_state.company_id, pin_color=u_color)
                    if ok: st.success("Provisioned."); time.sleep(1); st.rerun()
                    else: st.error(m)

    with tab_bulk:
        st.subheader("Batch Dataset Ingestion")
        u_file = st.file_uploader("Select structured .xlsx payload", type=['xlsx'])
        u_type = st.radio("Schema Mapping:", ["Users", "Jobs"])
        if u_file and st.button("Execute Ingestion", type="primary"):
            try:
                df = pd.read_excel(u_file)
                cols = [c.lower() for c in df.columns]
                has_name = 'name' in cols if u_type == "Users" else 'ref' in cols
                if has_name and 'postcode' in cols:
                    t_flag = "user" if u_type == "Users" else "job"
                    with st.spinner('Ingesting payload to central cluster...'):
                        cnt = process_bulk_upload(df, t_flag, st.session_state.company_id)
                    st.success(f"Ingestion complete: {cnt} vectors stored.")
                    time.sleep(1); st.rerun()
                else: st.error("Schema validation failed: Missing required columns.")
            except Exception as e: st.error(f"Ingestion Fault: {e}")
