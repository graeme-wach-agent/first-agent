from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY is missing from .env")

client = OpenAI(api_key=api_key)

user_input = input("What do you want to ask the agent? ")

response = client.responses.create(
    model="gpt-4.1-mini",
    input=user_input
)

print("\nAgent:\n")
print(response.output[0].content[0].text)