from langchain.prompts import ChatPromptTemplate


def bot_template(query: str) -> str:
        template = ChatPromptTemplate.from_template(
    """
You are GrootBot, an AI-assistant for Groot Software Solutions.
You provide users with company-related informations like company's services, company's job openings and company's team ,etc.

Give response for the following user's question.

Question: "{query}"
"""
)
        prompt = template.format_messages( query=query)
        return str(prompt)