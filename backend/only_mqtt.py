import paho.mqtt.client as mqtt
import json
import base64

# Configuration
THE_BROKER = "eu1.cloud.thethings.network"
THE_TOPIC = "v3/abb-app@ttn/devices/+/up"
USERNAME = "abb-app@ttn"
PASSWORD = "NNSXS.WOM6WDMQTIKE6F7D4PAR6GYTQAJM4OLYOOAH4DQ.435TDOASRAJHQ553HFGGTU6AB5EWJITUOHONO4GKMQFTGJCFZNMQ"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully!")
        client.subscribe(THE_TOPIC)
    else:
        print(f"Connect failed with code {rc}")

def on_message(client, userdata, msg):
    # Parse the incoming JSON
    payload = json.loads(msg.payload.decode("utf-8"))

    print("Received MQTT message:", payload)
    
    # Access the decoded payload (if you have a JS formatter in TTN)
    # or decode the raw bytes manually
    if "decoded_payload" in payload["uplink_message"]:
        data = payload["uplink_message"]["decoded_payload"]
        print(f"Temperature: {data.get('temperature')}°C")
        print(f"Location: {data.get('location')}")

# Setup Client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USERNAME, PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

# Connect and Loop
client.connect(THE_BROKER, 1883, 60)
client.loop_forever()