from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Define the app and enable cross-origin requests
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# A list to store our active dashboard connections
connected_clients = []

@app.get("/")
def home():
    return {"status": "API is online"}

@app.post("/broadcast")
async def receive_data(data: dict):
    # Send incoming data to all connected dashboards
    for client in connected_clients:
        try:
            await client.send_json(data)
        except:
            # If a client is broken, we ignore it (the WebSocket loop handles removal)
            pass
    return {"message": "Data shared!"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    
    try:
        # Keep the connection alive until someone closes the window
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        # Clean up if someone leaves or an error occurs
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
