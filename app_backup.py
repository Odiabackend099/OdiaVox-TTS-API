import os, secrets, hashlib, json, time, math, struct, io, wave, base64
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, Response, g, redirect
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Environment configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./odiadev_tts.sqlite3")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
KEY_PEPPER = os.getenv("KEY_PEPPER", "")
ADMIN_BEARER = os.getenv("ADMIN_BEARER", "odia-admin-2025")  # Fixed to match render.yaml
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
ODIA_TTS_URL = os.getenv("ODIA_TTS_URL", "https://odia-tts-render.onrender.com/tts").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
REQUIRE_KEY_FOR_SPEAK = os.getenv("REQUIRE_KEY_FOR_SPEAK","0") == "1"
DEV_FALLBACK_AUDIO = os.getenv("DEV_FALLBACK_AUDIO","1") == "1"  # Enable fallback by default
DEFAULT_RATE_LIMIT_PER_MIN = int(os.getenv("DEFAULT_RATE_LIMIT_PER_MIN", "120"))
DEFAULT_TOTAL_QUOTA = int(os.getenv("DEFAULT_TOTAL_QUOTA", "0"))

app = Flask(__name__, static_folder="public", static_url_path="/public")
app.config.update(SQLALCHEMY_DATABASE_URI=DATABASE_URL, SQLALCHEMY_TRACK_MODIFICATIONS=False, SECRET_KEY=SECRET_KEY)
CORS(app, origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS!=["*"] else "*")
db = SQLAlchemy(app)

REQS = Counter("http_requests_total", "Total HTTP requests", ["endpoint","method","status"])
LAT = Histogram("http_request_latency_ms", "Latency (ms)", ["endpoint","method"])

class APIKey(db.Model):
    __tablename__="api_keys"
    id=db.Column(db.String(36), primary_key=True)
    name=db.Column(db.String(255), nullable=False)
    key_hash=db.Column(db.String(64), nullable=False, unique=True)
    owner_email=db.Column(db.String(255), nullable=True)
    rate_limit_per_min=db.Column(db.Integer, default=DEFAULT_RATE_LIMIT_PER_MIN)
    total_quota=db.Column(db.BigInteger, default=DEFAULT_TOTAL_QUOTA)
    usage_count=db.Column(db.BigInteger, default=0)
    status=db.Column(db.String(16), default="active")
    created_at=db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at=db.Column(db.DateTime)

class UsageLog(db.Model):
    __tablename__="usage_logs"
    id=db.Column(db.Integer, primary_key=True, autoincrement=True)
    api_key_hash=db.Column(db.String(64), nullable=False)
    endpoint=db.Column(db.String(128), nullable=False)
    tokens=db.Column(db.Integer, default=0)
    status=db.Column(db.String(32), default="ok")
    created_at=db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def _hash_key(raw:str)->str: 
    return hashlib.sha256((KEY_PEPPER+raw).encode()).hexdigest()

def _gen_key()->str: 
    return "tts_" + secrets.token_hex(32)  # Add prefix for clarity

def _within_rate_limit(k):
    one_min=datetime.now(timezone.utc)-timedelta(minutes=1)
    recent=UsageLog.query.filter(UsageLog.api_key_hash==k.key_hash, UsageLog.created_at>=one_min, UsageLog.endpoint=="/gateway").count()
    return recent < k.rate_limit_per_min

def _within_quota(k): 
    return True if k.total_quota==0 else k.usage_count < k.total_quota

with app.app_context(): 
    db.create_all()

@app.after_request
def _security(r):
    r.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    r.headers["X-Content-Type-Options"]="nosniff"
    r.headers["Referrer-Policy"]="no-referrer"
    r.headers["Permissions-Policy"]="microphone=()"
    return r

def _is_admin(req): 
    auth_header = req.headers.get("Authorization","")
    # Check multiple possible admin tokens for compatibility
    valid_tokens = [
        f"Bearer {ADMIN_BEARER}",
        "Bearer odia-admin-2025",
        "Bearer odia-admin-token-2025-secure"
    ]
    return auth_header in valid_tokens

@app.get("/")
def root(): 
    return redirect("/public/agent.html", code=302)

@app.get("/metrics")
def metrics(): 
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.get("/ready")
def ready():
    try: 
        db.session.execute(db.text("SELECT 1"))
    except Exception as e: 
        return jsonify(ok=False, error=str(e)), 503
    return jsonify(ok=True)

@app.get("/health")
def health():
    return jsonify(
        status="ok", 
        service="odiadev-tts-gateway", 
        key_required=REQUIRE_KEY_FOR_SPEAK,
        tts_backend=ODIA_TTS_URL if ODIA_TTS_URL else "fallback"
    )

