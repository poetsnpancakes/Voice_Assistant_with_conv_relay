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
from twilio.twiml.voice_response import VoiceResponse, Start, Play , Connect,Stream
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from Models.gpt4omini import query_model
from langchain_core.output_parsers import StrOutputParser
import uvicorn
import aiohttp
import asyncio
import subprocess
import difflib


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



# State class to manage speaking and interruption cleanly
class TTSState:
    def __init__(self):
        self._interrupted = asyncio.Event()
        self.bot_speaking = False

    def interrupt(self):
        if not self._interrupted.is_set():
            print("⛔ Detected interruption")
            self._interrupted.set()

    def clear(self):
        self._interrupted.clear()

    def is_interrupted(self):
        return self._interrupted.is_set()

    async def wait(self):
        await self._interrupted.wait()



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
    
    stream_sid = None
    current_buffer = []
    last_sentence = ""
    state = TTSState()
    tts_task = None
    loop = asyncio.get_running_loop()
    last_assistant_reply = ""

    deepgram = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
    dg_connection = deepgram.listen.websocket.v("1")

    def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if sentence:
            print(f"🧍 Caller: {sentence}")
            current_buffer.append(sentence)
            if state.bot_speaking and not state.is_interrupted():
                state.interrupt()

    def is_echoed_response(current_segment: str, last_reply: str, threshold: float = 0.85) -> bool:
        if not current_segment or not last_reply:
           return False
        similarity = difflib.SequenceMatcher(None, current_segment.lower(), last_reply.lower()).ratio()
        return similarity >= threshold

    def on_utterance_end(self, utterance_end, **kwargs):
        nonlocal tts_task, last_sentence,last_assistant_reply  

        segment = " ".join(current_buffer).strip()
        current_buffer.clear()
        if not segment or segment == last_sentence or state.bot_speaking:
            return
        last_sentence = segment

        print(f"\n🔗 Utterance complete: {segment}\n")

        # This is where you process a complete utterance from the user
        if is_echoed_response(segment, last_assistant_reply):
           print("🛑 Skipping echoed response (likely from assistant)")
           return  # Don't send to GPT
        else:
            gpt_response = query_model(str(segment),stream_sid)
            last_assistant_reply = gpt_response
             # Proceed to ElevenLabs, TTS, etc.

        #reply = StrOutputParser().parse(query_model(segment)).content.strip()
        print(f"🤖 GPT: {gpt_response}")

        if tts_task and not tts_task.done():
            state.interrupt()
            tts_task.cancel()

        state.clear()
        state.bot_speaking = True
        tts_task = asyncio.run_coroutine_threadsafe(
            stream_audio_to_twilio(gpt_response, websocket, stream_sid, state), loop
        )

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)

    options = LiveOptions(
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
            msg = await websocket.receive_text()
            packet = json.loads(msg)

            if packet["event"] == "start":
                stream_sid = packet["start"]["streamSid"]
                print(f"🔊 Streaming started - Stream SID: {stream_sid}")
            elif packet["event"] == "stop":
                print("🔇 Streaming stopped")
                break
            elif packet["event"] == "media":
                raw = base64.b64decode(packet["media"]["payload"])
                pcm = audioop.ulaw2lin(raw, 2)
                pcm = audioop.ratecv(pcm, 2, 1, 8000, 16000, None)[0]
                print(f"📦 Received audio chunk of size {len(pcm)} bytes")
                #dg_connection.send(pcm)

    except WebSocketDisconnect:
        print("❌ WebSocket connection closed")
    finally:
        #dg_connection.finish()
        websocket.close()







async def stream_audio_to_twilio(text, websocket, stream_sid, state: TTSState):
    state.bot_speaking = True
    state.clear()
    tts_stop_event = asyncio.Event()  # 🔥 Used to stop both reader and writer

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.7, "similarity_boost": 0.75},
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
            headers=headers,
            json=payload,
        ) as response:

            if response.status != 200:
                print("❌ ElevenLabs error:", await response.text())
                return

            process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le",
                "-ac", "1", "-ar", "8000", "pipe:1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            async def reader():
                try:
                    while not response.content.at_eof():
                        if state.is_interrupted() or tts_stop_event.is_set():
                            process.terminate()
                            await process.wait()
                            break
                        chunk = await response.content.read(16)
                        if not chunk:
                            break
                        process.stdin.write(chunk)
                        #poll again before blocking drain
                        if state.is_interrupted() or tts_stop_event.is_set():
                                   process.terminate()
                                   await process.wait()
                                   break
                        await process.stdin.drain()
                    process.stdin.close()
                except Exception as e:
                    print(f"🔴 Reader error: {e}")

            async def writer():
                try:
                    while True:
                        if state.is_interrupted() or tts_stop_event.is_set():
                            process.terminate()
                            await process.wait()
                            break

                        pcm_chunk = await process.stdout.read(16)

                        # if state.is_interrupted() or tts_stop_event.is_set():
                        #     process.terminate()
                        #     await process.wait()
                        #     break
                        if not pcm_chunk:
                            break
                        mulaw_chunk = audioop.lin2ulaw(pcm_chunk, 2)
                        await websocket.send_text(json.dumps({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": base64.b64encode(mulaw_chunk).decode("ascii")
                            }
                        }))
                except Exception as e:
                    print(f"⚠️ Writer error: {e}")

            await asyncio.gather(reader(), writer(), return_exceptions=True)

            if process.returncode is None:
                process.terminate()
                await process.wait()

    state.bot_speaking = False
    state.clear()
    print("🧹 TTS stream finished.")






if __name__ == "__main__":
    
    #port = 5000 
    #public_url= ngrok.connect(port, bind_tls=True).public_url
    print(f"🌐 Public URL: {public_url}")

    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=f"{public_url}/call")
    print(f"📞 Waiting for calls on {number.phone_number}")

    uvicorn.run("temp3:app", port=port)
