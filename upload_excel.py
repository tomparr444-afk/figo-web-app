import pandas as pd
from supabase import create_client, Client
from geopy.geocoders import Nominatim
import time

# --- CONFIGURATION ---
EXCEL_FILENAME = "Locations.xlsx"  # Make sure your Excel file is named this!

# ⚠️ YOUR LIVE KEYS
SUPABASE_URL = "https://sryvcuplpagtcnrnwsjz.supabase.co"
SUPABASE_KEY = "sb_publishable_sz-4L9e9jjvksF_YpJGAlw_ThCUzA7N"

# Connect to database
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error connecting to Supabase: {e}")
    exit()

def upload_from_excel(filename):
    print(f"Reading {filename}...")
    
    geolocator = Nominatim(user_agent="kartaflow_uploader_v3")
    
    try:
        df = pd.read_excel(filename)
        
        # Check for required columns
        required_cols = ['Name', 'Company_ID', 'Postcode']
        if not all(col in df.columns for col in required_cols):
            print(f"❌ Error: Missing columns. Your Excel needs: {required_cols}")
            return

        print(f"Found {len(df)} engineers. Converting postcodes to coordinates...")

        success_count = 0
        for index, row in df.iterrows():
            name = row['Name']
            postcode = row['Postcode']
            company = row['Company_ID']
            
            try:
                # 1. Convert Postcode to Lat/Lon
                print(f"   📍 Locating {name} ({postcode})...")
                location = geolocator.geocode(postcode)
                
                if location:
                    # 2. Prepare payload
                    payload = {
                        "Name": name,
                        "Company_ID": str(company),
                        "Latitude": location.latitude,
                        "Longitude": location.longitude
                    }
                    
                    # 3. Upload to Supabase
                    supabase.table("Engineers").insert(payload).execute()
                    print(f"      ✅ Uploaded!")
                    success_count += 1
                else:
                    print(f"      ⚠️ Could not find postcode: {postcode}")
                
                time.sleep(1) # Be polite to the map server
                
            except Exception as e:
                print(f"      ❌ Failed: {e}")

        print(f"--- Complete: {success_count}/{len(df)} uploaded ---")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    upload_from_excel(EXCEL_FILENAME)