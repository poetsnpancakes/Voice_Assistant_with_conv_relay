# import os
# import json
# import base64
# import audioop
# import asyncio

# from flask import Flask, request
# from flask_sock import Sock
# from twilio.twiml.voice_response import VoiceResponse, Start
# from twilio.rest import Client
# from deepgram import DeepgramClient, ClientOptionsFromEnv      # <<<<< updated import
# from dotenv import load_dotenv
# from pyngrok import ngrok

# load_dotenv()

# # Twilio setup (unchanged)…
# twilio_client = Client(os.getenv('TWILIO_ACCOUNT_SID'),
#                        os.getenv('TWILIO_AUTH_TOKEN'))



# dg_client = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))

# #dg_client = deepgram.listen.live.v("1")



# app = Flask(__name__)
# sock = Sock(app)

# # Console-control codes (unchanged)
# CL = '\x1b[0K'
# BS = '\x08'

# @app.route('/call', methods=['POST'])
# def call():
#     response = VoiceResponse()
#     start = Start().stream(url=f"wss://{request.host}/stream")
#     response.append(start)
#     response.say('Please leave a message.')
#     response.pause(length=60)
#     print(f"Incoming call from {request.form['From']}")
#     return str(response), 200, {'Content-Type': 'text/xml'}

# @sock.route('/stream')
# async def stream(ws):
#     try:
#         deepgram: DeepgramClient = DeepgramClient()
#         dg_connection = deepgram.listen.websocket.v("1")
# 		# define callbacks for transcription messages
#         def on_message(self, result, **kwargs):
#             sentence = result.channel.alternatives[0].transcript
#             if len(sentence) == 0:
#                return
#             print(f"speaker: {sentence}")
#         dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
#     # connect to websocket
#     options = LiveOptions(model="nova-3", interim_results=False, language="en-US")
#     dg_connection.start(options)
#     lock_exit = threading.Lock()
#     exit = False
#     # define a worker thread
#     def myThread():
#       with httpx.stream("GET", URL) as r:
#         for data in r.iter_bytes():
#           lock_exit.acquire()
#           if exit:
#             	break
#           lock_exit.release()
#           dg_connection.send(data)
#     # start the worker thread
#     myHttp = threading.Thread(target=myThread)
#     myHttp.start()
#     # signal finished
#     input("Press Enter to stop recording...\n\n")
#     lock_exit.acquire()
#     exit = True
#     lock_exit.release()
#     # Wait for the HTTP thread to close and join
#     myHttp.join()
#     # Indicate that we've finished
#     dg_connection.finish()


#     # 2) Register transcript handlers up front
#     def print_transcript(evt):
#         txt = evt["channel"]["alternatives"][0]["transcript"]
#         # final transcripts end with newline; interim just overwrite
#         suffix = "\n" if evt["is_final"] else ""
#         end   = "" if evt["is_final"] else "\r"
#         print(CL + txt + suffix, end=end, flush=True)

#     dg_live.register_handler(dg_live.event.TRANSCRIPT_RECEIVED, print_transcript)
#     dg_live.register_handler(dg_live.event.CLOSE,
#                              lambda code: print(f"\n🔒 Deepgram socket closed (code {code})"))

#     # 3) Now actually receive Twilio's messages (await it!)
#     while True:
#         msg = await ws.receive()           # ← await here!
#         if msg is None:
#             break

#         pkt = json.loads(msg)
#         ev  = pkt.get("event")

#         if ev == "start":
#             print("⏺️  Twilio stream started")
#         elif ev == "stop":
#             print("🛑  Twilio stream stopped")
#             break
#         elif ev == "media":
#             raw   = base64.b64decode(pkt["media"]["payload"])
#             lin16 = audioop.ulaw2lin(raw, 2)
#             pcm16 = audioop.ratecv(lin16, 2, 1, 8000, 16000, None)[0]
#             dg_live.send(pcm16)

#     # 4) Tell Deepgram we’re done and wait for final results
#     await dg_live.finish()

# if __name__ == '__main__':
#     port      = 5000
#     public_url = ngrok.connect(port, bind_tls=True).public_url
#     print(f"Public URL: {public_url}")

#     # point Twilio at your tunnel
#     twilio_number = twilio_client.incoming_phone_numbers.list()[0]
#     twilio_number.update(voice_url=public_url + '/call')

#     print(f"Waiting for calls on {twilio_number.phone_number}")
#     app.run(port=port)




# -------------------------------------------
# try:
#     deepgram: DeepgramClient = DeepgramClient()
#     dg_connection = deepgram.listen.websocket.v("1")
# 		# define callbacks for transcription messages
#     def on_message(self, result, **kwargs):
#         sentence = result.channel.alternatives[0].transcript
#         if len(sentence) == 0:
#             return
#         print(f"speaker: {sentence}")
#     dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
#     # connect to websocket
#     options = LiveOptions(model="nova-3", interim_results=False, language="en-US")
#     dg_connection.start(options)
#     lock_exit = threading.Lock()
#     exit = False
#     # define a worker thread
#     def myThread():
#       with httpx.stream("GET", URL) as r:
#         for data in r.iter_bytes():
#           lock_exit.acquire()
#           if exit:
#             	break
#           lock_exit.release()
#           dg_connection.send(data)
#     # start the worker thread
#     myHttp = threading.Thread(target=myThread)
#     myHttp.start()
#     # signal finished
#     input("Press Enter to stop recording...\n\n")
#     lock_exit.acquire()
#     exit = True
#     lock_exit.release()
#     # Wait for the HTTP thread to close and join
#     myHttp.join()
#     # Indicate that we've finished
#     dg_connection.finish()
# except Exception as e:
#     print(f"Could not open socket: {e}")
#     return
