# hello_claude.py
# Our first test: prove we can talk to Claude from Python.

import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load the API key from the .env file into our environment
load_dotenv()

# Create a Claude client using the API key
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Send a single message to Claude and get the response
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=300,
    messages=[
        {
            "role": "user",
            "content": "Say hello to me as if I'm an AI Product Manager building Pulse AI — a real-time transaction intelligence agent for digital banking. Keep it short and energetic."
        }
    ]
)

# Print Claude's response to the terminal
print("\n=== Claude's response ===\n")
print(response.content[0].text)
print("\n=========================\n")