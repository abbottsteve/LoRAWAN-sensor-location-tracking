'''

@author: Stephen Boachie
@date: 2024-06-01
@version: 1.0

@title: LoRaWAN Geolocation - TTN Integration

@description: This module unifies the geolocation solvers into a single, cohesive pipeline.
              It establishes a secure MQTT connection to The Things Network over port 8883,
              applies adaptive multi-gateway logic for location estimation, and publishes the
              processed sensor data and computed coordinates through a ZeroMQ publisher.

              
@Key Enhancements:

    • Secure MQTT (Port 8883): TLS support added via `client.tls_set()` to ensure encrypted
    communication with The Things Network.

    • ZeroMQ Publishing: Introduces a ZMQ PUB socket that packages battery level,
    temperature, and calculated coordinates into a structured JSON payload.

    • Adaptive Solver Selection: Implements a clear `if/elif` branching model to choose the
    appropriate geolocation solver based on the number of gateways providing valid
    location metadata.

    • Unified Coordinate Processing: The 2‑gateway solver uses UTM projection for accurate
    linear distance calculations, while the 3‑gateway solver applies a simplified spherical
    approximation (111,320 m per degree) consistent with your earlier logic.

    • Sensor Payload Parsing: Adds a generalized `decoded_payload` extractor. Ensure your
    TTN Payload Formatter exposes the expected fields (`battery`, `temperature`) or adjust
    the parser to match your payload schema.

              
@Prerequisites:

These libraries need to be installed: `pip install paho-mqtt pyproj numpy scipy python-dateutil pyzmq`

'''

import json
import time
import numpy as np
import zmq
import paho.mqtt.client as mqtt
import ssl
from collections import deque
from pyproj import Transformer
from scipy.optimize import minimize
import dateutil.parser as dp

# --- CONFIGURATION ---
TTN_USERNAME = "fst-scm-b195-tst@ttn" # Replace with your actual TTN Application ID
TTN_PASSWORD = "NNSXS.NXSXUR2AKM3DFD47EF5ZOQ4ADXLNQJ2NJ5HUWDY.XVZ4PH25CSHBRER4J4GKF47EPVL6AYXH3AJG7YIEI4MVBNG3G5VA"  # Replace with your actual TTN API Key
MQTT_BROKER = "eu1.cloud.thethings.network" # TTN MQTT Broker URL
MQTT_PORT = 8883 # Secure MQTT Port
TOPIC = "v3/fst-scm-b195-tst@ttn/devices/+/up" # MQTT topic pattern to subscribe to all device uplinks in the application

# The ZeroMQ server will listen on tcp://*:5555 for incoming messages from this script and can be consumed by any ZeroMQ client (e.g., a dashboard or database ingestor) that connects to the same address.
zmq_context = zmq.Context()
zmq_socket = zmq_context.socket(zmq.PUB)
zmq_socket.bind("tcp://*:5555")

# Solver Constants and Parameters
C = 299792458.0            # Speed of light
PATH_LOSS_EXPONENT = 3.0   # For 2-GW Logic
PATH_LOSS_N = 2.5          # For 3-GW Logic
RSSI_REF = -35             # RSSI at 1m
BASELINE_THRESHOLD = 100.0 # Meters

# Coordinate Transformation (WGS84 <-> UTM Zone 32N)
to_meters = Transformer.from_crs("epsg:4326", "epsg:32632", always_xy=True)
to_gps = Transformer.from_crs("epsg:32632", "epsg:4326", always_xy=True)

# Global Buffers and State
history = {} # For Moving Average (Case 3)

# --- HELPER FUNCTIONS ---
def get_moving_average(dev_id, new_coord):
    if dev_id not in history:
        history[dev_id] = deque(maxlen=5)
    history[dev_id].append(new_coord)
    return np.mean(history[dev_id], axis=0)

def parse_toa(val):
    """Robustly parse various TOA/time formats to epoch seconds or return None."""
    if val is None:
        return None
    # numeric types (seconds / milliseconds / microseconds)
    if isinstance(val, (int, float)):
        v = float(val)
        if v > 1e14:        # microseconds
            return v / 1e6
        if v > 1e11:        # milliseconds
            return v / 1e3
        return v            # seconds
    s = str(val).strip()
    # pure digit strings -> interpret as epoch (sec/ms/us)
    if s.isdigit():
        v = float(s)
        if v > 1e14:
            return v / 1e6
        if v > 1e11:
            return v / 1e3
        return v
    # otherwise try ISO parsing
    try:
        return dp.parse(s).timestamp()
    except Exception:
        return None

# --- THE SOLVERS ---

def solve_case_1(gateways):
    """Single Gateway: Return Gateway location as estimate."""
    gw = gateways[0]['location']
    return gw['latitude'], gw['longitude']

