from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import os;
from dotenv import load_dotenv
from fastapi import FastAPI
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from qdrant_client.models import PointStruct, VectorParams, Distance
from typing import List
from langchain_community.utilities import SQLDatabase
from Models.gpt4omini import llm




load_dotenv()




DATABASE_URL = os.getenv('CONNECTION_STRING_ENV')

engine = create_engine(DATABASE_URL, echo=True)

include_tables_list = ["Careers","ServicesOffereds","DirectorsInfo"]
#db = SQLDatabase.from_uri(DATABASE_URL, include_tables=include_tables_list)
db = SQLDatabase(engine=engine, include_tables=include_tables_list)

# Toolkit
#toolkit = SQLDatabaseToolkit(db=db, llm=llm)
 
# Agent that uses LLM + SQL tools
# sql_agent = initialize_agent(
#     tools=toolkit.get_tools(),
#     llm=llm,
#     agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
#     verbose=True
# )



def get_session():
    with Session(engine) as session:
        yield session


# Qdrant Setup

# Load SentenceTransformer model (384-dim embeddings)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Qdrant Setup
#qdrant_client = QdrantClient("http://localhost:6333")
qdrant_client = QdrantClient("http://localhost:6333")
#collection_name = "new_collection_name"  # Change this to your desired collection name















