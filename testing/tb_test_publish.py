# Test script to publish a message to ThingsBoard every 1 minute

import json
import time
import ssl
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

# =============================
# CONFIG
# =============================
TB_HOST = "mqtt.thingsboard.cloud"
TB_PORT = 1883
TB_GATEWAY_TOKEN = "lRTivQoUvbtOg7ek2izU"

# =============================
# MQTT Client (Gateway)
# =============================
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="tb_test_publisher")
client.username_pw_set(TB_GATEWAY_TOKEN)

if TB_PORT == 8883:
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED,
                   tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.tls_insecure_set(False)

client.connect(TB_HOST, TB_PORT, 60)
client.loop_start()

TB_CONNECT_TOPIC = "v1/gateway/connect"
TB_TELEMETRY_TOPIC = "v1/gateway/telemetry"

# =============================
# Helpers
# =============================
def iso_to_epoch_ms(iso_ts: str) -> int | None:
    if not iso_ts:
        return None

    if iso_ts.endswith("Z"):
        iso_ts = iso_ts[:-1] + "+00:00"

    if "." in iso_ts:
        h, t = iso_ts.split(".", 1)
        frac, tz = t.split("+", 1)
        frac = frac[:6].ljust(6, "0")
        iso_ts = f"{h}.{frac}+{tz}"

    dt = datetime.fromisoformat(iso_ts)
    dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)

def connect_device(device_id: str):
    payload = {
        device_id: {
            "deviceType": "tracker"
        }
    }
    client.publish(TB_CONNECT_TOPIC, json.dumps(payload), qos=1)
    print(f"[TB] Device connected: {device_id}")

def publish_telemetry(device_id: str, telemetry: dict, ts_ms: int | None):
    if ts_ms:
        payload = {
            device_id: [{
                "ts": ts_ms,
                "values": telemetry
            }]
        }
    else:
        payload = {
            device_id: telemetry
        }

    client.publish(TB_TELEMETRY_TOPIC, json.dumps(payload), qos=1)
    print(f"[TB] Telemetry sent for {device_id}")

# =============================
# Main
# =============================
def main():
    # Test message
    test_data =  {"box1": [{"values": {"battery": 2.98, "temperature": 23, "latitude": 49.995488, "longitude": 8.507681, "gw_count": 3}}]}


    
    # Connect device first
  

    print(f"[TEST] Publishing message every 60 seconds...")
    print(f"[TEST] Message: {json.dumps(test_data, indent=2)}")

    while True:
        try:
            telemetry = {
                "battery": test_data.get("battery"),
                "temperature": test_data.get("temperature"),
                "gw_count": test_data.get("gw_count"),
                "lat": test_data.get("location", {}).get("latitude"),
                "lon": test_data.get("location", {}).get("longitude")
            }

            telemetry = {k: v for k, v in telemetry.items() if v is not None}
            ts_ms = iso_to_epoch_ms(test_data.get("timestamp"))

            publish_telemetry(device_id, telemetry, ts_ms)
            
            # Wait 60 seconds before next publish
            time.sleep(60)

        except Exception as e:
            print("Error:", e)
            time.sleep(1)


if __name__ == "__main__":
    main()