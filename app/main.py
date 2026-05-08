"""
Auralis - AI Safety & Emergency Response Platform
Endpoints for alert simulation and dashboard monitoring.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
from datetime import datetime
import asyncio

app = FastAPI(title="Auralis Safety Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mock Data Models ──
class LoginRequest(BaseModel):
    email: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: str

class ContactRequest(BaseModel):
    user_id: str
    name: str
    phone: str
    relation: str

class EmergencyTrigger(BaseModel):
    user_id: str
    type: str
    severity: str
    latitude: float
    longitude: float
    address: str
    details: str

class KeywordDetect(BaseModel):
    user_id: str
    transcript: str
    confidence: float

import uuid

# Simple in-memory stores
users = {}
contacts_db = []
notifications_db = []
emergencies_db = []
user_websockets = {}

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = users.get(req.email)
    if not user:
        user = {"id": f"u_{uuid.uuid4().hex[:6]}", "name": req.email.split("@")[0], "email": req.email, "phone": ""}
        users[req.email] = user
    return {"user": user}

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    user = {"id": f"u_{uuid.uuid4().hex[:6]}", "name": req.name, "email": req.email, "phone": req.phone}
    users[req.email] = user
    return {"user": user}

@app.get("/api/contacts/{user_id}")
async def get_contacts(user_id: str):
    return [c for c in contacts_db if c["user_id"] == user_id]

@app.post("/api/contacts")
async def add_contact(req: ContactRequest):
    contacts_db.append({"id": f"c_{uuid.uuid4().hex[:6]}", "user_id": req.user_id, "name": req.name, "phone": req.phone, "relation": req.relation})
    return {"status": "ok"}

@app.delete("/api/contacts/{id}")
async def delete_contact(id: str):
    global contacts_db
    contacts_db = [c for c in contacts_db if c.get("id") != id]
    return {"status": "ok"}

@app.get("/api/notifications/{user_id}")
async def get_notifications(user_id: str):
    return [n for n in notifications_db if n.get("user_id") == user_id]

@app.put("/api/notifications/{user_id}/read-all")
async def read_all_notifs(user_id: str):
    for n in notifications_db:
        if n.get("user_id") == user_id:
            n["read"] = True
    return {"status": "ok"}

@app.get("/api/stats/{user_id}")
async def get_stats(user_id: str):
    count = len([e for e in emergencies_db if e.get("user_id") == user_id])
    return {"safety_score": max(0, 100 - count * 10), "emergencies_count": count}

@app.get("/api/emergency/{user_id}")
async def get_emergencies(user_id: str):
    return [e for e in emergencies_db if e.get("user_id") == user_id]

@app.post("/api/emergency/trigger")
async def trigger_emergency(req: EmergencyTrigger):
    e = req.dict()
    e["created_at"] = datetime.utcnow().isoformat()
    e["status"] = "DISPATCHED"
    emergencies_db.append(e)
    
    # Notify user via websocket if connected
    if req.user_id in user_websockets:
        ws = user_websockets[req.user_id]
        try:
            await ws.send_text(json.dumps({"type": "EMERGENCY_TRIGGERED", "alert_type": req.type}))
        except:
            pass
    return {"status": "ok"}

@app.get("/api/nearby-services")
async def get_nearby(lat: float, lng: float):
    # Mock nearby emergency services based on current coordinates
    return {
        "hospitals": [
            {"type": "Hospital", "name": "City General Hospital", "distance": "1.2km", "address": "123 Health Ave", "phone": "555-0101", "lat": lat + 0.005, "lng": lng + 0.005}
        ],
        "police": [
            {"type": "Police", "name": "Central Police Station", "distance": "2.5km", "address": "456 Law Blvd", "phone": "555-0102", "lat": lat - 0.008, "lng": lng - 0.003}
        ],
        "fire": []
    }

@app.post("/api/ai/detect-keyword")
async def detect_keyword(req: KeywordDetect):
    txt = req.transcript.lower()
    emergency_keywords = ["help", "danger", "emergency", "save me", "fire", "police"]
    detected = [kw for kw in emergency_keywords if kw in txt]
    
    if detected:
        if req.user_id in user_websockets:
            try:
                await user_websockets[req.user_id].send_text(json.dumps({"type": "KEYWORD_DETECTED"}))
            except:
                pass
                
    return {"is_emergency": len(detected) > 0, "detected_keywords": detected}

@app.websocket("/ws/{user_id}")
async def user_websocket(websocket: WebSocket, user_id: str):
    await websocket.accept()
    user_websockets[user_id] = websocket
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if user_id in user_websockets:
            del user_websockets[user_id]


# ── Static Frontend ──
frontend_dir = os.path.abspath("./frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/{path:path}", include_in_schema=False)
    async def catch_all(path: str):
        target_path = os.path.join(frontend_dir, path)
        if os.path.exists(target_path) and os.path.isfile(target_path):
            return FileResponse(target_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))
