from Models.gpt4omini import query_model  
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser

def llm_rephrase(query: str) -> str:
    template = ChatPromptTemplate.from_template("""
    Rephrase this user query to be more search-friendly for a vector database.
    In case there is query related to services, rephrase this query and search from 'servicesoffereds' collection.
    In case there is query related to careers, rephrase this query and search from 'careers' collection.
    - For any query related to careers or job openings, refer to the 'Careers' table in the database.
    - Positions available in the company are listed under the 'CareerTitle' column in the 'Careers' table.
    - Each job description is detailed in the 'ShortDescription' column of the 'Careers' table.
    Query:'{query}'
 """
    )
    prompt = template.format(query=query)
    response = query_model(prompt)
    rewritten_query = StrOutputParser().parse(response)
    
    #return response.choices[0].message.content.strip()
    return rewritten_query.content.strip()