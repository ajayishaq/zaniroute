from flask import Flask, render_template, request, jsonify
import requests
from math import radians, cos, sin, asin, sqrt
import os

app = Flask(__name__)

# API Keys
TOMTOM_API_KEY = 'WZs47YSTQtzJjBIXKkbdV0U0pbOHg3cd'
OPEN_CHARGE_API_KEY = '87e356c0-2256-49b4-adf8-509e040551ea'

def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance between two coordinates"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of Earth in kilometers
    return c * r

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_stations():
    """Search for fuel and EV stations"""
    try:
        data = request.json
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
        radius = int(data.get('radius', 10000))
        station_type = data.get('type', 'all')

        stations = []

        # Search fuel stations
        if station_type in ['all', 'gas']:
            fuel_stations = search_fuel_stations(lat, lng, radius)
            stations.extend(fuel_stations)

        # Search EV stations
        if station_type in ['all', 'ev']:
            ev_stations = search_ev_stations(lat, lng, radius)
            stations.extend(ev_stations)

        # Sort by distance
        for station in stations:
            station['distance'] = haversine(lng, lat, station['lng'], station['lat'])

        stations.sort(key=lambda x: x['distance'])
        return jsonify({'success': True, 'stations': stations[:30]})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/geocode', methods=['POST'])
def geocode_location():
    """Geocode a location string"""
    try:
        location = request.json.get('location', '').strip()
        if not location:
            return jsonify({'success': False, 'error': 'No location provided'}), 400

        url = f'https://api.tomtom.com/search/2/geocode/{location}.json'
        params = {'key': TOMTOM_API_KEY, 'limit': 1}
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if not data.get('results'):
            return jsonify({'success': False, 'error': 'Location not found'}), 404

        result = data['results'][0]
        return jsonify({
            'success': True,
            'lat': result['position']['lat'],
            'lng': result['position']['lon'],
            'address': result.get('address', {}).get('freeformAddress', 'Unknown')
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def search_fuel_stations(lat, lng, radius):
    """Search TomTom for fuel stations"""
    try:
        url = f'https://api.tomtom.com/search/2/poiSearch/gas%20station.json'
        params = {
            'key': TOMTOM_API_KEY,
            'lat': lat,
            'lon': lng,
            'radius': min(radius, 50000),
            'limit': 50
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        stations = []
        for result in data.get('results', []):
            stations.append({
                'id': result.get('id'),
                'name': result.get('poi', {}).get('name') or result.get('address', {}).get('freeformAddress', 'Gas Station'),
                'lat': result['position']['lat'],
                'lng': result['position']['lon'],
                'type': 'gas',
                'address': result.get('address', {}).get('freeformAddress', 'Unknown location'),
                'distance': 0
            })

        return stations
    except Exception as e:
        print(f'Error searching fuel stations: {e}')
        return []

def search_ev_stations(lat, lng, radius):
    """Search OpenChargeMap for EV charging stations"""
    try:
        url = 'https://api.openchargemap.org/v3/poi/'
        params = {
            'key': OPEN_CHARGE_API_KEY,
            'latitude': lat,
            'longitude': lng,
            'distance': max(1, radius // 1000),
            'maxresults': 50
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json() or []

        stations = []
        for result in data:
            if result.get('AddressInfo', {}).get('Latitude') and result.get('AddressInfo', {}).get('Longitude'):
                stations.append({
                    'id': result.get('ID'),
                    'name': result.get('AddressInfo', {}).get('Title', 'EV Charging Station'),
                    'lat': result['AddressInfo']['Latitude'],
                    'lng': result['AddressInfo']['Longitude'],
                    'type': 'ev',
                    'address': result.get('AddressInfo', {}).get('AddressLine1', 'Unknown location'),
                    'distance': 0
                })

        return stations
    except Exception as e:
        print(f'Error searching EV stations: {e}')
        return []

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
