from Models.gpt4omini import query_model  
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser

#relational: if it sounds structured or data-specific, likely answered by MongoDB
routing_prompt = ChatPromptTemplate.from_template(
    """
    You are an intelligent classifier that routes user queries into one of the following three categories:

    1. **semantic**: The user is asking a natural language question that requires meaning-based understanding, such as product recommendations, search queries, or conceptual questions.

    2. **relational**: The user is asking about structured, factual data that would typically be stored in a SQL or tabular database. This includes filters, aggregations, or direct data retrieval like "show me top 5 orders by revenue" or "total sales in 2023".

    3. **general**: The user is having a casual or open-ended conversation, such as greetings, follow-ups, clarifications, small talk, or context-based questions in a session. These queries often depend on previous messages or use pronouns (e.g., "What about that?", "Tell me more", "Thanks", "Who are you?", "Can you help me with something else?").

    Example general queries:
    - "Hi, how are you?"
    - "Can you help me with that?"
    - "Tell me more about the last product."
    - "Thanks, that was helpful."

    Query: "{query}"

    Return exactly one word only — either: `semantic`, `relational`, or `general`.
    """
)

def classify_query(query: str) -> str:
    prompt = routing_prompt.format_messages(query=query)
    response = query_model(prompt)
    #rewritten_query = StrOutputParser().parse(response)
    return StrOutputParser().parse(response).content.strip().lower()


 
    

    