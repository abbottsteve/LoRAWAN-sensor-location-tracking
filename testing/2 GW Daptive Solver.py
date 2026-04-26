import json
import time
import numpy as np
from pyproj import Transformer
import paho.mqtt.client as mqtt

# --- CONFIGURATION ---
MQTT_BROKER = "eu1.cloud.thethings.network"
MQTT_USER = "fst-scm-b195-tst@ttn"
MQTT_PASS = "NNSXS.NXSXUR2AKM3DFD47EF5ZOQ4ADXLNQJ2NJ5HUWDY.XVZ4PH25CSHBRER4J4GKF47EPVL6AYXH3AJG7YIEI4MVBNG3G5VA"
TOPIC = "v3/fst-scm-b195-tst@ttn/devices/+/up"

# Settings for the solver
BASELINE_THRESHOLD_METERS = 100.0  # If GWs are closer than this, use Centroid
PATH_LOSS_EXPONENT = 3.0           # 2.0 = open space, 4.0 = thick city
SIGMA_RSSI = 5.0                   # Uncertainty factor for RSSI

# Coordinate Transformer: WGS84 (Lat/Lon) to UTM Zone 32N (Meters)
# Change 'epsg:32632' if your gateways are not in Central Europe
transformer_to_meters = Transformer.from_crs("epsg:4326", "epsg:32632", always_xy=True)
transformer_to_gps = Transformer.from_crs("epsg:32632", "epsg:4326", always_xy=True)

# Buffer to store metadata because gateways report at slightly different times
uplink_buffer = {}

def solve_weighted_centroid(gws):
    """
    Used when gateways are in the same building.
    Uses RSSI and SNR to find a 'probability center' between them.
    """
    total_w = 0
    sum_x = 0
    sum_y = 0
    
    for gw in gws:
        # Convert RSSI to linear weight. -60dBm is much stronger than -90dBm.
        # We also factor in SNR (Signal to Noise Ratio).
        weight = (10 ** (gw['rssi'] / 20)) * max(0.1, gw['snr'])
        
        sum_x += gw['x'] * weight
        sum_y += gw['y'] * weight
        total_w += weight
        
    return sum_x / total_w, sum_y / total_w

def solve_trilateration(gws):
    """
    Used when gateways are far apart. 
    Uses the RSSI distance circles to find an intersection.
    """
    # For 2 gateways, the intersection of two circles is two points.
    # We pick the one weighted closer to the gateway with the better SNR.
    x1, y1, r1 = gws[0]['x'], gws[0]['y'], 10**(((-30) - gws[0]['rssi'])/(10*PATH_LOSS_EXPONENT))
    x2, y2, r2 = gws[1]['x'], gws[1]['y'], 10**(((-30) - gws[1]['rssi'])/(10*PATH_LOSS_EXPONENT))
    
    # Simple midpoint weighting as a fallback for 2-point trilateration
    d = np.sqrt((x2-x1)**2 + (y2-y1)**2)
    a = (r1**2 - r2**2 + d**2) / (2*d)
    h = np.sqrt(max(0, r1**2 - a**2))
    
    x_point = x1 + a*(x2-x1)/d
    y_point = y1 + a*(y2-y1)/d
    
    return x_point, y_point

def process_uplink(device_id, metadata):
    if len(metadata) < 2:
        return # Need at least 2 gateways for this math

    # 1. Convert all GW coordinates to Meters
    for gw in metadata:
        loc = gw.get('location', {})
        gw['x'], gw['y'] = transformer_to_meters.transform(loc['longitude'], loc['latitude'])

    # 2. Calculate Baseline
    dist = np.sqrt((metadata[0]['x'] - metadata[1]['x'])**2 + (metadata[0]['y'] - metadata[1]['y'])**2)
    
    print(f"--- Processing {device_id} ---")
    print(f"Gateway Baseline: {dist:.2f} meters")

    # 3. Choose Logic
    if dist < BASELINE_THRESHOLD_METERS:
        print("Mode: Same Building (Weighted Centroid)")
        res_x, res_y = solve_weighted_centroid(metadata)
    else:
        print("Mode: Wide Aperture (Trilateration)")
        res_x, res_y = solve_trilateration(metadata)

    # 4. Convert back to GPS
    final_lon, final_lat = transformer_to_gps.transform(res_x, res_y)
    print(f"Result: Lat {final_lat:.6f}, Lon {final_lon:.6f}\n")

# --- MQTT CALLBACKS ---
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload)
    dev_id = payload['end_device_ids']['device_id']
    f_cnt = payload['uplink_message']['f_cnt']
    metadata = payload['uplink_message'].get('rx_metadata', [])

    # Key is DeviceID + Frame Counter to ensure we group reports of the same packet
    key = f"{dev_id}_{f_cnt}"
    
    if key not in uplink_buffer:
        uplink_buffer[key] = metadata
        # Wait 0.5s for other gateways to report before solving
        time.sleep(0.5) 
        process_uplink(dev_id, uplink_buffer[key])
        del uplink_buffer[key]

# --- START SCRIPT ---
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_message = on_message
client.connect(MQTT_BROKER, 1883, 60)
client.subscribe(TOPIC)
client.loop_forever()