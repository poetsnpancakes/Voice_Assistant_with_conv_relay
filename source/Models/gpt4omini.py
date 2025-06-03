import getpass
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not os.environ.get("OPENAI_API_KEY"):
  os.environ["OPENAI_API_KEY"] = getpass.getpass("")

#chaining
llm = init_chat_model("gpt-4o-mini", model_provider="openai") 

def query_model(query:str)-> str:
       res= llm.invoke([HumanMessage(content=str(query))])
       return res