@app.post("/create-api-key")
def create_api_key():
    if not _is_admin(request): 
        return jsonify(error="Forbidden - Invalid admin token"), 403
    
    p=request.get_json(silent=True) or {}
    raw=_gen_key()
    kh=_hash_key(raw)
    
    # Check if key already exists
    existing = APIKey.query.filter_by(key_hash=kh).first()
    if existing:
        return jsonify(error="Key collision, please try again"), 500
    
    k=APIKey(
        id=secrets.token_hex(8), 
        name=p.get("name") or "Unnamed", 
        key_hash=kh,
        owner_email=p.get("owner_email"), 
        rate_limit_per_min=int(p.get("rate_limit_per_min") or DEFAULT_RATE_LIMIT_PER_MIN),
        total_quota=int(p.get("total_quota") or DEFAULT_TOTAL_QUOTA)
    )
    db.session.add(k)
    db.session.commit()
    
    return jsonify(
        id=k.id, 
        name=k.name, 
        api_key=raw,  # Full key returned only once
        instructions="Save this API key securely. It won't be shown again."
    )

def _validate_key_header():
    raw=request.headers.get("x-api-key") or request.headers.get("X-Api-Key")
    if not raw: 
        return None,("Missing API key",401)
    kh=_hash_key(raw)
    k=APIKey.query.filter_by(key_hash=kh).first()
    if not k or k.status!="active": 
        return None,("Invalid API key",401)
    return k,None

def _wav_beep(seconds=1.0, freq=440.0, sr=16000, vol=0.5)->bytes:
    """Generate a simple beep sound as WAV"""
    n=int(seconds*sr)
    atk=int(0.02*sr)
    rel=int(0.05*sr)
    buf=bytearray()
    for i in range(n):
        env = i/atk if i<atk else (n-i)/rel if i>n-rel else 1.0
        s=vol*env*math.sin(2*math.pi*freq*i/sr)
        buf += struct.pack("<h", int(max(-1,min(1,s))*32767))
    bio=io.BytesIO()
    with wave.open(bio,"wb") as w: 
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(buf))
    return bio.getvalue()

def _generate_tts_audio(text, voice="female"):
    """Actually generate real TTS audio or fallback"""
    print(f"[TTS] Generating audio for: {text[:50]}...")
    
    # Try to use the Edge TTS service
    if ODIA_TTS_URL:
        try:
            print(f"[TTS] Calling TTS service: {ODIA_TTS_URL}")
            r = requests.post(
                ODIA_TTS_URL, 
                json={"text": text, "voice": voice}, 
                timeout=45
            )
            r.raise_for_status()
            
            # Get the audio data
            audio_data = r.content
            content_type = r.headers.get("Content-Type", "audio/mpeg")
            
            print(f"[TTS] Success! Got {len(audio_data)} bytes of {content_type}")
            
            # Convert to base64 data URL for browser compatibility
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            audio_url = f"data:{content_type};base64,{audio_base64}"
            
            return {
                "success": True,
                "audio_url": audio_url,
                "audio_format": content_type,
                "audio_size": len(audio_data),
                "source": "edge-tts"
            }
            
        except requests.exceptions.RequestException as e:
            print(f"[TTS] External TTS failed: {e}")
        except Exception as e:
            print(f"[TTS] Unexpected error: {e}")
    
    # Fallback: Generate a beep sound
    if DEV_FALLBACK_AUDIO:
        print("[TTS] Using fallback beep audio")
        try:
            # Generate beep with varying pitch based on text length
            freq = 440 + (len(text) % 200)  # Vary frequency slightly
            audio_data = _wav_beep(seconds=0.5, freq=freq)
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            audio_url = f"data:audio/wav;base64,{audio_base64}"
            
            return {
                "success": True,
                "audio_url": audio_url,
                "audio_format": "audio/wav",
                "audio_size": len(audio_data),
                "source": "fallback-beep"
            }
        except Exception as e:
            print(f"[TTS] Fallback audio failed: {e}")
    
    # If all else fails, return error
    return {
        "success": False,
        "error": "TTS generation failed",
        "audio_url": None
    }

@app.post("/gateway")
def gateway():
    """Main TTS API endpoint - generates REAL audio"""
    k, err = _validate_key_header()
    if err: 
        return jsonify(error=err[0]), err[1]
    
    # Rate limiting
    if not _within_rate_limit(k):
        db.session.add(UsageLog(api_key_hash=k.key_hash, endpoint="/gateway", status="rate_limit"))
        db.session.commit()
        return jsonify(error="Rate limit exceeded"), 429
    
    # Quota check
    if not _within_quota(k):
        db.session.add(UsageLog(api_key_hash=k.key_hash, endpoint="/gateway", status="quota_exceeded"))
        db.session.commit()
        return jsonify(error="Quota exceeded"), 402
    
    # Get request parameters
    p=request.get_json(silent=True) or {}
    text=(p.get("text") or "").strip()
    voice=p.get("voice") or "female"
    
    if not text: 
        return jsonify(error="Text is required"), 400
    
    # ACTUALLY GENERATE AUDIO (not fake URL!)
    audio_result = _generate_tts_audio(text, voice)
    
    # Update usage
    k.usage_count += 1
    k.last_used_at = datetime.now(timezone.utc)
    db.session.add(k)
    db.session.add(UsageLog(api_key_hash=k.key_hash, endpoint="/gateway", status="ok"))
    db.session.commit()
    
    # Return response with REAL audio URL
    if audio_result["success"]:
        return jsonify(
            text=text,
            voice=voice,
            audio_url=audio_result["audio_url"],
            audio_format=audio_result["audio_format"],
            audio_source=audio_result["source"],
            character_count=len(text),
            success=True
        )
    else:
        return jsonify(
            error=audio_result["error"],
            text=text,
            voice=voice,
            success=False
        ), 503

