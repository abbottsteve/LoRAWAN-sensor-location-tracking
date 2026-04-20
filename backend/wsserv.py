import asyncio
import websockets
import json
from datetime import datetime

import zmq

connected_clients = set()
# Initialize ZeroMQ context and subscriber socket once
zmq_context = zmq.Context()
zmq_socket = zmq_context.socket(zmq.SUB)
zmq_socket.connect("tcp://localhost:5555")
zmq_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# build the zmq subscriber tcp://localhost:5555" to get data from mqtt_ttn.py
def build_payload():
    message = zmq_socket.recv_string()
    data = json.loads(message)
    print("Received from ZeroMQ:", data)
    return data



async def handler(websocket):
    connected_clients.add(websocket)
    print("Client connected")

    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        print("Client disconnected")

async def broadcast_loop():
    while True:
        if connected_clients:
            payload_data = await asyncio.to_thread(build_payload)
            payload = json.dumps(payload_data)

            # FIX: wrap each send coroutine in a Task
            tasks = [asyncio.create_task(ws.send(payload)) for ws in connected_clients]

            # Wait for all sends to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            print("Sent:", payload)

        await asyncio.sleep(2)
    print("Starting WebSocket server on ws://localhost:8080")
    server = await websockets.serve(handler, "localhost", 8080)

    await broadcast_loop()

async def main():
    print("Starting WebSocket server on ws://localhost:8080")
    server = await websockets.serve(handler, "localhost", 8080)
    await broadcast_loop()

if __name__ == "__main__":
    asyncio.run(main())
