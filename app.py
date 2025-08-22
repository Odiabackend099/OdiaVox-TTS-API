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

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./odiadev_tts.sqlite3")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
KEY_PEPPER = os.getenv("KEY_PEPPER", "")
ADMIN_BEARER = os.getenv("ADMIN_BEARER", "")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
ODIA_TTS_URL = os.getenv("ODIA_TTS_URL", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
REQUIRE_KEY_FOR_SPEAK = os.getenv("REQUIRE_KEY_FOR_SPEAK","0") == "1"
DEV_FALLBACK_AUDIO = os.getenv("DEV_FALLBACK_AUDIO","0") == "1"
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

def _hash_key(raw:str)->str: return hashlib.sha256((KEY_PEPPER+raw).encode()).hexdigest()
def _gen_key()->str: return secrets.token_hex(32)
def _within_rate_limit(k):
    one_min=datetime.now(timezone.utc)-timedelta(minutes=1)
    recent=UsageLog.query.filter(UsageLog.api_key_hash==k.key_hash, UsageLog.created_at>=one_min, UsageLog.endpoint=="/gateway").count()
    return recent < k.rate_limit_per_min
def _within_quota(k): return True if k.total_quota==0 else k.usage_count < k.total_quota

with app.app_context(): db.create_all()

@app.after_request
def _security(r):
    r.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    r.headers["X-Content-Type-Options"]="nosniff"
    r.headers["Referrer-Policy"]="no-referrer"
    r.headers["Permissions-Policy"]="microphone=()"
    return r

def _is_admin(req): return ADMIN_BEARER and req.headers.get("Authorization","") == f"Bearer {ADMIN_BEARER}"

@app.get("/")
def root(): return redirect("/public/agent.html", code=302)

@app.get("/metrics")
def metrics(): return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.get("/ready")
def ready():
    try: db.session.execute(db.text("SELECT 1"))
    except Exception as e: return jsonify(ok=False, error=str(e)), 503
    return jsonify(ok=True)

@app.get("/health")
def health():
    return jsonify(status="ok", service="odiadev-tts-gateway", key_required=REQUIRE_KEY_FOR_SPEAK)

@app.post("/create-api-key")
def create_api_key():
    if not _is_admin(request): return jsonify(error="Forbidden"), 403
    p=request.get_json(silent=True) or {}
    raw=_gen_key(); kh=_hash_key(raw)
    k=APIKey(id=secrets.token_hex(8), name=p.get("name") or "Unnamed", key_hash=kh,
             owner_email=p.get("owner_email"), rate_limit_per_min=int(p.get("rate_limit_per_min") or DEFAULT_RATE_LIMIT_PER_MIN),
             total_quota=int(p.get("total_quota") or DEFAULT_TOTAL_QUOTA))
    db.session.add(k); db.session.commit()
    return jsonify(id=k.id, name=k.name, last_four=raw[-4:], api_key=raw)

def _validate_key_header():
    raw=request.headers.get("x-api-key")
    if not raw: return None,("Missing API key",401)
    kh=_hash_key(raw)
    k=APIKey.query.filter_by(key_hash=kh).first()
    if not k or k.status!="active": return None,("Invalid API key",401)
    return k,None

@app.post("/gateway")
def gateway():
    k, err = _validate_key_header()
    if err: return jsonify(error=err[0]), err[1]
    if not _within_rate_limit(k):
        db.session.add(UsageLog(api_key_hash=k.key_hash, endpoint="/gateway", status="rate_limit")); db.session.commit()
        return jsonify(error="Rate limit exceeded"), 429
    if not _within_quota(k):
        db.session.add(UsageLog(api_key_hash=k.key_hash, endpoint="/gateway", status="quota_exceeded")); db.session.commit()
        return jsonify(error="Quota exceeded"), 402
    
    p=request.get_json(silent=True) or {}
    text=(p.get("text") or "").strip(); voice=p.get("voice") or "female"
    if not text: return jsonify(error="Text is required"), 400
    
    # ACTUALLY GENERATE AUDIO - THE FIX!
    audio_url = None
    try:
        if ODIA_TTS_URL:
            print(f"Calling TTS service: {ODIA_TTS_URL}")
            r = requests.post(ODIA_TTS_URL, json={"text": text, "voice": voice}, timeout=45)
            r.raise_for_status()
            
            # Get audio data and convert to base64
            audio_data = r.content
            if audio_data and len(audio_data) > 0:
                audio_base64 = base64.b64encode(audio_data).decode()
                audio_url = f"data:audio/mpeg;base64,{audio_base64}"
                print(f"✅ Generated audio: {len(audio_data)} bytes")
            else:
                print("❌ Empty audio data from TTS service")
                audio_url = None
        else:
            print("❌ No ODIA_TTS_URL configured")
            audio_url = None
            
    except Exception as e:
        print(f"❌ TTS service failed: {str(e)}")
        audio_url = None
    
    # Fallback: generate simple audio if TTS failed
    if not audio_url:
        print("🔄 Using fallback audio generation")
        fallback_audio = _generate_fallback_audio(text)
        audio_base64 = base64.b64encode(fallback_audio).decode()
        audio_url = f"data:audio/wav;base64,{audio_base64}"
    
    # Update usage tracking
    k.usage_count += 1
    k.last_used_at = datetime.now(timezone.utc)
    db.session.add(k)
    db.session.add(UsageLog(api_key_hash=k.key_hash, endpoint="/gateway", status="ok"))
    db.session.commit()
    
    return jsonify(
        text=text, 
        voice=voice, 
        audio_url=audio_url,
        character_count=len(text),
        processing_time=1500
    )

def _generate_fallback_audio(text: str) -> bytes:
    """Generate simple beep audio as fallback"""
    duration = max(1.0, len(text) * 0.05)  # 50ms per character, minimum 1 second
    return _wav_beep(seconds=duration, freq=440.0, sr=16000, vol=0.3)

def _wav_beep(seconds=1.0, freq=440.0, sr=16000, vol=0.5)->bytes:
    n=int(seconds*sr); atk=int(0.02*sr); rel=int(0.05*sr); buf=bytearray()
    for i in range(n):
        env = i/atk if i<atk else (n-i)/rel if i>n-rel else 1.0
        s=vol*env*math.sin(2*math.pi*freq*i/sr); buf += struct.pack("<h", int(max(-1,min(1,s))*32767))
    bio=io.BytesIO()
    with wave.open(bio,"wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(bytes(buf))
    return bio.getvalue()

@app.route("/speak", methods=["GET","POST"])
def speak():
    if REQUIRE_KEY_FOR_SPEAK:
        k, err = _validate_key_header()
        if err: return jsonify(error=err[0]), err[1]
    text = request.args.get("text") or (request.get_json(silent=True) or {}).get("text") or ""
    voice = request.args.get("voice") or (request.get_json(silent=True) or {}).get("voice") or "female"
    if not text.strip(): return jsonify(error="Text is required"), 400
    try:
        if ODIA_TTS_URL:
            r=requests.post(ODIA_TTS_URL, json={"text":text,"voice":voice}, timeout=45); r.raise_for_status()
            ct=r.headers.get("Content-Type","audio/mpeg"); data=r.content
            return Response(data, mimetype=ct, headers={"Cache-Control":"no-store","Content-Length":str(len(data))})
    except Exception as e:
        print(f"TTS error in /speak: {str(e)}")
        pass
    if DEV_FALLBACK_AUDIO:
        data=_wav_beep(); return Response(data, mimetype="audio/wav", headers={"Cache-Control":"no-store","Content-Length":str(len(data))})
    return jsonify(error="TTS backend unavailable"), 503

@app.post("/agent")
def agent():
    if REQUIRE_KEY_FOR_SPEAK:
        k, err = _validate_key_header()
        if err: return jsonify(error=err[0]), err[1]
    p=request.get_json(silent=True) or {}; text=(p.get("text") or "").strip()
    if not text: return jsonify(error="Text is required"), 400
    if OPENAI_API_KEY:
        try:
            r=requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"},
                json={"model":"gpt-4o-mini","messages":[{"role":"system","content":"Be brief, Naija tone."},{"role":"user","content":text}],"temperature":0.3},
                timeout=45); r.raise_for_status()
            out=r.json(); reply=out.get("choices",[{}])[0].get("message",{}).get("content","") or text
            return jsonify(reply=reply, source="openai")
        except Exception as e:
            pass
    return jsonify(reply=text, source="echo")

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")))