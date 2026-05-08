from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import json
import uuid
import sqlite3
from datetime import datetime
import asyncio
import random

app = FastAPI(title="Auralis Safety API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database Setup ──
DB_PATH = os.path.join(os.path.dirname(__file__), "auralis.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            relation TEXT DEFAULT 'Family',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS emergencies (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            severity TEXT DEFAULT 'HIGH',
            latitude REAL,
            longitude REAL,
            address TEXT,
            details TEXT,
            ai_confidence REAL DEFAULT 0.95,
            status TEXT DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'INFO',
            read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ── Models ──
class UserCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = ""

class ContactCreate(BaseModel):
    user_id: str
    name: str
    phone: str
    relation: Optional[str] = "Family"

class EmergencyAlert(BaseModel):
    user_id: str
    type: str
    severity: Optional[str] = "HIGH"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = "Unknown Location"
    details: Optional[str] = ""
    ai_confidence: Optional[float] = 0.95

class LocationUpdate(BaseModel):
    user_id: str
    latitude: float
    longitude: float

class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: Optional[str] = "INFO"

class KeywordDetection(BaseModel):
    user_id: str
    transcript: str
    confidence: Optional[float] = 0.9

# ── WebSocket Manager ──
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_notification(self, user_id: str, data: dict):
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(user_id)

    async def broadcast(self, data: dict):
        for ws in list(self.active_connections.values()):
            try:
                await ws.send_json(data)
            except Exception:
                pass

manager = ConnectionManager()

# ── Auth Endpoints ──
@app.post("/api/auth/register")
def register(user: UserCreate):
    conn = get_db()
    cur = conn.cursor()
    try:
        user_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO users (id, name, email, phone, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, user.name, user.email, user.phone, datetime.utcnow().isoformat())
        )
        conn.commit()
        return {"success": True, "user": {"id": user_id, "name": user.name, "email": user.email, "phone": user.phone}}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already registered")
    finally:
        conn.close()

@app.post("/api/auth/login")
def login(data: dict):
    email = data.get("email", "")
    conn = get_db()
    cur = conn.cursor()
    user = cur.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")
    return {"success": True, "user": dict(user)}

# ── Contact Endpoints ──
@app.get("/api/contacts/{user_id}")
def get_contacts(user_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM contacts WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/contacts")
def add_contact(contact: ContactCreate):
    conn = get_db()
    cid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO contacts (id, user_id, name, phone, relation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (cid, contact.user_id, contact.name, contact.phone, contact.relation, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return {"success": True, "contact": {"id": cid, "name": contact.name, "phone": contact.phone, "relation": contact.relation}}

@app.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: str):
    conn = get_db()
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# ── Emergency Endpoints ──
@app.post("/api/emergency/trigger")
async def trigger_emergency(alert: EmergencyAlert):
    conn = get_db()
    eid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO emergencies (id, user_id, type, severity, latitude, longitude, address, details, ai_confidence, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (eid, alert.user_id, alert.type, alert.severity, alert.latitude, alert.longitude,
         alert.address, alert.details, alert.ai_confidence, "ACTIVE", datetime.utcnow().isoformat())
    )
    conn.commit()

    # Create in-app notification
    nid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO notifications (id, user_id, title, message, type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (nid, alert.user_id, f"🚨 EMERGENCY: {alert.type}",
         f"Emergency dispatched at {alert.address or 'your location'}. Severity: {alert.severity}.",
         "EMERGENCY", datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    # Send WebSocket push notification
    await manager.send_notification(alert.user_id, {
        "type": "EMERGENCY_TRIGGERED",
        "emergency_id": eid,
        "alert_type": alert.type,
        "severity": alert.severity,
        "location": {"lat": alert.latitude, "lng": alert.longitude},
        "timestamp": datetime.utcnow().isoformat()
    })

    return {"success": True, "emergency_id": eid, "status": "DISPATCHED"}

@app.get("/api/emergency/{user_id}")
def get_emergencies(user_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM emergencies WHERE user_id = ? ORDER BY created_at DESC LIMIT 20", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.put("/api/emergency/{emergency_id}/resolve")
def resolve_emergency(emergency_id: str):
    conn = get_db()
    conn.execute("UPDATE emergencies SET status = 'RESOLVED' WHERE id = ?", (emergency_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# ── AI Detection Endpoint ──
@app.post("/api/ai/detect-keyword")
async def detect_keyword(detection: KeywordDetection):
    danger_keywords = ["help", "danger", "emergency", "save me", "call police", "fire", "attack", "hurt"]
    transcript_lower = detection.transcript.lower()
    detected = [kw for kw in danger_keywords if kw in transcript_lower]

    result = {
        "is_emergency": len(detected) > 0,
        "detected_keywords": detected,
        "ai_confidence": round(detection.confidence * (1.0 if detected else 0.1), 3),
        "recommendation": "TRIGGER_ALERT" if detected else "SAFE",
        "transcript": detection.transcript,
        "analyzed_at": datetime.utcnow().isoformat()
    }

    if detected:
        nid = str(uuid.uuid4())
        conn = get_db()
        conn.execute(
            "INSERT INTO notifications (id, user_id, title, message, type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (nid, detection.user_id, "🎙️ Voice Alert Detected",
             f"AI detected keywords: {', '.join(detected)}. Transcript: \"{detection.transcript}\"",
             "WARNING", datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

        await manager.send_notification(detection.user_id, {
            "type": "KEYWORD_DETECTED",
            "keywords": detected,
            "transcript": detection.transcript,
            "confidence": detection.confidence,
        })

    return result

# ── Notifications Endpoints ──
@app.get("/api/notifications/{user_id}")
def get_notifications(user_id: str):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.put("/api/notifications/{notification_id}/read")
def mark_read(notification_id: str):
    conn = get_db()
    conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.put("/api/notifications/{user_id}/read-all")
def mark_all_read(user_id: str):
    conn = get_db()
    conn.execute("UPDATE notifications SET read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# ── Nearby Services (Simulated) ──
@app.get("/api/nearby-services")
def get_nearby_services(lat: float = 0.0, lng: float = 0.0):
    hospitals = [
        {"id": "h1", "name": "City General Hospital", "type": "Hospital", "address": "123 Healthcare Ave", "phone": "108", "distance": f"{round(random.uniform(0.5, 3.5), 1)} km", "lat": lat + 0.01, "lng": lng + 0.01},
        {"id": "h2", "name": "St. Mary Medical Center", "type": "Hospital", "address": "456 Medical Blvd", "phone": "108", "distance": f"{round(random.uniform(0.5, 5.0), 1)} km", "lat": lat - 0.015, "lng": lng + 0.02},
        {"id": "h3", "name": "Apollo Health Clinic", "type": "Hospital", "address": "789 Wellness Rd", "phone": "108", "distance": f"{round(random.uniform(1.0, 6.0), 1)} km", "lat": lat + 0.025, "lng": lng - 0.01},
    ]
    police = [
        {"id": "p1", "name": "Central Police Station", "type": "Police", "address": "1 Law Enforcement Sq", "phone": "100", "distance": f"{round(random.uniform(0.3, 2.5), 1)} km", "lat": lat - 0.008, "lng": lng - 0.012},
        {"id": "p2", "name": "North Precinct", "type": "Police", "address": "200 Justice Drive", "phone": "100", "distance": f"{round(random.uniform(1.0, 4.0), 1)} km", "lat": lat + 0.018, "lng": lng + 0.015},
    ]
    fire = [
        {"id": "f1", "name": "Fire Station Alpha", "type": "Fire", "address": "50 Rescue Road", "phone": "101", "distance": f"{round(random.uniform(0.5, 3.0), 1)} km", "lat": lat - 0.012, "lng": lng + 0.008},
    ]
    return {"hospitals": hospitals, "police": police, "fire": fire}

# ── Stats Endpoint ──
@app.get("/api/stats/{user_id}")
def get_user_stats(user_id: str):
    conn = get_db()
    contacts_count = conn.execute("SELECT COUNT(*) FROM contacts WHERE user_id = ?", (user_id,)).fetchone()[0]
    emergencies_count = conn.execute("SELECT COUNT(*) FROM emergencies WHERE user_id = ?", (user_id,)).fetchone()[0]
    unread_notifications = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read = 0", (user_id,)).fetchone()[0]
    conn.close()
    return {
        "contacts_count": contacts_count,
        "emergencies_count": emergencies_count,
        "unread_notifications": unread_notifications,
        "safety_score": max(30, 100 - (emergencies_count * 5)),
        "status": "PROTECTED"
    }

# ── WebSocket ──
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(user_id)

# ── Serve Frontend ──
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
if os.path.isdir(frontend_path):
    @app.get("/")
    def read_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))

    @app.get("/{path:path}")
    def serve_static(path: str):
        file_path = os.path.join(frontend_path, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_path, "index.html"))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
