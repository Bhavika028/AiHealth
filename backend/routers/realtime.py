"""
PulseSync AI - Real-time Notification Engine (WebSockets / Event Stream)
Dispatches live alerts for patient arrivals, ICU transfers, and pharmacy dispense notifications.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import asyncio

router = APIRouter(prefix="/api/realtime", tags=["Real-Time Engine"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                parsed = json.loads(data)
                # Broadcast received message
                await manager.broadcast(parsed)
            except Exception:
                await websocket.send_json({"type": "PONG", "message": "Heartbeat active"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@router.post("/broadcast")
async def trigger_broadcast(event: Dict[str, Any]):
    """HTTP trigger to dispatch real-time events to all connected clients."""
    await manager.broadcast(event)
    return {"status": "broadcasted", "recipients": len(manager.active_connections)}
