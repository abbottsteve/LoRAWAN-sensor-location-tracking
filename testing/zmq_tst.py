# Simple ZMQ publisher on tcp://*:5556 that publishes test message every 60 seconds
# message : {'device_id': 'box1', 'battery': 2.98, 'temperature': 23, 'timestamp': '2026-04-28T07:15:08.685470885Z', 'location': {'latitude': 49.995488, 'longitude': 8.507681}, 'gw_count': 3}


import zmq
import time
import traceback

# Configuration (Ensure these match your setup)
ZMQ_ENDPOINT = "tcp://*:5555"

# ZeroMQ Setup
context = zmq.Context()
zmq_socket = context.socket(zmq.PUB)
zmq_socket.bind(ZMQ_ENDPOINT)

def main():
    # Test message
    test_data = '{box1:[{battery: 2.98, temperature: 23, latitude: 49.995488, longitude: 8.507681, gw_count: 3}]}'
    
    print(f"[ZMQ] Publisher bound to {ZMQ_ENDPOINT}")
    print(f"[ZMQ] Publishing message every 60 seconds...")

    total_sleep = 60
    interval = 0.5

    while True:
        try:
            # Send the data
            zmq_socket.send_json(test_data)
            print(f"[ZMQ] Published: {test_data}")
            
            # Reset sleep counter for each loop
            slept = 0
            while slept < total_sleep:
                time.sleep(interval)
                slept += interval
                
        except KeyboardInterrupt:
            print("\n[ZMQ] Shutting down...")
            break
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            time.sleep(1)

if __name__ == "__main__":
    main()