from dotenv import load_dotenv
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool
from livekit.plugins import (
    openai,
    noise_cancellation,
)
from mcp_client import MCPServerSse
from mcp_client.agent_tools import MCPToolsIntegration
import os
import logging
import signal
import sys
import asyncio
from tools import open_url

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable to track if shutdown is requested
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_requested = True
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        logger.info(
            "Initializing Assistant agent with tools: [open_url]")
        super().__init__(instructions=AGENT_INSTRUCTION,
                         tools=[open_url],)
        logger.info("Assistant agent initialized successfully")


async def entrypoint(ctx: agents.JobContext):
    global shutdown_requested

    logger.info("Starting agent entrypoint")
    logger.info(f"Job context: {ctx}")

    try:
        session = AgentSession(
            llm=openai.realtime.RealtimeModel(
                voice="alloy",  # OpenAI voice options: alloy, echo, fable, onyx, nova, shimmer
                temperature=0.2,
            ),
        )
        logger.info(
            "AgentSession created with OpenAI Realtime Model (voice: alloy)")

        mcp_server_url = os.environ.get("N8N_MCP_SERVER_URL")
        logger.info(f"MCP Server URL from environment: {mcp_server_url}")

        mcp_server = MCPServerSse(
            params={"url": mcp_server_url},
            cache_tools_list=True,
            name="SSE MCP Server"
        )
        logger.info("MCP Server created")

        logger.info("Creating agent with MCP tools integration")
        agent = await MCPToolsIntegration.create_agent_with_tools(
            agent_class=Assistant,
            mcp_servers=[mcp_server]
        )
        logger.info("Agent with MCP tools created successfully")

        logger.info("Starting session with room and agent")
        await session.start(
            room=ctx.room,
            agent=agent,
            room_input_options=RoomInputOptions(
                # LiveKit Cloud enhanced noise cancellation
                # - If self-hosting, omit this parameter
                # - For telephony applications, use `BVCTelephony` for best results
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )
        logger.info("Session started successfully")

        logger.info("Connecting to context")
        await ctx.connect()
        logger.info("Connected to context successfully")

        logger.info("Generating initial reply with session instructions")
        await session.generate_reply(
            instructions=SESSION_INSTRUCTION,
        )
        logger.info("Initial reply generated successfully")

        # Keep the session alive until shutdown is requested
        while not shutdown_requested:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error in agent entrypoint: {e}")
        raise
    finally:
        logger.info("Agent entrypoint cleanup completed")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            port=8081,  # Explicitly set port 8081 for web agent
        )
    )
