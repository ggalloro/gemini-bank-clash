import os
import sys
import threading
from google import genai

# Load GitHub PAT from environment variable
github_token = os.environ.get("CODER_GITHUB_TOKEN")
if not github_token:
    print("Error: CODER_GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
    sys.exit(1)

# Load Google Project ID from environment variable
google_project_id = os.environ.get("GOOGLE_PROJECT_ID")
if not google_project_id:
    print("Error: GOOGLE_PROJECT_ID environment variable is not set.", file=sys.stderr)
    sys.exit(1)

comment_body = os.environ.get("COMMENT_BODY", "").strip()
issue_number = os.environ.get("ISSUE_NUMBER")
repo = os.environ.get("REPO")

if not comment_body.startswith("/implement"):
    print("Error: Comment body does not start with /implement", file=sys.stderr)
    sys.exit(1)

# Extract instructions
instructions = comment_body[len("/implement"):].strip()

# Formulate prompt using the instruction or falling back to general issue implementation
if not instructions:
    instructions = f"implement issue #{issue_number} in repository {repo} and create a PR for it"
else:
    instructions = f"implement issue #{issue_number} in repository {repo} and create a PR for it. Follow these instructions: {instructions}"

input_query = f"use the `coder` skill and Github PAT `{github_token}` to {instructions}"

client = genai.Client(
    vertexai=True,
    project=google_project_id,
    location="global",
)

stream = client.interactions.create(
    agent="antigravity-preview-05-2026",
    agent_config={
        "type": "antigravity",
        "model": "gemini-3.8-flash",
    },
    input=input_query,
    environment={
        "type": "remote",
        "network": {
            "allowlist": [
                {"domain": "*"}
            ]
        }
    },
    stream=True,
    background=True,
    store=True,
)

timeout_seconds = float(os.environ.get("INTERACTION_TIMEOUT", "1200"))
interaction_id = None


def cancel_interaction():
    print(f"Error: Interaction timed out after {timeout_seconds} seconds.", file=sys.stderr)
    if interaction_id:
        try:
            client.interactions.cancel(id=interaction_id)
        except Exception:
            pass
    sys.stderr.flush()
    sys.stdout.flush()
    os._exit(1)


timer = threading.Timer(timeout_seconds, cancel_interaction)
timer.start()

try:
    for event in stream:
        if not interaction_id:
            if hasattr(event, "interaction") and event.interaction and hasattr(event.interaction, "id"):
                interaction_id = event.interaction.id
            elif hasattr(event, "id") and getattr(event, "id"):
                interaction_id = event.id

        print(event)
finally:
    timer.cancel()

