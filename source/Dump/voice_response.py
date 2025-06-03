import base64
import audioop
import json
import os
import requests
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketDisconnect
from dotenv import load_dotenv
from pyngrok import ngrok
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Start, Play , Connect
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from model.gpt4omini import query_model
from langchain_core.output_parsers import StrOutputParser
import uvicorn
import aiohttp
import asyncio

load_dotenv()

app = FastAPI()
global public_url
port= 5000
public_url= ngrok.connect(port, bind_tls=True).public_url

# Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ElevenLabs
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("RACHEL_VOICE_ID")

@app.post("/call")
async def call(request: Request):
    form = await request.form()
    caller = form.get("From")
    print(f"📞 Incoming call from {caller}")
    
    response = VoiceResponse()
    #start = Start()
    #start.stream(url=f"wss://{request.headers['host']}/stream")
    #response.append(start)
    response.say("You are connected to AI assistant.")
    connect = Connect()
    connect.stream(url=f"wss://{request.headers['host']}/stream")
    response.append(connect)
    #response.say(
    #'This TwiML instruction is unreachable unless the Stream is ended by your WebSocket server.')

    #response.pause(length=60)
    return HTMLResponse(content=str(response), status_code=200)

@app.websocket("/stream")
async def stream(websocket: WebSocket):
    
    await websocket.accept()
    print("📡 WebSocket connection open")
    global stream_sid

    deepgram: DeepgramClient = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
    dg_connection = deepgram.listen.websocket.v("1")

    current_buffer = []

    def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if sentence and result.is_final:
            current_buffer.append(sentence)

    def on_utterance_end(self, utterance_end, **kwargs):
        segment = " ".join(current_buffer).strip()
        if not segment:
            return

        print(f"\n🔗 Utterance complete: {segment}\n")

        # Query GPT
        gpt_response = query_model(str(segment))
        reply = StrOutputParser().parse(gpt_response).content.strip()
        print(f"🤖 GPT: {reply}")

        # Synthesize with ElevenLabs
        #audio_url = synthesize_with_elevenlabs(reply)

        # Use Twilio to play synthesized audio
        #if audio_url:
            #play_twiml_to_call(audio_url)
        # Send TTS audio back to Twilio over WebSocket
        asyncio.create_task(stream_audio_to_twilio(reply,websocket))

        current_buffer.clear()

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)

    options: LiveOptions = LiveOptions(
        model="nova-3",
        punctuate=True,
        language="en-US",
        encoding="linear16",
        channels=1,
        sample_rate=16000,
        interim_results=True,
        utterance_end_ms="1000",
        vad_events=True,
    )
    dg_connection.start(options)

    try:
        while True:
            message = await websocket.receive_text()
            packet = json.loads(message)

            if packet['event'] == 'start':
                stream_sid = packet['start']['streamSid']
                print(f"🔊 Streaming started - Stream SID: {stream_sid}")
                #print("🔊 Streaming started")
            elif packet['event'] == 'stop':
                print("🔇 Streaming stopped")
                break
            elif packet['event'] == 'media':
                payload = base64.b64decode(packet['media']['payload'])
                audio = audioop.ulaw2lin(payload, 2)
                audio = audioop.ratecv(audio, 2, 1, 8000, 16000, None)[0]
                dg_connection.send(audio)

    except WebSocketDisconnect:
        print("❌ WebSocket connection closed")
    finally:
        dg_connection.finish()




async def stream_audio_to_twilio(text: str, websocket: WebSocket):
    

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Accept": "audio/mulaw",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.7,
            "similarity_boost": 0.75
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                raw_mulaw = await response.read()
                media_message = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": base64.b64encode(raw_mulaw).decode("ascii")
                    }
                }
                if websocket:
                    await websocket.send_text(json.dumps(media_message))
                    print("🔁 Sent audio back to Twilio")
            else:
                print("❌ Error from ElevenLabs:", await response.text())


def synthesize_with_elevenlabs(text: str, websocket:WebSocket) -> str:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.7,
            "similarity_boost": 0.75
        }
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.ok:
        filepath = f"static/{text[:10].replace(' ', '_')}.mp3"
        os.makedirs("static", exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(response.content)
        return f"{public_url}/{filepath}"
    else:
        print("❌ Error synthesizing with ElevenLabs:", response.text)
        return ""


def play_twiml_to_call(audio_url: str):
    calls = twilio_client.calls.list(status="in-progress")
    for call in calls:
        twilio_client.calls(call.sid).update(
            twiml=str(VoiceResponse().play(audio_url))
        )
        print(f"🔈 Playing audio to call SID: {call.sid}")

if __name__ == "__main__":
    
    #port = 5000 
    #public_url= ngrok.connect(port, bind_tls=True).public_url
    print(f"🌐 Public URL: {public_url}")

    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=f"{public_url}/call")
    print(f"📞 Waiting for calls on {number.phone_number}")

    uvicorn.run("voice_response:app", port=port)
