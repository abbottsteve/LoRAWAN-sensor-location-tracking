import paho.mqtt.client as mqtt
import json
import base64
import ssl
import sys

THE_BROKER = "eu1.cloud.thethings.network"
THE_TOPIC = "v3/fst-scm-b195-tst@ttn/devices/+/up"
USERNAME = "fst-scm-b195-tst@ttn"
PASSWORD = "NNSXS.NXSXUR2AKM3DFD47EF5ZOQ4ADXLNQJ2NJ5HUWDY.XVZ4PH25CSHBRER4J4GKF47EPVL6AYXH3AJG7YIEI4MVBNG3G5VA"

def fmt_temp(val):
    try:
        v = float(val)
        # if device reports hundredths (common) convert to degrees
        if abs(v) > 500:  # likely raw integer (e.g. 2350 -> 23.50°C)
            return f"{v/100:.2f} °C"
        return f"{v:.2f} °C"
    except Exception:
        return str(val)

def fmt_batt(val):
    try:
        v = float(val)
        if v > 1000:  # millivolts -> volts
            return f"{v/1000:.3f} V"
        if 0 <= v <= 100:  # percentage
            return f"{v:.0f} %"
        return f"{v:.2f}"
    except Exception:
        return str(val)

def parse_and_print(msg_payload, topic):
    # payload is TTN V3 uplink JSON
    device = None
    try:
        device = msg_payload.get("end_device_ids", {}).get("device_id")
    except Exception:
        device = None

    uplink = msg_payload.get("uplink_message") or msg_payload  # handle raw variations

    # Try decoded payload first
    decoded = uplink.get("decoded_payload")
    temp = None
    batt = None
    if isinstance(decoded, dict):
        # common field names
        for tname in ("temperature", "temp", "t"):
            if tname in decoded:
                temp = decoded[tname]
                break
        for bname in ("battery", "bat", "vbat", "battery_mv", "battery_mV"):
            if bname in decoded:
                batt = decoded[bname]
                break

    # If no decoded payload, try raw frm_payload (base64)
    if temp is None and batt is None:
        frm = uplink.get("frm_payload")
        if frm:
            try:
                raw = base64.b64decode(frm)
                # print raw hex for debugging
                raw_hex = raw.hex()
            except Exception:
                raw_hex = None
        else:
            raw_hex = None

    print("==== UPLINK ====")
    if device:
        print(f"Device: {device}")
    if temp is not None:
        print("Temperature:", fmt_temp(temp))
    if batt is not None:
        print("Battery:", fmt_batt(batt))
    if temp is None and batt is None:
        if raw_hex:
            print("Raw payload (hex):", raw_hex)
        else:
            print("No decoded payload present.")

    # Gateways / rx metadata
    rx = uplink.get("rx_metadata") or msg_payload.get("rx_metadata") or []
    try:
        gw_count = len(rx)
    except Exception:
        gw_count = 0
    print(f"Gateways seen: {gw_count}")
    for i, g in enumerate(rx):
        gw_id = (g.get("gateway_ids") or {}).get("gateway_id") or g.get("gateway_id")
        rssi = g.get("rssi")
        snr = g.get("snr") or g.get("signal_strength")  # fallback names
        loc = g.get("location") or {}
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        print(f"  - gateway #{i+1}: id={gw_id}")
        if rssi is not None:
            print(f"      RSSI: {rssi} dBm")
        if snr is not None:
            print(f"      SNR: {snr}")
        if lat is not None and lon is not None:
            print(f"      Location: {lat}, {lon}")
        elif loc:
            # maybe alt or accuracy present
            print(f"      Location metadata: {loc}")
    print("================\n")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker, subscribing to topic:", THE_TOPIC)
        client.subscribe(THE_TOPIC)
    else:
        print("Connection failed with rc=", rc)
        sys.exit(1)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception as e:
        print("Failed to decode JSON payload:", e)
        return
    parse_and_print(payload, msg.topic)

def main():
    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)
    # use system CA certs for TLS
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(THE_BROKER, 8883, 60)
    except Exception as e:
        print("Connect error:", e)
        sys.exit(1)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Interrupted, disconnecting...")
        client.disconnect()

if __name__ == "__main__":
    main()

