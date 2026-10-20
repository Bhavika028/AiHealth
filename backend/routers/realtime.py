"""Authenticated per-user notification polling; no cross-patient global broadcast."""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from ..database import SessionLocal
from ..security import current_user
from ..workflow_models import Notification
router=APIRouter(prefix='/api/realtime',tags=['Notifications'])

@router.websocket('/ws')
async def websocket_endpoint(websocket:WebSocket):
    # Browser clients may send a bearer token through the subprotocol rather than the URL.
    protocols=websocket.headers.get('sec-websocket-protocol','').split(',')
    bearer=next((p.strip()[7:] for p in protocols if p.strip().startswith('bearer.')),None)
    try:
        with SessionLocal() as db: user=current_user('Bearer '+bearer if bearer else None,db);uid=user.id
    except HTTPException:
        await websocket.close(code=1008);return
    await websocket.accept(subprotocol='pulsesync' if 'pulsesync' in protocols else None)
    try:
        while True:
            with SessionLocal() as db:
                current_user('Bearer '+bearer,db)
                count=db.query(Notification).filter_by(user_id=uid,status='UNREAD').count()
            await websocket.send_json({'type':'NOTIFICATIONS','unread':count})
            await asyncio.sleep(10)
    except (WebSocketDisconnect,HTTPException,RuntimeError):
        await websocket.close()
