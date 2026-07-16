"""Checkpointing, rollback and restore over the REST API.

Run an SGR server with checkpointing enabled, for example in config.yaml:

    execution:
      checkpoint:
        enabled: true
        backend: file      # survives a server restart
        dir: checkpoints

Then start a research request, inspect its checkpoints, roll it back to an
earlier step, and (after a restart) restore it from disk.
"""

import json

import requests
from openai import OpenAI

BASE_URL = "http://localhost:8010"

client = OpenAI(base_url=f"{BASE_URL}/v1", api_key="dummy")

# Step 1: start a research request and capture the agent id.
print("Starting research...")
response = client.chat.completions.create(
    model="sgr_agent",
    messages=[{"role": "user", "content": "Research AI market trends"}],
    stream=True,
    temperature=0,
)

agent_id = None
for chunk in response:
    if chunk.model and chunk.model.startswith("sgr_agent_"):
        agent_id = chunk.model
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

print(f"\n\nAgent ID: {agent_id}")

# Step 2: list the checkpoints the agent saved while running.
checkpoints = requests.get(f"{BASE_URL}/agents/{agent_id}/checkpoints").json()
print(f"\nSaved {checkpoints['total']} checkpoints:")
for cp in checkpoints["checkpoints"]:
    print(f"  step {cp['step']} — state={cp['state']} — {cp['created_at']}")

# Step 3: roll the live agent back to step 1.
rollback = requests.post(
    f"{BASE_URL}/agents/{agent_id}/rollback",
    json={"step": 1},
).json()
print(f"\nRolled back to step {rollback['step']} (state={rollback['state']})")

# Step 4: after a server restart the agent is gone from memory, but with the
# file backend its checkpoints remain on disk. Restore it by id:
restore = requests.post(f"{BASE_URL}/agents/{agent_id}/restore").json()
print(f"\nRestored agent {restore['agent_id']} at step {restore['step']}")

# The restored agent is addressable again — its state is available via the API.
state = requests.get(f"{BASE_URL}/agents/{agent_id}/state").json()
print(json.dumps(state, indent=2, ensure_ascii=False))
