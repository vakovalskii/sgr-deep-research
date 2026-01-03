# Research with Messages

Example demonstrating the use of `task_messages` with multimodal content in OpenAI format.

## Description

This example shows how to send messages with images to SGR Agent Core API. The API accepts messages in OpenAI format, allowing you to include multimodal content (text and images) in your requests.

## Prerequisites

1. SGR Agent Core API server must be running:

```bash
sgr --config-file examples/sgr_deep_research/config.yaml
```

2. The server should be accessible at `http://localhost:8010/v1`

## Usage

Run the example script:

```bash
python examples/research_with_images/research_with_images.py
```

## Example: Message with Image

The example demonstrates sending a message with both text and an image:

```python
from openai import OpenAI
import base64
from pathlib import Path

client = OpenAI(base_url="http://localhost:8010/v1", api_key="dummy")


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


image_path = Path(__file__).parent / "sgr_concept.png"
base64_image = encode_image(str(image_path))

response = client.chat.completions.create(
    model="custom_research_agent",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "This is the SGR Agent Core architecture diagram. Explain how Schema-Guided Reasoning works based on this diagram.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                },
            ],
        },
    ],
    stream=True,
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## How It Works

1. **Image Encoding**: The image file is read and encoded to base64 format
2. **Multimodal Content**: The message content is a list containing both text and image parts
3. **Message Format**: The message follows OpenAI's multimodal message format with `type: "text"` and `type: "image_url"`
4. **Agent Processing**: The agent receives the complete message including the image and can analyze it

## Message Format

Messages follow OpenAI's `ChatCompletionMessageParam` format:

- `role`: One of `"system"`, `"user"`, `"assistant"`, or `"tool"`
- `content`: Can be:
  - A string for text-only messages
  - A list of content parts for multimodal messages:
    - `{"type": "text", "text": "..."}` for text
    - `{"type": "image_url", "image_url": {"url": "..."}}` for images
- Optional fields: `name`, `tool_calls`, `tool_call_id`

## Notes

- Images must be base64-encoded and prefixed with the data URI scheme (`data:image/png;base64,`)
- The agent receives all messages as-is in `task_messages`
- Prompts are added as separate messages at the end of the context
- All message content is preserved and passed to the agent
