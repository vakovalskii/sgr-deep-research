from openai import OpenAI

# Initialize client
client = OpenAI(
    base_url="http://localhost:8010/v1",
    api_key="dummy",  # Not required for local server
)

# Make research request
response = client.chat.completions.create(
    model="sgr_tool_calling_agent",
    messages=[{"role": "user", "content": "Research BMW X6 2025 prices in Russia"}],
    stream=True,
    temperature=0.4,
)

# Print streaming response
for chunk in response:
    try:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="")
    except (AttributeError, IndexError, TypeError):
        pass
    try:
        if chunk.choices[0].delta.tool_calls[0].function.arguments:
            print(chunk.choices[0].delta.tool_calls[0].function.arguments, end="")
    except (AttributeError, IndexError, TypeError):
        pass
