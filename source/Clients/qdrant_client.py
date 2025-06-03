from qdrant_client import QdrantClient
from dotenv import load_dotenv
import os
from sentence_transformers import SentenceTransformer

# Load environment variables from .env file
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
qdrant = QdrantClient("QDRANT_URL")


# Qdrant setup
# Load SentenceTransformer model (384-dim embeddings)
#embedding_model = SentenceTransformer("all-MiniLM-L6-v2")