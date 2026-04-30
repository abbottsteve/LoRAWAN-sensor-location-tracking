import json
import time
import ssl
import zmq
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from typing import Optional

# =============================
# CONFIG
# =============================
TB_HOST = "mqtt.thingsboard.cloud"   # or your TB host
TB_PORT = 1883                       # 8883 if TLS
TB_GATEWAY_TOKEN = "lRTivQoUvbtOg7ek2izU"

ZMQ_ENDPOINT = "tcp://localhost:5555"

# =============================
# ZeroMQ Subscriber
# =============================
zmq_context = zmq.Context()
zmq_socket = zmq_context.socket(zmq.SUB)
zmq_socket.connect(ZMQ_ENDPOINT)
zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# =============================
# MQTT Client (Gateway)
client = mqtt.Client(client_id="tb_gateway_backend")
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="tb_gateway_backend")
client.username_pw_set(TB_GATEWAY_TOKEN)

if TB_PORT == 8883:
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED,
                   tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.tls_insecure_set(False)

client.connect(TB_HOST, TB_PORT, 60)
client.loop_start()

TB_CONNECT_TOPIC = "v1/gateway/connect"
TB_TELEMETRY_TOPIC = "v1/gateway/telemetry"

connected_devices = set()

# =============================
# Helpers
# =============================
def iso_to_epoch_ms(iso_ts: str) -> Optional[int]:
    if not iso_ts:
        return None

    if iso_ts.endswith("Z"):
        iso_ts = iso_ts[:-1] + "+00:00"

    import re
    if "." in iso_ts:
        h, t = iso_ts.split(".", 1)
        tz_match = re.search(r"([+-])", t)
        if tz_match:
            sep = tz_match.group(1)
            frac, tz = t.split(sep, 1)
            frac = frac[:6].ljust(6, "0")
            iso_ts = f"{h}.{frac}{sep}{tz}"
        else:
            frac = t[:6].ljust(6, "0")
            iso_ts = f"{h}.{frac}"

    dt = datetime.fromisoformat(iso_ts)
    dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)

def connect_device(device_id: str):
    if device_id in connected_devices:
        return

    payload = {
        device_id: {
            "deviceType": "tracker"
        }
    }
    client.publish(TB_CONNECT_TOPIC, json.dumps(payload), qos=1)
    connected_devices.add(device_id)
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
            device_id: [{
                "values": telemetry
            }]
        }

    client.publish(TB_TELEMETRY_TOPIC, json.dumps(payload), qos=1)
    print(f"[TB] Telemetry sent for {device_id}")

# =============================
# Main
# =============================
def main():
    print("[ZMQ] Waiting for messages…")
    print(zmq_socket.recv_string())

    while True:
        print("[ZMQ] loop for messages…")
        try:
            msg = zmq_socket.recv_string()
            data = json.loads(msg)
            print("[ZMQ]", data)

            device_id = data.get("device_id")
            if not device_id:
                print("[ERROR] Missing device_id in message, skipping.")
                continue

            connect_device(device_id)

            telemetry = {
                "battery": data.get("battery"),
                "temperature": data.get("temperature"),
                "gw_count": data.get("gw_count"),
                "lat": data.get("location", {}).get("latitude"),
                "lon": data.get("location", {}).get("longitude")
            }

            telemetry = {k: v for k, v in telemetry.items() if v is not None}
            ts_ms = iso_to_epoch_ms(data.get("timestamp"))

        except Exception as e:
            import traceback
            print("Error:", e)
            traceback.print_exc()
            time.sleep(1)
            print("Error:", e)
            time.sleep(1)


if __name__ == "__main__":
    main()