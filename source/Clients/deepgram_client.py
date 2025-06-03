from deepgram import DeepgramClient
from dotenv import load_dotenv
import os


# Load environment variables from .env file
load_dotenv()

deepgram_client: DeepgramClient = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))