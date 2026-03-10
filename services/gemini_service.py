from google import genai
from google.genai import types
import os

def get_gemini_response(model_name, system_instruction, chat_history, prompt_text, images=None):
    # Initialize the client locally inside the service
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    # Format the history specifically for Gemini's Pydantic schema
    formatted_history = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} 
        for m in chat_history
    ]

    chat = client.chats.create(
        model=model_name,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction
        ),
        history=formatted_history
    )

    # Handle the multimodal payload
    if images and len(images) > 0:
        content_packet = [prompt_text] + images
        response = chat.send_message(message=content_packet)
    else:
        response = chat.send_message(message=prompt_text)

    # Do the token auditing right here in the terminal
    if hasattr(response, 'usage_metadata'):
        print("\n" + "="*40)
        print(f"CACHE AUDIT: {model_name}")
        print(f"Total Tokens:  {response.usage_metadata.total_token_count}")
        if hasattr(response.usage_metadata, 'cached_content_token_count'):
            print(f"Cached Tokens: {response.usage_metadata.cached_content_token_count}")
        else:
            print("Cached Tokens: 0 (Key not returned by API)")
        print("="*40 + "\n")

    return response.text