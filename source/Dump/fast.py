import os
import json
import base64
import audioop
import asyncio

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Start
from twilio.rest import Client as TwilioClient
from deepgram import DeepgramClient, ClientOptionsFromEnv
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()
PUBLIC_URL = os.getenv("PUBLIC_URL")

parsed = urlparse(PUBLIC_URL)
HOST = parsed.netloc

# Twilio setup
twilio = TwilioClient(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

# Deepgram v3+ client
dg = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))

app = FastAPI()

CL = "\x1b[0K"
BS = "\x08"

@app.post("/call")
async def call(request: Request):
    form = await request.form()
    resp = VoiceResponse()
    resp.append(Start().stream(url=f"wss://{HOST}/stream"))
    resp.say("Please leave a message.")
    resp.pause(length=60)
    print(f"Incoming call from {form['From']}")
    return PlainTextResponse(str(resp), media_type="text/xml")

@app.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    print("🛰  WebSocket accepted")

    # open Deepgram live socket
    try:
        async with dg.transcription.live({
            "punctuate": True,
            "interim_results": True,
            "language": "en-US"
        }) as live_source:

            print("🛰  Connected to Deepgram")

            # task: read Twilio → Deepgram
            async def forward_twilio():
                try:
                    while True:
                        msg = await ws.receive_text()
                        pkt = json.loads(msg)
                        ev  = pkt.get("event")
                        if ev == "media":
                            raw   = base64.b64decode(pkt["media"]["payload"])
                            lin16 = audioop.ulaw2lin(raw, 2)
                            pcm16 = audioop.ratecv(lin16, 2, 1, 8000, 16000, None)[0]
                            live_source.send(pcm16)
                        elif ev == "start":
                            print("⏺️  Twilio stream started")
                        elif ev == "stop":
                            print("🛑  Twilio stream stopped")
                            break
                except WebSocketDisconnect:
                    pass

            forward_task = asyncio.create_task(forward_twilio())

            # consume transcripts
            async for evt in live_source:
                alt  = evt["channel"]["alternatives"][0]
                text = alt.get("transcript", "")
                if not text:
                    continue

                if evt.get("is_final", False):
                    print(CL + text + "\n", end="")
                else:
                    print(CL + text, end="", flush=True)

            forward_task.cancel()

    except Exception as e:
        print("❌ Stream error:", e)
    finally:
        await ws.close()
        print("🔒 WebSocket closed")

if __name__ == "__main__":
    import uvicorn
    # update your Twilio number's webhook
    # (if you’re auto‐tunneling, capture your public URL here)
    public_url = os.getenv("PUBLIC_URL")  # or hardcode your ngrok URL
    number = twilio.incoming_phone_numbers.list()[0]
    number.update(voice_url=public_url + "/call")
    print("Waiting for calls on", number.phone_number)
    uvicorn.run(app, host="0.0.0.0", port=5000)