def solve_case_2(gateways):
    """Two Gateways: Adaptive Solver (Centroid vs Trilateration)."""
    for gw in gateways:
        loc = gw['location']
        gw['x'], gw['y'] = to_meters.transform(loc['longitude'], loc['latitude'])

    dist = np.sqrt((gateways[0]['x'] - gateways[1]['x'])**2 + (gateways[1]['y'] - gateways[1]['y'])**2)

    if dist < BASELINE_THRESHOLD:
        # Weighted Centroid
        total_w = 0
        sum_x = sum_y = 0
        for gw in gateways:
            weight = (10 ** (gw['rssi'] / 20)) * max(0.1, gw['snr'])
            sum_x += gw['x'] * weight
            sum_y += gw['y'] * weight
            total_w += weight
        res_x, res_y = sum_x / total_w, sum_y / total_w
    else:
        # Trilateration
        x1, y1, r1 = gateways[0]['x'], gateways[0]['y'], 10**(((RSSI_REF) - gateways[0]['rssi'])/(10*PATH_LOSS_EXPONENT))
        x2, y2, r2 = gateways[1]['x'], gateways[1]['y'], 10**(((RSSI_REF) - gateways[1]['rssi'])/(10*PATH_LOSS_EXPONENT))
        d = np.sqrt((x2-x1)**2 + (y2-y1)**2)
        a = (r1**2 - r2**2 + d**2) / (2*d)
        res_x = x1 + a*(x2-x1)/d
        res_y = y1 + a*(y2-y1)/d

    lon, lat = to_gps.transform(res_x, res_y)
    return lat, lon

def solver_3gw_cost(coords, gateways):
    lat, lon = coords
    error = 0
    ref_gw = gateways[0]
    ref_dist = np.sqrt((lat - ref_gw['lat'])**2 + (lon - ref_gw['lon'])**2) * 111320

    for i, gw in enumerate(gateways):
        dist = np.sqrt((lat - gw['lat'])**2 + (lon - gw['lon'])**2) * 111320
        rssi_dist = 10 ** ((RSSI_REF - gw.get('rssi', RSSI_REF)) / (10 * PATH_LOSS_N))
        rssi_err = (dist - rssi_dist)**2

        tdoa_err = 0
        # check explicitly for None (0 is a valid timestamp)
        if i > 0 and (gw.get('toa') is not None) and (ref_gw.get('toa') is not None):
            time_diff = gw['toa'] - ref_gw['toa']
            tdoa_err = ((dist - ref_dist) - (time_diff * C))**2

        weight = 1.0 if gw.get('snr', -100) > -15 else 0.05
        error += weight * (0.7 * rssi_err + 0.3 * tdoa_err)
    return error

def solve_case_3(dev_id, metadata):
    """Three+ Gateways: Chan Algorithm with Robust Weighting."""
    gateways = []
    for gw in metadata:
        # safe access to location/rssi/snr
        loc = gw.get('location') or {}
        lat = loc.get('latitude')
        lon = loc.get('longitude')
        if lat is None or lon is None:
            continue
        toa_str = gw.get('timestamp') or gw.get('time') or gw.get('received_at')
        toa = parse_toa(toa_str)
        gateways.append({
            'lat': lat, 'lon': lon,
            'rssi': gw.get('rssi'), 'snr': gw.get('snr'), 'toa': toa
        })

    if not gateways:
        return None, None

    start_pos = [np.mean([g['lat'] for g in gateways]), np.mean([g['lon'] for g in gateways])]
    res = minimize(solver_3gw_cost, start_pos, args=(gateways,), method='Nelder-Mead')
    avg_coords = get_moving_average(dev_id, res.x)
    return avg_coords[0], avg_coords[1]

# --- MAIN LOGIC ---

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        dev_id = payload['end_device_ids']['device_id']
        uplink = payload.get('uplink_message', {})
        metadata = uplink.get('rx_metadata', [])

        # 1. Parse Sensor Values (Mapping depends on your Payload Formatter)
        decoded = uplink.get('decoded_payload', {})
        sensor_data = {            
            "battery": decoded.get("battery") or decoded.get("volt"),
            "temperature": decoded.get("temperature") or decoded.get("temp"),
            "timestamp": uplink.get("received_at")
        }

        # 2. Geolocation Logic
        gws_with_loc = [gw for gw in metadata if 'location' in gw]
        count = len(gws_with_loc)
        lat, lon = None, None

        if count == 1:
            lat, lon = solve_case_1(gws_with_loc)
        elif count == 2:
            lat, lon = solve_case_2(gws_with_loc)
        elif count >= 3:
            lat, lon = solve_case_3(dev_id, gws_with_loc)

        if lat and lon:
            sensor_data["location"] = {"latitude": round(lat, 6), "longitude": round(lon, 6)}
            sensor_data["gw_count"] = count

            # 3. Output to ZeroMQ

            sensor_data = {dev_id: [sensor_data]} # Wrap in device_id structure
            
            zmq_socket.send_json(sensor_data)
            print(sensor_data)

    except Exception as e:
        print(f"Error processing message: {e}")

# --- START ---
client = mqtt.Client(transport="tcp")
client.username_pw_set(TTN_USERNAME, TTN_PASSWORD)

# TLS Setup for Port 8883
client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

client.on_message = on_message
print(f"Connected to {MQTT_BROKER}...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(TOPIC)

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("Stopping...")
    zmq_socket.close()
    zmq_context.term()