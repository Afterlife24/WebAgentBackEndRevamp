from dotenv import load_dotenv
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool
from livekit.plugins import (
    openai,
    noise_cancellation,
)
from livekit.plugins.openai.realtime.realtime_model import TurnDetection
import logging
import signal
import sys
import asyncio
from tools import open_url, navigate_to_section

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
            "Initializing Assistant agent with tools: [open_url, navigate_to_section]")
        super().__init__(instructions=AGENT_INSTRUCTION,
                         tools=[open_url, navigate_to_section],)
        logger.info("Assistant agent initialized successfully")


async def entrypoint(ctx: agents.JobContext):
    global shutdown_requested

    logger.info("Starting agent entrypoint")
    logger.info(f"Job context: {ctx}")

    try:
        session = AgentSession(
            llm=openai.realtime.RealtimeModel(
                voice="alloy",
                turn_detection=TurnDetection(
                    type="server_vad",
                    threshold=0.5,
                    prefix_padding_ms=300,
                    silence_duration_ms=500,
                ),
            ),
        )
        logger.info(
            "AgentSession created with OpenAI Realtime Model (voice: alloy, turn detection: server_vad, transcription language: en)")

        agent = Assistant()
        logger.info("Assistant agent created")

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
