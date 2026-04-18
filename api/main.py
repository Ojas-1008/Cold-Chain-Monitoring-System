from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json

# --- SETUP ---
app = FastAPI()

# Add CORS support so our browser can talk to the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow everything for now (very beginner friendly)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# This list will keep track of everyone who is "connected" to our dashboard
# It's like a guest list for a party
connected_clients = []

# --- ENDPOINTS ---

# A simple home page just to make sure the API is running
@app.get("/")
def read_root():
    return {"message": "Cold Chain Monitoring API is running!"}

# THE BROADCAST ENDPOINT
# The subscriber will send data here using a POST request
@app.post("/broadcast")
async def receive_broadcast(data: dict):
    # Call our broadcast_data function to send this to all WebSocket clients
    await broadcast_data(data)
    return {"message": "Data broadcast successfully!"}

# THE WEBSOCKET ENDPOINT
# This is the "secret doorway" our dashboard uses to talk to the API in real-time
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 1. Accept the person's connection request
    await websocket.accept()
    
    # 2. Add them to our "connected_clients" guest list
    connected_clients.append(websocket)
    print(f"New client connected! Total clients: {len(connected_clients)}")
    
    try:
        # Keep the connection open while the client is still there
        while True:
            # We wait for any text from the client (this keeps the line open)
            data = await websocket.receive_text()
            # If we wanted to, we could do something with 'data' here
            
    except WebSocketDisconnect:
        # If the person closes their browser or leaves, remove them from the list
        connected_clients.remove(websocket)
        print(f"Client disconnected. Total clients left: {len(connected_clients)}")
    except Exception as e:
        # If any other error happens, remove them just to be safe
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"An error occurred: {e}")

# --- BROADCAST FUNCTION ---
# We will use this later to send sensor data to EVERYONE in the connected_clients list
async def broadcast_data(data_to_send: dict):
    # Convert our Python dictionary into a JSON string
    json_data = json.dumps(data_to_send)
    
    # Go through every client in our list...
    for client in connected_clients:
        try:
            # ...and send them the data!
            await client.send_text(json_data)
        except:
            # If sending fails (maybe they closed it), just ignore it for now
            pass
