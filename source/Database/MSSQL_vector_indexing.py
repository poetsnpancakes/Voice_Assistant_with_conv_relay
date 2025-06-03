from sqlalchemy import create_engine, text
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from tqdm import tqdm
import os



# Load environment variables
load_dotenv()

# MSSQL setup
DATABASE_URL = os.getenv("CONNECTION_STRING_ENV")
engine = create_engine(DATABASE_URL)
include_tables = ["Careers", "ServicesOffereds", "DirectorsInfo"]

# Embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim vectors

# Qdrant setup
qdrant_client = QdrantClient("http://localhost:6333")

# Function to fetch records from a table
def fetch_records(table_name):
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table_name}"))
        return [dict(row._mapping) for row in result]

# Loop through tables
for table in include_tables:
    print(f"\n📥 Fetching records from '{table}'...")
    records = fetch_records(table)

    if not records:
        print(f"⚠️ No records found in table '{table}'")
        continue

    # Define collection name as table name
    collection_name = table.lower()

    # Recreate collection in Qdrant
    qdrant_client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )

    # Create and collect embeddings
    points = []
    for idx, record in enumerate(tqdm(records, desc=f"Embedding '{table}'")):
        # You can customize which fields to use here
        text_input = " ".join([str(v) for v in record.values() if isinstance(v, str)])
        if not text_input:
            continue

        embedding = embedding_model.encode(text_input)

        point = PointStruct(
            id=idx,
            vector=embedding.tolist(),
            payload={**record}
        )
        points.append(point)

    # Upload to Qdrant
    if points:
        qdrant_client.upsert(collection_name=collection_name, points=points)
        print(f"✅ Inserted {len(points)} records into collection '{collection_name}'")
    else:
        print(f"⚠️ No valid text fields found for embedding in table '{table}'")
