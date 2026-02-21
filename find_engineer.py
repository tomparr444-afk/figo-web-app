import zipfile
import xml.etree.ElementTree as ET
from math import radians, cos, sin, asin, sqrt
import sys

# --- CONFIGURATION ---
FILENAME = "Engineers Locations(2).kmz"

def get_geolocator():
    try:
        from geopy.geocoders import Nominatim
        return Nominatim(user_agent="engineer_locator_tool_v5")
    except ImportError:
        print("CRITICAL ERROR: 'geopy' library is missing.")
        sys.exit(1)

def haversine(lon1, lat1, lon2, lat2):
    # Convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 3956 # Radius of earth in miles
    return c * r

def extract_engineers(filename):
    engineers = []
    try:
        with zipfile.ZipFile(filename, 'r') as kmz:
            kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]
            if not kml_files:
                print("Error: No KML file found inside the KMZ.")
                sys.exit(1)
            
            with kmz.open(kml_files[0], 'r') as kml_file:
                tree = ET.parse(kml_file)
                root = tree.getroot()
                
                for placemark in root.iter():
                    if placemark.tag.endswith('Placemark'):
                        name = "Unknown"
                        lat = None
                        lon = None
                        
                        for child in placemark.iter():
                            if child.tag.endswith('name'):
                                name = child.text
                            if child.tag.endswith('coordinates'):
                                parts = child.text.strip().split(',')
                                if len(parts) >= 2:
                                    lon = float(parts[0])
                                    lat = float(parts[1])
                        
                        if lat is not None and lon is not None:
                            engineers.append({'name': name, 'lat': lat, 'lon': lon})
                            
    except FileNotFoundError:
        print(f"Error: Could not find file '{filename}'.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading KMZ: {e}")
        sys.exit(1)
        
    return engineers

def main():
    print("-" * 40)
    print("   ENGINEER LOCATOR TOOL")
    print("-" * 40)
    
    geolocator = get_geolocator()
    
    print(f"Reading map data from: {FILENAME}...")
    engineers = extract_engineers(FILENAME)
    print(f"SUCCESS: Loaded {len(engineers)} engineers.")
    
    while True:
        print("\n" + "-" * 40)
        postcode = input("Enter a Postcode (or 'q' to quit): ").strip()
        
        if postcode.lower() == 'q':
            break
        
        if not postcode:
            continue

        print(f"Searching for '{postcode}'...")
        
        try:
            location = geolocator.geocode(postcode)
            
            if location is None:
                print("❌ Postcode not found. Try again.")
                continue
                
            user_lat = location.latitude
            user_lon = location.longitude
            print(f"✅ Location: {location.address}")
            
            nearest_eng = None
            min_dist = float('inf')
            
            for eng in engineers:
                dist = haversine(user_lon, user_lat, eng['lon'], eng['lat'])
                if dist < min_dist:
                    min_dist = dist
                    nearest_eng = eng
            
            if nearest_eng:
                print("\n" + "*" * 30)
                print("🎯 NEAREST ENGINEER FOUND:")
                print(f"   Name:     {nearest_eng['name']}")
                print(f"   Distance: {min_dist:.1f} miles")
                print("*" * 30)
            
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()