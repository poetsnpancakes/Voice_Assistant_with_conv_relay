import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Router import voice_assistant_router
from dotenv import load_dotenv
from pyngrok import ngrok
import os
from Clients.twilio_client import twilio_client


load_dotenv()

app = FastAPI()

port= 5000
public_url= ngrok.connect(port, bind_tls=True).public_url


'''
origins = [
  "http://127.0.0.1:8000/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
'''

app.include_router(voice_assistant_router.router)



if __name__ == "__main__":
    
    #port = 5000 
    #public_url= ngrok.connect(port, bind_tls=True).public_url
    print(f"🌐 Public URL: {public_url}")

    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=f"{public_url}/call")
    print(f"📞 Waiting for calls on {number.phone_number}")

    uvicorn.run("main:app", port=port)


#http://127.0.0.1:8000/docs
#http://localhost:8000/docs