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
from Models.gpt4omini import query_model
from langchain_core.output_parsers import StrOutputParser
import uvicorn
import aiohttp
import asyncio
import subprocess

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
    #global interrupted
    #global bot_speaking
    global state
    loop = asyncio.get_running_loop()
    tts_task = None
    state = {
    "interrupted": asyncio.Event(),
    "bot_speaking": False
}


    deepgram: DeepgramClient = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
    dg_connection = deepgram.listen.websocket.v("1")

    current_buffer = []
    last_sentence = ""  

    def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if sentence:
          print(f"🧍 Caller: {sentence}")
          current_buffer.append(sentence)

          if state["bot_speaking"] and not state["interrupted"].is_set():
              print("⛔ Detected user-over-bot interruption, stopping bot speech…")
              state["interrupted"].set()



  


    def on_utterance_end(self, utterance_end, **kwargs):
        nonlocal tts_task, last_sentence
        segment = " ".join(current_buffer).strip()
        if not segment:
            return
        
        
        if segment == last_sentence:
            print("⚠️ Skipping duplicate utterance:", segment)
            current_buffer.clear()
            return
        last_sentence = segment  # Update after validation

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
        #asyncio.create_task(stream_audio_to_twilio(reply,websocket))
        #loop = asyncio.get_event_loop()
        

        if tts_task and not tts_task.done():
           print("⛔ Detected interruption, stopping bot speech...")
           state["interrupted"].set()
           tts_task.cancel()

           def _handle_tts_cancel(fut):
            try:
                fut.result()
            except asyncio.CancelledError:
               print("🧹 TTS task cancelled cleanly.")
            except Exception as e:
               print(f"⚠️ Exception in cancelled TTS task: {e}")

           tts_task.add_done_callback(_handle_tts_cancel)
        state["interrupted"].clear()
        state["bot_speaking"] = True
        tts_task =asyncio.run_coroutine_threadsafe(stream_audio_to_twilio(reply, websocket,state), loop)

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






async def stream_audio_to_twilio(text: str, websocket: WebSocket, state):
    # Mark that TTS is now active
    state["bot_speaking"] = True
    state["interrupted"].clear()  # reset any prior interruption

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
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
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    print("❌ ElevenLabs error:", await response.text())
                    return

                process = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le",
                    "-ac", "1", "-ar", "8000", "pipe:1",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL
                )

                async def reader():
                        try:
                            while True:
                                if state["interrupted"].is_set():
                                    process.terminate()
                                    await process.wait()
                                    return
                                chunk = await response.content.read(64)   # ← smaller chunks
                                if not chunk:
                                   break
                                process.stdin.write(chunk)
                               # poll again before blocking drain
                                if state["interrupted"].is_set():
                                   process.terminate()
                                   await process.wait()
                                   return
                                await process.stdin.drain()
                            process.stdin.close() 
                        except Exception as e:
                            print(f"🔴 Stream input error: {e}")

                async def writer():
                    try:
                        while True:
                            # 1) check *before* reading
                            if state["interrupted"].is_set():
                                process.terminate()
                                await process.wait()
                                return
                            
                            # 2) smaller read for faster polling
                            pcm_chunk = await process.stdout.read(64)

                            # 3) check *immediately* after read but before processing
                            if state["interrupted"].is_set():
                                process.terminate()
                                await process.wait()
                                return

                            if not pcm_chunk:
                                break
                            mulaw_chunk = audioop.lin2ulaw(pcm_chunk, 2)
                            media_message = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": base64.b64encode(mulaw_chunk).decode("ascii")
                                }
                            }
                            await websocket.send_text(json.dumps(media_message))
                            #await asyncio.sleep(0.02)
                    except Exception as e:
                        print(f"⚠️ Audio write error: {e}")
                    finally:
                        # make extra sure stdin is closed if writer exits first
                        try:
                            process.stdin.close()
                        except:
                            pass

                # run reader+writer but guard them from outside cancellation
                await asyncio.gather(reader(), writer(), return_exceptions=True)

        except asyncio.CancelledError:
            print("⚠️ TTS streaming task was cancelled.")
            state["interrupted"].set()

        finally:
            # clean up ffmpeg and mark TTS as done
            print("🧹 Cleaning up TTS stream")
            try:
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
            except:
                pass

            # now bot is no longer speaking
            state["bot_speaking"] = False
            state["interrupted"].clear()






if __name__ == "__main__":
    
    #port = 5000 
    #public_url= ngrok.connect(port, bind_tls=True).public_url
    print(f"🌐 Public URL: {public_url}")

    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=f"{public_url}/call")
    print(f"📞 Waiting for calls on {number.phone_number}")

    uvicorn.run("temp2:app", port=port)
