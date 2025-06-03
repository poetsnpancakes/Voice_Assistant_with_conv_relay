from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, ConversationRelay
import os
from dotenv import load_dotenv
from pyngrok import ngrok
import uvicorn
import json
from starlette.websockets import WebSocketDisconnect
from Models.gpt4omini import query_model
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
app = FastAPI()

# Ngrok
port = 5000
public_url = ngrok.connect(port, bind_tls=True).public_url

# Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.post("/call")
async def call(request: Request):
    form = await request.form()
    caller = form.get("From")
    print(f"📞 Incoming call from {caller}")

    response = VoiceResponse()

    connect = Connect()
    convo = ConversationRelay(
        url=f"wss://{request.headers['host']}/relay",
        tts_provider="twilio",  # or "elevenlabs" if you set up with Twilio
        voice="Polly.Joanna-Neural",  # or another supported voice
        welcome_greeting="Hello, I'm your AI voice assistant. How can I help you?"
    )
    connect.append(convo)
    response.append(connect)

    return HTMLResponse(content=str(response), status_code=200)

@app.websocket("/relay")
async def relay(websocket: WebSocket):
    await websocket.accept()
    print("🔗 WebSocket relay connected")

    try:
        while True:
            message = await websocket.receive_text()
            packet = json.loads(message)

            if packet["event"] == "start":
                print(f"🎙 Conversation started")
            elif packet["event"] == "media":
                # Not needed here — Twilio handles STT
                pass
            elif packet["event"] == "transcript":
                user_text = packet["text"]
                print(f"🗣 Caller: {user_text}")

                if user_text.strip() == "":
                    continue

                # Run GPT
                gpt_response = query_model(user_text)
                reply = StrOutputParser().parse(gpt_response).content.strip()
                print(f"🤖 GPT: {reply}")

                # Send text back to Twilio for TTS
                response_packet = {
                    "event": "reply",
                    "text": reply
                }
                await websocket.send_text(json.dumps(response_packet))

            elif packet["event"] == "stop":
                print("📴 Conversation stopped")
                break

    except WebSocketDisconnect:
        print("❌ `WebSocket` disconnected")


if __name__ == "__main__":
    print(f"🌐 Public URL: {public_url}")
    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=f"{public_url}/call")
    print(f"📞 Waiting for calls on {number.phone_number}")
    uvicorn.run("relay:app", port=port)
