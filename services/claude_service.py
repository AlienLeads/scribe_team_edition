import anthropic
import os

def get_claude_response(model_name, system_instruction, chat_history, prompt_text, images=None):
    # Initialize Anthropic client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # 1. Format System Prompt with Ephemeral Caching
    system_block = [
        {
            "type": "text",
            "text": system_instruction,
            "cache_control": {"type": "ephemeral"}
        }
    ]

    # 2. Format Chat History (Anthropic expects 'user' or 'assistant')
    formatted_messages = []
    for m in chat_history:
        role = "assistant" if m["role"] == "model" else m["role"] 
        formatted_messages.append({"role": role, "content": m["content"]})

    # 3. Add the current user prompt
    if images and len(images) > 0:
        return "Claude Vision is not yet configured in the adapter. Please try a text-only prompt to test the connection!"
    else:
        formatted_messages.append({"role": "user", "content": prompt_text})

    # 4. Execute the API Call
    response = client.messages.create(
        model=model_name, # <--- Changed from hardcoded string to the variable!
        max_tokens=4096,
        system=system_block,
        messages=formatted_messages
    )

    # 5. Terminal Audit (To verify caching is working!)
    print("\n" + "="*40)
    print("CACHE AUDIT: CLAUDE")
    print(f"Input Tokens: {response.usage.input_tokens}")
    if hasattr(response.usage, 'cache_creation_input_tokens'):
        print(f"Cache Created: {response.usage.cache_creation_input_tokens}")
        print(f"Cache Read: {response.usage.cache_read_input_tokens}")
    print("="*40 + "\n")

    return response.content[0].text