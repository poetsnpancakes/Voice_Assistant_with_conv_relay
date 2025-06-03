from Models.gpt4omini import query_model
from Database.sqlDB import engine  # Your MSSQL connection via SQLAlchemy
from langchain.prompts import ChatPromptTemplate
from sqlalchemy import inspect
import pandas as pd
import json
import re

# Tables to include
included_tables = ["Careers", "ServicesOffereds", "DirectorsInfo"]

# Sample schema description for the LLM
def get_sql_schema_description():
    inspector = inspect(engine)
    schema_description = ""
    for table_name in included_tables:
        columns = inspector.get_columns(table_name)
        col_names = [col["name"] for col in columns]
        schema_description += f"Table `{table_name}` with columns: {', '.join(col_names)}.\n"
    return schema_description

schema_description = get_sql_schema_description()

# Prompt template for generating SQL
template = ChatPromptTemplate.from_template(
    """
You are an intelligent SQL query generator. Use ONLY the tables and columns described below.

{schema_description}

Write a SQL SELECT query for the question below.
Only return the raw SQL query (without markdown, explanations, or variable assignments).
Only generate the SQL-query for data retrieval, not for data manipulation (INSERT, UPDATE, DELETE ,DROP ,TRUNCATE , ALTER , etc.).

Question: "{query}"
"""
)

# Main function
def sql_query(query: str) -> dict:
    # 1. Generate the SQL using the LLM
    prompt = template.format_messages(schema_description=schema_description, query=query)
    result = query_model(prompt)

    # 2. Extract SQL query string
    raw_sql = result.content.strip()
    raw_sql = re.sub(r"```(?:sql)?", "", raw_sql).strip()

    # 3. Execute query using pandas for easy access to records
    try:
        df = pd.read_sql_query(raw_sql, engine)
    except Exception as e:
        return {"error": f"SQL execution error: {e}", "query": raw_sql}

    if df.empty:
        return {"response": "No results found.", "query": raw_sql}

    # Convert result to list of dictionaries
    db_result = df.to_dict(orient="records")

    # 4. Summarize result using GPT model
    explanation_prompt = f"""
    You are GrootBot, an AI-assistant for Groot Software Solutions.
    You are given a list of search results from a database. Your task is to generate a short(under 200-characters-short), readable answer in natural language based on the result.
    You are not allowed to use any code or markdown formatting in your response.
    - For any query related to careers or job openings, refer to the 'Careers' table in the database.
    - For any query related to founders or directors, refer to the 'directorsinfo' table in the database.
    - Positions available in the company are listed under the 'CareerTitle' column in the 'Careers' table.
    - Each job description is detailed in the 'ShortDescription' column of the 'Careers' table.
    In case user queries about services offered, ask user to visit our website at https://grootsoftwares.com/services.
    In case of an error or no results or if user wants to submit a resume ask user to email at hr@grootsoftwares.com".
    Question: {query}

Results:
{json.dumps(db_result, indent=2, default=str)}

Generate a short, readable answer in natural language based on the result.
"""
    #final_response = query_model(explanation_prompt)

    return {
        #"query": raw_sql,
        #"response": 
        #final_response.content.strip()
        explanation_prompt
    }
