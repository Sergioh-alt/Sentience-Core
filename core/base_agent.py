import os
from langchain_groq import ChatGroq

class BaseAgent:
    def __init__(self, aid, model, temp=0.3):
        self.id = aid
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Falta GROQ_API_KEY en el .env")
        
        self.llm = ChatGroq(
            model_name=model,
            temperature=temp,
            groq_api_key=api_key
        )