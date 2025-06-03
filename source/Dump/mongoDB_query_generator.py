from Database.db import product_collection
from Models.gpt4omini import query_model  
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
import ast
import json
import re

# One-time schema introspection
def get_collection_schema_sample(product_coll, sample_size=100):
    sample_docs = list(product_coll.find({}, {"_id": 0}).limit(sample_size))
    return sample_docs

def generate_schema_description(docs):
    fields = set()
    for doc in docs:
        fields.update(doc.keys())
    return f"{', '.join(fields)}."

schema_description = generate_schema_description(get_collection_schema_sample(product_collection))



 # Prompt for LLM
template = ChatPromptTemplate.from_template(
    """
You are a MongoDB query generator.
"{schema_description}"
Generate a MongoDB query in Python dictionary format that can be executed directly using `find` or `aggregate` (not with $query wrapper).
Return ONLY the dictionary.

 Query: "{query}"

 """
)





def mongo_query(query:str)->str:
    prompt = template.format_messages(schema_description=schema_description,query=query)
    result = query_model(prompt)

    # Clean result content to remove markdown formatting
    cleaned_content = re.sub(r"```(?:python)?", "", result.content).strip()
    # Step 2: remove assignment if any (e.g., query = {...})
    cleaned_content = re.sub(r"^\s*\w+\s*=\s*", "", cleaned_content)
    
    
    # Evaluate the cleaned string
    db_query_dict = ast.literal_eval(cleaned_content)

    # Run query in MongoDB
    if any(key.startswith("$") for key in db_query_dict.keys()):
    # Transform into valid pipeline with one key per stage
        pipeline = [{k: db_query_dict[k]} for k in db_query_dict]
        pipeline.append({"$project": {"_id": 0}})
        db_result = list(product_collection.aggregate(pipeline))
    else:
        db_result = list(product_collection.find(db_query_dict, {"_id": 0}))

     #return {"question": query, "db_query": db_query_dict, "results": db_result}

    # Step 4: Generate human-readable response
    explanation_prompt = f"""
        You are a chatbot that converts database query results into a natural language summary.

        Question: {query}

        Results:
        {json.dumps(db_result, indent=2)}

        Generate a short, readable answer in natural language based on the result.
        """
    final_response = query_model(explanation_prompt)

    return {
            #"question": query,
            #"response": 
            final_response.content.strip()
        }


