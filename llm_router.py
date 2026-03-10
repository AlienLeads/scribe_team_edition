import os
from services.gemini_service import get_gemini_response
from services.claude_service import get_claude_response  # <-- Uncommented!

def generate_response(provider, model_name, system_instruction, chat_history, prompt_text, images=None):

    if provider.lower() == "claude":
        # <-- Now it actually calls the file!
        return get_claude_response(model_name, system_instruction, chat_history, prompt_text, images)

    elif provider.lower() == "gemini":
        return get_gemini_response(model_name, system_instruction, chat_history, prompt_text, images)

    else:
        raise ValueError(f"Unknown provider: {provider}")   