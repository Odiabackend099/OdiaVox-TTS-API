cd "$HOME\odiadev-tts-api"

# Create the fixed server that accepts BOTH GET and POST
@"
import asyncio, os
from flask import Flask, request, Response, jsonify
import edge_tts

app = Flask(__name__)
F = os.getenv("ODIADEV_VOICE_FEMALE","en-US-JennyNeural")
M = os.getenv("ODIADEV_VOICE_MALE","en-US-GuyNeural")

async def synth(text, voice):
    audio=b""
    com=edge_tts.Communicate(text, voice=voice, rate="+0%")
    async for chunk in com.stream():
        if chunk["type"]=="audio": audio+=chunk["data"]
    return audio

@app.route("/tts", methods=["GET", "POST"])
def tts():
    p = request.get_json(silent=True) or {}
    text = (p.get("text") or request.args.get("text") or "").strip()
    v    = (p.get("voice") or request.args.get("voice") or "female").lower()
    if not text: return jsonify(error="text required"), 400
    voice = F if v.startswith("f") else M
    data = asyncio.run(synth(text, voice))
    return Response(data, mimetype="audio/mpeg", headers={"Cache-Control":"no-store"})

if __name__=="__main__":
    print("TTS: http://127.0.0.1:5051/tts (GET and POST supported)")
    app.run(host="127.0.0.1", port=5051, debug=False)
"@ | Out-File -FilePath "edge_tts_server.py" -Encoding UTF8