import requests
import os
from dotenv import load_dotenv



load_dotenv()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("RACHEL_VOICE_ID")




def synthesize_with_elevenlabs(text: str) -> str:
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
        #return f"{ngrok.connect(5000, bind_tls=True).public_url}/{filepath}"
        return
    else:
        print("❌ Error synthesizing with ElevenLabs:", response.text)
        return ""
