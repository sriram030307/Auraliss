// ═══════════════ APP STATE ═══════════════
const API_BASE = `http://${window.location.host}/api`;
let currentUser = null;
let contacts = [];
let emergencies = [];
let notifications = [];
let unreadNotifsCount = 0;

// Hardware State
let map, miniMap;
let userMarker, miniUserMarker;
let userLat = 40.7128; // Default fallback
let userLng = -74.0060;
let isLocationActive = false;

// Voice AI State
let recognizer = null;
let isVoiceActive = false;

// Emergency State
let emergencyTimer = null;
let currentCountdown = 10;
let isEmergencyActive = false;
let currentEmergencyReason = "";
let websocket = null;

// ═══════════════ INITIALIZATION ═══════════════
document.addEventListener("DOMContentLoaded", () => {
  const savedUser = localStorage.getItem('auralis_user');
  if (savedUser) {
    currentUser = JSON.parse(savedUser);
    initializeApp();
  } else {
    showScreen('auth-view');
  }
});

function showScreen(screenId) {
  document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
  document.getElementById(screenId).classList.add('active');
  
  if (screenId === 'app-view' && !map) {
    setTimeout(() => {
      initMaps();
      switchTab('dashboard');
    }, 100);
  }
}

// ═══════════════ AUTH ═══════════════
function toggleAuthMode() {
  const loginForm = document.getElementById('login-form');
  const regForm = document.getElementById('register-form');
  if (loginForm.style.display === 'none') {
    loginForm.style.display = 'block';
    regForm.style.display = 'none';
  } else {
    loginForm.style.display = 'none';
    regForm.style.display = 'block';
  }
}

async function handleLogin() {
  const email = document.getElementById('login-email').value;
  if (!email) return showToast("Please enter email", "error");
  
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    
    const data = await res.json();
    if (res.ok) {
      currentUser = data.user;
      localStorage.setItem('auralis_user', JSON.stringify(currentUser));
      initializeApp();
    } else {
      showToast(data.detail || "Login failed", "error");
    }
  } catch (e) {
    showToast("Server connection error", "error");
  }
}

async function handleRegister() {
  const name = document.getElementById('reg-name').value;
  const email = document.getElementById('reg-email').value;
  const phone = document.getElementById('reg-phone').value;
  
  if (!name || !email) return showToast("Name and email required", "error");
  
  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, phone })
    });
    
    const data = await res.json();
    if (res.ok) {
      currentUser = data.user;
      localStorage.setItem('auralis_user', JSON.stringify(currentUser));
      initializeApp();
      showToast("Account created successfully", "success");
    } else {
      showToast(data.detail || "Registration failed", "error");
    }
  } catch (e) {
    showToast("Server connection error", "error");
  }
}

function logout() {
  if (!confirm("Are you sure you want to disable your Guardian Network?")) return;
  localStorage.removeItem('auralis_user');
  currentUser = null;
  if (websocket) websocket.close();
  if (recognizer && isVoiceActive) toggleVoiceMonitoring();
  showScreen('auth-view');
}

// ═══════════════ APP LIFECYCLE ═══════════════
async function initializeApp() {
  showScreen('app-view');
  
  // Populate UI with user data
  document.getElementById('sidebar-name').innerText = currentUser.name;
  document.getElementById('sidebar-avatar').innerText = currentUser.name.charAt(0).toUpperCase();
  document.getElementById('settings-name').innerText = currentUser.name;
  document.getElementById('settings-email').innerText = currentUser.email;
  document.getElementById('settings-phone').innerText = currentUser.phone || "Not provided";
  document.getElementById('settings-avatar').innerText = currentUser.name.charAt(0).toUpperCase();
  
  document.getElementById('greeting-title').innerText = `Guardian Active, ${currentUser.name.split(' ')[0]}`;

  await fetchUserData();
  connectWebSocket();
  startGPS();
  initHardwareSensors();
}

async function fetchUserData() {
  try {
    // Contacts
    const cRes = await fetch(`${API_BASE}/contacts/${currentUser.id}`);
    contacts = await cRes.json();
    renderContacts();
    document.getElementById('stat-contacts').innerText = contacts.length;
    document.getElementById('contacts-count').innerText = contacts.length;

    // Notifications
    const nRes = await fetch(`${API_BASE}/notifications/${currentUser.id}`);
    notifications = await nRes.json();
    renderNotifications();

    // Stats
    const sRes = await fetch(`${API_BASE}/stats/${currentUser.id}`);
    const stats = await sRes.json();
    document.getElementById('stat-score').innerText = stats.safety_score;
    document.getElementById('stat-emergencies').innerText = stats.emergencies_count;
    
    // Emergency History
    const eRes = await fetch(`${API_BASE}/emergency/${currentUser.id}`);
    emergencies = await eRes.json();
    renderHistory();
    
  } catch (e) {
    console.error("Data fetch error", e);
  }
}

