import asyncio
import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from starlette.responses import HTMLResponse
from contextlib import suppress
from Models.gpt4omini import query_model
from pyngrok import ngrok
from twilio.rest import Client
import uvicorn
from twilio.twiml.voice_response import VoiceResponse, Start, Play , Connect,Stream, ConversationRelay
from Services.bot_query import query_rephrase




load_dotenv()

app = FastAPI()
global public_url
global call_sid
port= 5000
public_url= ngrok.connect(port, bind_tls=True).public_url

# Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)




@app.post("/call")
async def call(request: Request):
    global call_sid
    form = await request.form()
    caller = form.get("From")
    print(f"📞 Incoming call from {caller}")
    call_sid = form.get("CallSid")

    response = VoiceResponse()
    connect = Connect()
    conversationrelay = ConversationRelay(
    url=f"wss://{request.headers['host']}/stream",
    welcome_greeting='You are connected to AI assistant. How can I help you?',)
    conversationrelay.language(
    code='en-US', tts_provider='ElevenLabs', voice='21m00Tcm4TlvDq8ikWAM')
    connect.append(conversationrelay)
    response.append(connect)

    return HTMLResponse(content=str(response), status_code=200)


@app.websocket("/stream")
async def stream(websocket: WebSocket):

        await websocket.accept()
        queue = asyncio.queues.Queue()
        global call_sid
        

        async def reader():
           async for msg in websocket.iter_json():
              print(f"📝 Incoming message: {msg}")
              await queue.put(msg)


        async def processor():
          buffer   = []
          llm_task = None

          async def cancel_llm():
            nonlocal llm_task
            if llm_task:
                llm_task.cancel()
                with suppress(asyncio.CancelledError):
                    await llm_task
                llm_task = None

          while True:
            data = await queue.get()
            if data["type"] == "prompt":
                buffer.append(data["voicePrompt"])
                if data.get("last", False):
                    message = " ".join(buffer)
                    buffer = []
                    await cancel_llm()
                    async def run_and_print():
                       response = await query_rephrase(str(message), call_sid)
                       #print(f"🤖 AI Response: {response.content}")
                       print(f"🤖 AI Response: {response}")
                       #await websocket.send_json({"type": "text", "token": response.content})
                       await websocket.send_json({"type": "text", "token": response})
                    llm_task = asyncio.create_task(run_and_print())

            elif data["type"] == "interrupt":
                buffer = []
                await cancel_llm()

    # run both coroutines until the socket closes
        await asyncio.gather(reader(), processor())



if __name__ == "__main__":
    
    #port = 5000 
    #public_url= ngrok.connect(port, bind_tls=True).public_url
    print(f"🌐 Public URL: {public_url}")

    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=f"{public_url}/call")
    print(f"📞 Waiting for calls on {number.phone_number}")

    uvicorn.run("bento:app", port=port)



