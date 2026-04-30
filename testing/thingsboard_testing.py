import paho.mqtt.client as mqtt
import zmq
import json
import time
import logging

# --- Configuration ---
THINGSBOARD_HOST = "mqtt.eu.thingsboard.cloud"
THINGSBOARD_PORT = 1883
GATEWAY_TOKEN = "lRTivQoUvbtOg7ek2izU"
MQTT_TOPIC = "v1/gateway/telemetry"

ZMQ_ENDPOINT = "tcp://localhost:5555"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to ThingsBoard Gateway.")
    else:
        logging.error(f"MQTT Connection failed with code {rc}")

def main():
    # 1. Setup ZMQ Subscriber
    context = zmq.Context()
    zmq_sub = context.socket(zmq.SUB)
    zmq_sub.connect(ZMQ_ENDPOINT)
    zmq_sub.setsockopt_string(zmq.SUBSCRIBE, "") 
    logging.info(f"ZMQ Subscriber connected to {ZMQ_ENDPOINT}")

    # 2. Setup MQTT Client
    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(GATEWAY_TOKEN)
    mqtt_client.on_connect = on_connect
    
    try:
        mqtt_client.connect(THINGSBOARD_HOST, THINGSBOARD_PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as e:
        logging.error(f"MQTT Connection Error: {e}")
        return

    logging.info("Bridge started. Waiting for ZMQ messages...")

    try:
        while True:
            # 3. Receive data from ZMQ
            zmq_raw_data = zmq_sub.recv_json()
            logging.info(f"Received ZMQ data: {zmq_raw_data}")
            
            # 5. Publish to ThingsBoard
            payload_str = json.dumps(zmq_raw_data)
            mqtt_client.publish(MQTT_TOPIC, payload_str, qos=1)
            logging.info(f"Forwarded to ThingsBoard: {payload_str}")

    except KeyboardInterrupt:
        logging.info("Bridge stopping...")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        zmq_sub.close()
        context.term()
        logging.info("Bridge Offline.")

if __name__ == "__main__":
    main()