function connectWebSocket() {
  if (websocket) websocket.close();
  
  websocket = new WebSocket(`ws://${window.location.host}/ws/${currentUser.id}`);
  
  websocket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'EMERGENCY_TRIGGERED') {
      showToast(`Emergency Alert Dispatched: ${data.alert_type}`, "error");
      fetchUserData(); // Refresh data
    } else if (data.type === 'KEYWORD_DETECTED') {
      showToast(`AI Detected Warning Keywords!`, "warning");
    }
  };
  
  websocket.onclose = () => {
    setTimeout(connectWebSocket, 5000); // Reconnect
  };
}

// ═══════════════ UI & NAVIGATION ═══════════════
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
  
  document.getElementById(`tab-${tabId}`).classList.add('active');
  document.getElementById(`nav-${tabId}`).classList.add('active');
  
  if (tabId === 'map' && map) {
    setTimeout(() => { map.invalidateSize(); fetchNearbyServices(); }, 100);
  }
  if (tabId === 'dashboard' && miniMap) {
    setTimeout(() => miniMap.invalidateSize(), 100);
  }
}

// ═══════════════ CONTACTS ═══════════════
async function addContact() {
  const name = document.getElementById('c-name').value;
  const phone = document.getElementById('c-phone').value;
  const relation = document.getElementById('c-relation').value;
  
  if (!name || !phone) return showToast("Name and phone required", "error");
  
  try {
    const res = await fetch(`${API_BASE}/contacts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id, name, phone, relation })
    });
    
    if (res.ok) {
      document.getElementById('c-name').value = '';
      document.getElementById('c-phone').value = '';
      showToast("Contact added", "success");
      fetchUserData();
    }
  } catch (e) {
    showToast("Error adding contact", "error");
  }
}

async function removeContact(id) {
  if (!confirm("Remove this contact?")) return;
  try {
    await fetch(`${API_BASE}/contacts/${id}`, { method: 'DELETE' });
    showToast("Contact removed", "info");
    fetchUserData();
  } catch (e) {
    showToast("Error removing contact", "error");
  }
}

function renderContacts() {
  const list = document.getElementById('contacts-list');
  list.innerHTML = '';
  
  if (contacts.length === 0) {
    list.innerHTML = `<p class="empty-msg">No contacts yet. Add your first trusted contact.</p>`;
    return;
  }
  
  contacts.forEach(c => {
    const el = document.createElement('div');
    el.className = 'contact-card';
    el.innerHTML = `
      <div class="contact-info">
        <strong>${c.name} <span class="contact-relation">${c.relation}</span></strong>
        <span>📞 ${c.phone}</span>
      </div>
      <button class="btn-secondary" onclick="removeContact('${c.id}')" style="color:var(--danger); border-color:var(--danger)">Remove</button>
    `;
    list.appendChild(el);
  });
}

// ═══════════════ NOTIFICATIONS & HISTORY ═══════════════
function renderNotifications() {
  const list = document.getElementById('notifications-list');
  const previewList = document.getElementById('recent-notifs-list');
  
  list.innerHTML = '';
  previewList.innerHTML = '';
  
  unreadNotifsCount = notifications.filter(n => !n.read).length;
  document.getElementById('stat-notifs').innerText = unreadNotifsCount;
  
  const badge = document.getElementById('notif-badge');
  if (unreadNotifsCount > 0) {
    badge.style.display = 'block';
    badge.innerText = unreadNotifsCount;
  } else {
    badge.style.display = 'none';
  }
  
  if (notifications.length === 0) {
    list.innerHTML = `<p class="empty-msg">No notifications yet</p>`;
    previewList.innerHTML = `<p class="empty-msg">No recent alerts</p>`;
    return;
  }
  
  notifications.forEach((n, idx) => {
    const iconClass = n.type === 'EMERGENCY' ? 'danger' : (n.type === 'WARNING' ? 'warning' : 'info');
    const iconSym = n.type === 'EMERGENCY' ? '🚨' : (n.type === 'WARNING' ? '⚠️' : 'ℹ️');
    
    const html = `
      <div class="notif-item ${!n.read ? 'unread' : ''}" style="${!n.read ? 'border-left: 3px solid var(--primary)' : ''}">
        <div class="notif-icon ${iconClass}">${iconSym}</div>
        <div class="notif-content">
          <div class="notif-title">${n.title}</div>
          <div class="notif-msg">${n.message}</div>
          <div class="notif-time">${new Date(n.created_at).toLocaleString()}</div>
        </div>
      </div>
    `;
    
    list.innerHTML += html;
    if (idx < 3) previewList.innerHTML += html;
  });
}

async function markAllRead() {
  try {
    await fetch(`${API_BASE}/notifications/${currentUser.id}/read-all`, { method: 'PUT' });
    fetchUserData();
  } catch (e) {}
}

function renderHistory() {
  const list = document.getElementById('history-list');
  list.innerHTML = '';
  
  if (emergencies.length === 0) {
    list.innerHTML = `<p class="empty-msg">No emergency history</p>`;
    return;
  }
  
  emergencies.forEach(e => {
    list.innerHTML += `
      <div class="notif-item">
        <div class="notif-icon danger">⚡</div>
        <div class="notif-content">
          <div class="notif-title">${e.type} <span style="float:right; font-size:0.8rem; background:rgba(255,255,255,0.1); padding:2px 8px; border-radius:10px;">${e.status}</span></div>
          <div class="notif-msg">Location: ${e.address || 'Unknown'}</div>
          <div class="notif-time">${new Date(e.created_at).toLocaleString()}</div>
        </div>
      </div>
    `;
  });
}

// ═══════════════ MAPS & GPS ═══════════════
function initMaps() {
  // Main Map
  map = L.map('full-map', { zoomControl: false }).setView([userLat, userLng], 14);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
  
  // Mini Map
  miniMap = L.map('mini-map', { zoomControl: false, dragging: false, scrollWheelZoom: false }).setView([userLat, userLng], 14);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(miniMap);
}

function startGPS() {
  const dots = [document.getElementById('gps-dot'), document.getElementById('gps-dot-map')];
  const texts = [document.getElementById('gps-text'), document.getElementById('gps-text-map')];
  const locDisplay = document.getElementById('countdown-location');
  
  if ("geolocation" in navigator) {
    navigator.geolocation.watchPosition((position) => {
      userLat = position.coords.latitude;
      userLng = position.coords.longitude;
      isLocationActive = true;
      
      dots.forEach(d => { if(d) { d.className = 'pulse-dot green'; }});
      texts.forEach(t => { if(t) t.innerText = 'GPS Active'; });
      if(locDisplay) locDisplay.innerText = `Lat: ${userLat.toFixed(4)}, Lng: ${userLng.toFixed(4)}`;

      // Update Markers
      const icon = L.divIcon({ className: 'my-location-marker', iconSize: [20,20], iconAnchor: [10,10]});
      
      if (!userMarker && map) {
        userMarker = L.marker([userLat, userLng], {icon}).addTo(map);
        map.setView([userLat, userLng], 15);
      } else if (userMarker) {
        userMarker.setLatLng([userLat, userLng]);
      }
      
      if (!miniUserMarker && miniMap) {
        miniUserMarker = L.marker([userLat, userLng], {icon}).addTo(miniMap);
        miniMap.setView([userLat, userLng], 14);
      } else if (miniUserMarker) {
        miniUserMarker.setLatLng([userLat, userLng]);
        miniMap.setView([userLat, userLng], 14);
      }
      
    }, (error) => {
      console.warn("GPS Error", error);
      dots.forEach(d => { if(d) d.className = 'pulse-dot red'; });
      texts.forEach(t => { if(t) t.innerText = 'No GPS Signal'; });
    }, { enableHighAccuracy: true });
  } else {
    texts.forEach(t => { if(t) t.innerText = 'No GPS Sensor'; });
  }
}

async function fetchNearbyServices() {
  if (!isLocationActive) return;
  try {
    const res = await fetch(`${API_BASE}/nearby-services?lat=${userLat}&lng=${userLng}`);
    const data = await res.json();
    
    const list = document.getElementById('nearby-list');
    list.innerHTML = '';
    
    const allServices = [...data.hospitals, ...data.police, ...data.fire];
    allServices.sort((a,b) => parseFloat(a.distance) - parseFloat(b.distance));
    
    allServices.forEach(s => {
      const typeClass = s.type.toLowerCase();
      list.innerHTML += `
        <div class="nearby-item ${typeClass}">
          <div class="nearby-header">
            <span class="nearby-name">${s.name}</span>
            <span class="nearby-dist">${s.distance}</span>
          </div>
          <div class="nearby-address">${s.address}</div>
          <div class="nearby-phone">📞 ${s.phone}</div>
        </div>
      `;
      
      // Add markers to map
      if(map) {
        const color = typeClass === 'hospital' ? 'green' : (typeClass === 'police' ? 'blue' : 'orange');
        const mIcon = L.divIcon({
          className: 'custom-icon',
          html: `<div style="background:${color};width:12px;height:12px;border-radius:50%;border:2px solid white;"></div>`,
          iconSize: [16,16]
        });
        L.marker([s.lat, s.lng], {icon: mIcon}).addTo(map).bindPopup(`<b>${s.name}</b><br>${s.phone}`);
      }
    });
  } catch (e) {
    console.error("Failed to fetch nearby services");
  }
}

// ═══════════════ VOICE AI ═══════════════
function toggleVoiceMonitoring() {
  const btn = document.getElementById('voice-toggle-btn');
  const badge = document.getElementById('voice-status-badge');
  const waveform = document.getElementById('voice-waveform');
  const display = document.getElementById('transcript-display');
  
  if (isVoiceActive) {
    if (recognizer) recognizer.stop();
    isVoiceActive = false;
    btn.innerText = "Activate";
    btn.classList.remove('active');
    badge.innerText = "Inactive";
    badge.className = "voice-status-badge";
    waveform.classList.remove('active');
    display.innerText = "—";
    showToast("Voice monitoring disabled", "info");
  } else {
    startSpeechRecognition();
  }
}

function startSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showToast("Voice recognition not supported in this browser.", "error");
    return;
  }
  
  recognizer = new SpeechRecognition();
  recognizer.continuous = true;
  recognizer.interimResults = false;
  recognizer.lang = "en-US";
  
  recognizer.onstart = () => {
    isVoiceActive = true;
    document.getElementById('voice-toggle-btn').innerText = "Deactivate";
    document.getElementById('voice-toggle-btn').classList.add('active');
    document.getElementById('voice-status-badge').innerText = "Listening";
    document.getElementById('voice-status-badge').className = "voice-status-badge active";
    document.getElementById('voice-waveform').classList.add('active');
    showToast("AI Voice Guardian Activated", "success");
  };
  
  recognizer.onresult = async (event) => {
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        const transcript = event.results[i][0].transcript.trim().toLowerCase();
        document.getElementById('transcript-display').innerText = `"${transcript}"`;
        
        // Analyze via Backend
        try {
          const res = await fetch(`${API_BASE}/ai/detect-keyword`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: currentUser.id,
              transcript: transcript,
              confidence: event.results[i][0].confidence
            })
          });
          const data = await res.json();
          
          if (data.is_emergency) {
            triggerEmergency(`AI Voice Detected: ${data.detected_keywords.join(', ')}`);
          } else if (transcript.includes("safe") && isEmergencyActive) {
            cancelEmergency();
            showToast("Emergency Cancelled via Voice Command", "success");
          }
        } catch(e) {}
      }
    }
  };
  
  recognizer.onerror = (e) => {
    console.warn("Speech error", e);
    if(e.error === 'not-allowed' || e.error === 'not-allowed-by-user') {
      showToast("Microphone access denied", "error");
      isVoiceActive = false; // Prevent onend from restarting
      document.getElementById('voice-toggle-btn').innerText = "Activate";
      document.getElementById('voice-toggle-btn').classList.remove('active');
      document.getElementById('voice-status-badge').innerText = "Inactive";
      document.getElementById('voice-status-badge').className = "voice-status-badge";
      document.getElementById('voice-waveform').classList.remove('active');
    }
  };
  
  recognizer.onend = () => {
    // Auto-restart if it shouldn't have stopped
    if (isVoiceActive) recognizer.start();
  };
  
  recognizer.start();
}

// ═══════════════ EMERGENCY FLOW ═══════════════
function triggerEmergency(reason) {
  if (isEmergencyActive) return;
  isEmergencyActive = true;
  currentEmergencyReason = reason;
  
  const modal = document.getElementById('emergency-modal');
  document.getElementById('emergency-reason').innerText = reason;
  modal.style.display = 'flex';
  
  currentCountdown = 10;
  updateCountdownUI();
  
  emergencyTimer = setInterval(() => {
    currentCountdown--;
    updateCountdownUI();
    
    if (currentCountdown <= 0) {
      clearInterval(emergencyTimer);
      executeDispatch();
    }
  }, 1000);
}

function updateCountdownUI() {
  document.getElementById('countdown-number').innerText = currentCountdown;
  document.getElementById('countdown-text').innerText = currentCountdown;
  
  // Update SVG ring
  const circle = document.getElementById('countdown-circle');
  const maxOffset = 339.292;
  circle.style.strokeDashoffset = maxOffset - (maxOffset * (currentCountdown / 10));
}

function cancelEmergency() {
  if (emergencyTimer) clearInterval(emergencyTimer);
  isEmergencyActive = false;
  document.getElementById('emergency-modal').style.display = 'none';
  showToast("Alert Cancelled", "info");
}

function sendNow() {
  if (emergencyTimer) clearInterval(emergencyTimer);
  executeDispatch();
}

async function executeDispatch() {
  document.getElementById('emergency-modal').style.display = 'none';
  isEmergencyActive = false;
  
  const payload = {
    user_id: currentUser.id,
    type: currentEmergencyReason,
    severity: "CRITICAL",
    latitude: userLat,
    longitude: userLng,
    address: `Lat: ${userLat.toFixed(4)}, Lng: ${userLng.toFixed(4)}`,
    details: "Automated dispatch triggered via Auralis system."
  };
  
  try {
    const res = await fetch(`${API_BASE}/emergency/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (res.ok) {
      showDispatchedModal(payload);
      fetchUserData(); // Refresh dashboard
    } else {
      showToast("Failed to dispatch alert", "error");
    }
  } catch (e) {
    showToast("Network error during dispatch", "error");
  }
}

function showDispatchedModal(data) {
  const modal = document.getElementById('dispatched-modal');
  const info = document.getElementById('dispatched-info');
  
  let contactsStr = contacts.length > 0 ? contacts.map(c => c.name).join(', ') : "None";
  
  info.innerHTML = `
    <p><strong>Reason:</strong> ${data.type}</p>
    <p><strong>Location:</strong> Sent to Authorities</p>
    <p><strong>Notified Contacts:</strong> ${contactsStr}</p>
  `;
  
  modal.style.display = 'flex';
}

function closeDispatchedModal() {
  document.getElementById('dispatched-modal').style.display = 'none';
}

// ═══════════════ HARDWARE SENSORS ═══════════════
let shakeCount = 0;
let lastShakeTime = 0;
let freefallDetected = false;
let freefallTime = 0;

function initHardwareSensors() {
  if (!window.DeviceMotionEvent) {
    console.warn("Device motion not supported.");
    return;
  }
  
  // Note: On some mobile browsers, DeviceMotionEvent requires user interaction (like a button click) 
  // and requesting permission first. For this demo, we bind it directly assuming permission is granted or not strictly required by the specific browser version.
  
  window.addEventListener('devicemotion', (event) => {
    if (!currentUser || isEmergencyActive) return;
    
    const acc = event.accelerationIncludingGravity;
    if (!acc) return;
    
    const x = acc.x || 0;
    const y = acc.y || 0;
    const z = acc.z || 0;
    
    // Calculate total acceleration magnitude (m/s^2)
    const magnitude = Math.sqrt(x*x + y*y + z*z);
    const now = Date.now();
    
    // 1. Fall Detection (Old people fall)
    // Free-fall threshold: magnitude drops below 3.0 m/s^2
    if (magnitude < 3.0) {
      freefallDetected = true;
      freefallTime = now;
    }
    // Impact after free-fall: magnitude spikes above 20.0 m/s^2 within 2 seconds
    if (freefallDetected && (now - freefallTime < 2000)) {
      if (magnitude > 20.0) {
        triggerEmergency("Severe Fall Detected");
        freefallDetected = false;
        return;
      }
    } else if (now - freefallTime > 2000) {
      freefallDetected = false; // Reset if impact didn't happen
    }
    
    // 2. Accident Detection (High impact collision)
    // Magnitude spikes extremely high (> 35.0 m/s^2)
    if (magnitude > 35.0) {
      triggerEmergency("Severe Accident/Impact Detected");
      return;
    }
    
    // 3. Harassment/Danger Shake Detection (Shake 3 times)
    // Strong shake (> 18.0 m/s^2)
    if (magnitude > 18.0 && magnitude <= 35.0 && !freefallDetected) {
      if (now - lastShakeTime > 500) { // 500ms cooldown between shakes
        shakeCount++;
        lastShakeTime = now;
        
        if (shakeCount >= 3) {
          triggerEmergency("Manual Shake SOS Detected");
          shakeCount = 0;
          return;
        }
      }
    }
    
    // Reset shake count if more than 4 seconds pass
    if (shakeCount > 0 && now - lastShakeTime > 4000) {
      shakeCount = 0;
    }
  });
}

// ═══════════════ TOASTS ═══════════════
function showToast(message, type = "info") {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  
  container.appendChild(toast);
  
  // Trigger animation
  setTimeout(() => toast.classList.add('show'), 10);
  
  // Remove after 3s
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
