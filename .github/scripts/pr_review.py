import asyncio
import os
import sys
from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.hooks import policy

# Load Google Project ID from environment variable
google_project_id = os.environ.get("GOOGLE_PROJECT_ID")
if not google_project_id:
    print("Error: GOOGLE_PROJECT_ID environment variable is not set.", file=sys.stderr)
    sys.exit(1)

repo = os.environ.get("GITHUB_REPOSITORY")
if not repo:
    print("Error: GITHUB_REPOSITORY environment variable is not set.", file=sys.stderr)
    sys.exit(1)

# Read instructions from stdin alternatively
if not sys.stdin.isatty():
    instructions = sys.stdin.read().strip()
else:
    instructions = ""

if not instructions:
    print("Error: No instructions provided via stdin.", file=sys.stderr)
    sys.exit(1)

async def main():
    skills_dir = os.path.abspath(".agents/skills")
    config = LocalAgentConfig(
        vertex=True,
        project=google_project_id,
        location="global",
        skills_paths=[skills_dir],
        policies=[policy.allow_all()],
    )

    timeout_seconds = float(os.environ.get("INTERACTION_TIMEOUT", "600"))

    async with Agent(config=config) as agent:
        try:
            response = await asyncio.wait_for(agent.chat(instructions), timeout=timeout_seconds)

            print("Agent (Streaming thoughts):", flush=True)
            print("-------------------------------------------------------", flush=True)
            async for thought in response.thoughts:
                print(thought, end="", flush=True)
            print("\n-------------------------------------------------------\n", flush=True)

            print("Agent (Streaming final answer):", flush=True)
            print("-------------------------------------------------------", flush=True)
            async for token in response:
                print(token, end="", flush=True)
            print("\n-------------------------------------------------------\n", flush=True)
        except asyncio.TimeoutError:
            print(f"Error: Interaction timed out after {timeout_seconds} seconds.", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
