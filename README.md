# ODIADEV TTS Gateway (Render-ready)

Backend: Flask + SQLAlchemy + CORS + Prometheus metrics.  
Frontend: lightweight HTML tester at `/public/agent.html` (saves `x-api-key` locally).  
Default engine calls your Render app: **GET https://odia-tts-render.onrender.com/speak?text=...**

## Quick Start (Windows PowerShell)
```powershell
Expand-Archive .\odiadev-tts-api__v0.3.1.zip -DestinationPath .\odiadev-tts-api -Force
cd .\odiadev-tts-api
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# set ADMIN_BEARER in .env, then:
python app.py
```
Open http://localhost:5000 → paste an API key → Play last → Send.

### Create an API key (admin only)
```powershell
$resp = Invoke-RestMethod 'http://127.0.0.1:5000/create-api-key' -Method Post `
  -Headers @{ Authorization = 'Bearer <ADMIN_BEARER>' } -ContentType 'application/json' `
  -Body '{"name":"Local UI"}'
$resp.api_key
```

## Render variables
```
SECRET_KEY, KEY_PEPPER, ADMIN_BEARER
ALLOWED_ORIGINS=https://<your-ui>,http://localhost:5000
DATABASE_URL=postgres://... (recommended)
ODIA_TTS_URL=https://odia-tts-render.onrender.com/speak
ODIA_TTS_METHOD=GET
ODIA_TTS_TEXT_PARAM=text
ODIA_TTS_VOICE_PARAM=voice
REQUIRE_KEY_FOR_SPEAK=1
DEV_FALLBACK_AUDIO=0
```