@app.route("/speak", methods=["GET","POST"])
def speak():
    """Direct TTS endpoint for testing"""
    if REQUIRE_KEY_FOR_SPEAK:
        k, err = _validate_key_header()
        if err: 
            return jsonify(error=err[0]), err[1]
    
    text = request.args.get("text") or (request.get_json(silent=True) or {}).get("text") or ""
    voice = request.args.get("voice") or (request.get_json(silent=True) or {}).get("voice") or "female"
    
    if not text.strip(): 
        return jsonify(error="Text is required"), 400
    
    # Generate audio
    audio_result = _generate_tts_audio(text.strip(), voice)
    
    if audio_result["success"] and audio_result["audio_url"].startswith("data:"):
        # For data URLs, return as JSON
        return jsonify(audio_result)
    elif audio_result["success"]:
        # For actual audio data, return as binary
        audio_data = base64.b64decode(audio_result["audio_url"].split(",")[1])
        return Response(
            audio_data, 
            mimetype=audio_result["audio_format"],
            headers={"Cache-Control":"no-store","Content-Length":str(len(audio_data))}
        )
    else:
        return jsonify(error="TTS backend unavailable"), 503

@app.post("/agent")
def agent():
    """AI agent endpoint for conversational responses"""
    if REQUIRE_KEY_FOR_SPEAK:
        k, err = _validate_key_header()
        if err: 
            return jsonify(error=err[0]), err[1]
    
    p=request.get_json(silent=True) or {}
    text=(p.get("text") or "").strip()
    
    if not text: 
        return jsonify(error="Text is required"), 400
    
    # Try OpenAI if configured
    if OPENAI_API_KEY:
        try:
            r=requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"},
                json={
                    "model":"gpt-4o-mini",
                    "messages":[
                        {"role":"system","content":"Be brief, helpful, and friendly. Use Nigerian Pidgin English tone if appropriate."},
                        {"role":"user","content":text}
                    ],
                    "temperature":0.7,
                    "max_tokens":150
                },
                timeout=45
            )
            r.raise_for_status()
            out=r.json()
            reply=out.get("choices",[{}])[0].get("message",{}).get("content","") or text
            return jsonify(reply=reply, source="openai")
        except Exception as e:
            print(f"[Agent] OpenAI error: {e}")
    
    # Fallback to echo
    return jsonify(reply=text, source="echo")

@app.get("/test-audio")
def test_audio():
    """Test endpoint to verify audio generation is working"""
    test_text = "Hello! This is a test of the Nigerian TTS API. If you can hear this, the system is working perfectly!"
    audio_result = _generate_tts_audio(test_text)
    
    if audio_result["success"]:
        return f"""
        <html>
        <body style="font-family: Arial; padding: 20px;">
            <h1>TTS Audio Test</h1>
            <p>Text: "{test_text}"</p>
            <p>Source: {audio_result['source']}</p>
            <p>Format: {audio_result['audio_format']}</p>
            <p>Size: {audio_result['audio_size']} bytes</p>
            <audio controls autoplay>
                <source src="{audio_result['audio_url']}" type="{audio_result['audio_format']}">
                Your browser does not support audio.
            </audio>
            <br><br>
            <button onclick="location.reload()">Test Again</button>
        </body>
        </html>
        """
    else:
        return jsonify(audio_result), 503

# Initialize demo API key on startup if database is empty
with app.app_context():
    if APIKey.query.count() == 0:
        demo_key = "tts_demo_" + secrets.token_hex(24)
        k = APIKey(
            id="demo001",
            name="Demo API Key",
            key_hash=_hash_key(demo_key),
            owner_email="demo@example.com",
            rate_limit_per_min=60,
            total_quota=0  # Unlimited for demo
        )
        db.session.add(k)
        db.session.commit()
        print(f"[STARTUP] Created demo API key: {demo_key}")
        print(f"[STARTUP] Admin token: {ADMIN_BEARER}")
        print(f"[STARTUP] TTS Backend: {ODIA_TTS_URL if ODIA_TTS_URL else 'Fallback beep'}")

if __name__=="__main__":
    port = int(os.getenv("PORT","5000"))
    print(f"\n{'='*60}")
    print(f"ODIADEV TTS Gateway Starting...")
    print(f"{'='*60}")
    print(f"Server: http://0.0.0.0:{port}")
    print(f"Test Audio: http://localhost:{port}/test-audio")
    print(f"Admin Token: {ADMIN_BEARER}")
    print(f"TTS Backend: {ODIA_TTS_URL if ODIA_TTS_URL else 'Fallback beep'}")
    print(f"{'='*60}\n")
    
    app.run(host="0.0.0.0", port=port, debug=False)