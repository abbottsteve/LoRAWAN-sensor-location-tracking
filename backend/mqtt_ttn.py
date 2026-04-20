import json
import ssl
import base64
import paho.mqtt.client as mqtt

import zmq
import json


# -----------------------------
# TTN MQTT CONFIG
# -----------------------------
MQTT_SERVER = "eu1.cloud.thethings.network"
MQTT_PORT = 8883
MQTT_UserName = "abb-app@ttn"
APP_ID = "abb-app@ttn"
API_KEY = "NNSXS.WOM6WDMQTIKE6F7D4PAR6GYTQAJM4OLYOOAH4DQ.435TDOASRAJHQ553HFGGTU6AB5EWJITUOHONO4GKMQFTGJCFZNMQ"

MQTT_TOPIC = "v3/abb-app@ttn/devices/+/up"

# -----------------------------
# FORMAT TTN MESSAGE
# -----------------------------
def format_ttn_message(payload: dict) -> dict:
    uplink = payload.get("uplink_message", {})

    # Extract decoded temperature
    Raw_data = uplink.get("frm_payload", {})
    temp_raw = int((base64.b64decode(Raw_data).hex()), 16)

    calibrated_temp = None
    if temp_raw is not None:
        calibrated_temp = float(temp_raw/100000) - 7.0  # recalibration
        calibrated_temp = float(f"{calibrated_temp:.0f}")

    # Extract gateway metadata
    rx_list = uplink.get("rx_metadata", [])
    rx = rx_list[0] if rx_list else {}

    gateway_ids = rx.get("gateway_ids", {})
    location = rx.get("location", {})

    device_ids = payload.get("end_device_ids", {})

    return {
        "device_id": device_ids.get("device_id"),
        #"application_id": device_ids.get("application_ids", {}).get("application_id"),
        "temperature": calibrated_temp,
        "map_location": {
            #"gateway_id": gateway_ids.get("gateway_id"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "altitude": location.get("altitude"),
        },
        "received_at": uplink.get("received_at") or payload.get("received_at"),
    }


# -----------------------------
# MQTT CALLBACKS
# -----------------------------
def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected to TTN MQTT:", rc)
    client.subscribe(MQTT_TOPIC)
    print("Subscribed to:", MQTT_TOPIC)


# Create ZeroMQ context and PUB socket globally
zmq_context = zmq.Context()
zmq_socket = zmq_context.socket(zmq.PUB)
zmq_socket.bind("tcp://*:5555")

def on_message(client, userdata, msg):
    """
    Callback function for MQTT when a message is received.

    Args:
        client: The MQTT client instance.
        userdata: The private user data as set in Client() or userdata_set().
        msg: An instance of MQTTMessage, which contains topic, payload, qos, retain.
    """
    try:
        raw = msg.payload.decode("utf-8")
        data = json.loads(raw)
        formatted = format_ttn_message(data)

        # Publish to ZeroMQ (socket is already bound)
        zmq_socket.send_string(json.dumps(formatted))
        print("Published to ZeroMQ:", formatted)

    except Exception as e:
        print("Error parsing MQTT message:", e)
        return


# -----------------------------
# START MQTT CLIENT
# -----------------------------
def main():
    try:
        #client = mqtt.Client(client_id="", protocol=mqtt.MQTTv5)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="")

        client.username_pw_set(MQTT_UserName, API_KEY)

        # Enable TLS
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        client.tls_insecure_set(False)

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(MQTT_SERVER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    finally:
        zmq_socket.close()
        zmq_context.term()


if __name__ == "__main__":
    main()

