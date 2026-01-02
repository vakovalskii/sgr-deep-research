import base64
from pathlib import Path

from openai import OpenAI

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
                    "text": (
                        "This is the SGR Agent Core architecture diagram. "
                        "Explain how Schema-Guided Reasoning works based on this diagram."
                    ),
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
