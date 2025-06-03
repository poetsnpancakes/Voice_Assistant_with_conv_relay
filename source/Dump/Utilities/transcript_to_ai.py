import base64
import audioop
import json
import os
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketDisconnect
from dotenv import load_dotenv
from pyngrok import ngrok
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Start
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from model.gpt4omini import query_model
from langchain_core.output_parsers import StrOutputParser

# Load environment variables
load_dotenv()

app = FastAPI()

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.post("/call")
async def call(request: Request):
    """Handle incoming Twilio voice call."""
    form = await request.form()
    caller = form.get("From")
    print(f"📞 Incoming call from {caller}")
    
    response = VoiceResponse()
    start = Start()
    start.stream(url=f"wss://{request.headers['host']}/stream")
    response.append(start)
    response.say("This call is being transcribed.")
    response.pause(length=60)
    
    return HTMLResponse(content=str(response), status_code=200)

@app.websocket("/stream")
async def stream(websocket: WebSocket):
    await websocket.accept()
    print("📡 WebSocket connection open")

    # Create Deepgram connection for this stream
    deepgram: DeepgramClient = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
    dg_connection = deepgram.listen.websocket.v("1")

    # def on_open(self, open, **kwargs):
    #    print(f"\n\n{open}\n\n")

    # buffer to accumulate each utterance
    current_buffer = []

    def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if len(sentence) == 0:
            return
        print(f"speaker: {sentence}")
        if sentence:
        # optionally only append final results:
           if result.is_final:
            current_buffer.append(sentence)
           else:
            # for UI you might show partials,
            # but you might skip appending them to buffer
              pass

    # def on_metadata(self, metadata, **kwargs):
    #    print(f"\n\n{metadata}\n\n")

    # def on_speech_started(self, speech_started, **kwargs):
    #     print(f"\n\n{speech_started}\n\n")

    def on_utterance_end(self, utterance_end, **kwargs):
         segment = " ".join(current_buffer).strip()
         if not segment:
            return

         print(f"\n🔗 Utterance complete: {segment}\n")
        #import openai
        #  openai.api_key = os.getenv("OPENAI_API_KEY")
        #  response = openai.ChatCompletion.create(
        #    model="gpt-4o-mini",
        #    messages=[
        #   {"role": "system", "content": "You are a helpful assistant."},
        #   {"role": "user", "content": segment}
        #    ])
         response= query_model(str(segment))

            
         #reply = response.choices[0].message.content.strip()
         reply= StrOutputParser().parse(response).content.strip()
         print(f"🤖 LLM replied: {reply}\n")

         # 3) Clear buffer for next utterance
         current_buffer.clear()

    # def on_error(self, error, **kwargs):
    #     print(f"\n\n{error}\n\n")

    # def on_close(self, close, **kwargs):
    #     print(f"\n\n{close}\n\n")

    #dg_connection.on(LiveTranscriptionEvents.Open, on_open)
    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    #dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
    #dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
    #dg_connection.on(LiveTranscriptionEvents.Error, on_error)
    #dg_connection.on(LiveTranscriptionEvents.Close, on_close)

    options: LiveOptions = LiveOptions(
    model="nova-3",
    punctuate=True,
    language="en-US",
    encoding="linear16",
    channels=1,
    sample_rate=16000,
    ## To get UtteranceEnd, the following must be set:
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
                print("🔊 Streaming started")
            elif packet['event'] == 'stop':
                print("🔇 Streaming stopped")
                break
            elif packet['event'] == 'media':
                
                payload = base64.b64decode(packet['media']['payload'])

                # Convert μ-law (8kHz) → PCM 16-bit LE, 16kHz
                audio = audioop.ulaw2lin(payload, 2)
                audio = audioop.ratecv(audio, 2, 1, 8000, 16000, None)[0]

                # Send audio to Deepgram
                dg_connection.send(audio)
                

    except WebSocketDisconnect:
        print("❌ WebSocket connection closed")

    finally:
        dg_connection.finish()

# Start server and ngrok tunnel
if __name__ == "__main__":
    import uvicorn
    port = 5000
    public_url = ngrok.connect(port, bind_tls=True).public_url
    print(f"🌐 Public URL: {public_url}")

    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=f"{public_url}/call")
    print(f"📞 Waiting for calls on {number.phone_number}")

    uvicorn.run("transcript_to_ai:app", port=port)
