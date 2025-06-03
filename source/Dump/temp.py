import os
import json
import base64
import audioop
import threading
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response
from starlette.websockets import WebSocketDisconnect
from dotenv import load_dotenv
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from pyngrok import ngrok
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Start


load_dotenv()

# Load Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Init FastAPI
app = FastAPI()

# Create Deepgram client
dg_client = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))

@app.post("/call")
async def handle_call(request: Request):
    """Twilio hits this endpoint on incoming call"""
    form = await request.form()
    print(f"Incoming call from {form['From']}")

    response = VoiceResponse()
    start = Start()
    start.stream(url=f"wss://{request.headers['host']}/stream")
    response.append(start)
    response.say("You are now being recorded.")
    response.pause(length=60)
    return Response(content=str(response), media_type="text/xml")

@app.websocket("/stream")
async def stream_audio(websocket: WebSocket):
    """Handle audio stream from Twilio and send to Deepgram"""
    await websocket.accept()

    # Setup Deepgram connection
    dg_connection = dg_client.listen.websocket.v("1")

    def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if sentence:
            print("Transcript:", sentence)

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

    options = LiveOptions(model="nova-3", interim_results=True, language="en-US")
    dg_connection.start(options)

    try:
        while True:
            message = await websocket.receive_text()
            packet = json.loads(message)

            if packet['event'] == 'start':
                print("Streaming started")
            elif packet['event'] == 'stop':
                print("Streaming stopped")
                break
            elif packet['event'] == 'media':
                print("Received media packet")
                #print("Payload size:", len(packet['media']['payload']))
                # Convert Twilio μ-law → 16-bit PCM → 16kHz
                try:
                   audio = base64.b64decode(packet['media']['payload'])
                   audio = audioop.ulaw2lin(audio, 2)
                   audio = audioop.ratecv(audio, 2, 1, 8000, 16000, None)[0]
                   dg_connection.send(audio)
                except Exception as e:
                    print(f"Error processing audio: {e}")
    except WebSocketDisconnect:
        print("WebSocket disconnected.")
    finally:
        dg_connection.finish()

def start_ngrok():
    public_url = ngrok.connect(5000, bind_tls=True).public_url
    print(f"Public URL: {public_url}")
    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=public_url + "/call")
    print(f"Waiting for calls on {number.phone_number}")

# Run ngrok and start app
if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=start_ngrok).start()
    uvicorn.run("transcript:app", host="localhost", port=5000)
