from dotenv import load_dotenv
import os
import re
from typing import AsyncIterable
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from livekit import agents, rtc
from livekit.agents import (
    AgentSession,
    Agent,
    ChatContext,
    ChatMessage,
    ModelSettings,
    room_io,
    function_tool,
    TurnHandlingOptions,
    InterruptionOptions,
    UserStateChangedEvent,
    AgentStateChangedEvent,
    FunctionToolsExecutedEvent,
    ConversationItemAddedEvent,
)
from livekit.plugins import (
    cartesia,
    groq,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel
import logging
import signal
import sys
import asyncio
from tools import open_url, navigate_to_section, get_product_info

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

# Language-specific Cartesia configuration
# STT: ink-whisper supports multilingual input
# TTS: sonic-3 supports en, ar, fr natively
LANGUAGE_CONFIG: dict[str, dict[str, str]] = {
    "en": {"stt_lang": "en", "tts_voice": "f786b574-daa5-4673-aa0c-cbe3e8534c02", "tts_lang": "en"},
    "ar": {"stt_lang": "ar", "tts_voice": "f786b574-daa5-4673-aa0c-cbe3e8534c02", "tts_lang": "ar"},
    "fr": {"stt_lang": "fr", "tts_voice": "f786b574-daa5-4673-aa0c-cbe3e8534c02", "tts_lang": "fr"},
}

# Sliding window: keep last N conversation items to cap per-turn input tokens.
# 70b-versatile uses ~2400 tokens/request. Groq free tier = 12k TPM.
# 10 items keeps enough context for the model to remember tool-calling format.
MAX_HISTORY_ITEMS = 10  # ~5 user + 5 assistant turns


# Regex to strip Llama-style function call syntax that leaks into text output
_FUNC_CALL_RE = re.compile(
    r"<function=\w+.*?</function>|<\|.*?\|>",
    re.DOTALL,
)


async def _strip_function_calls(text: AsyncIterable[str]) -> AsyncIterable[str]:
    """Filter out function-call markup from the LLM text stream before TTS."""
    buf = ""
    for chunk in text if hasattr(text, '__iter__') else []:
        yield chunk
    async for chunk in text:
        buf += chunk
        # Only yield once we're sure there's no partial <function tag
        while buf:
            match = _FUNC_CALL_RE.search(buf)
            if match:
                # Yield text before the match
                if match.start() > 0:
                    yield buf[:match.start()]
                buf = buf[match.end():]
            elif "<" in buf:
                # Might be a partial tag — hold it
                idx = buf.rfind("<")
                if idx > 0:
                    yield buf[:idx]
                    buf = buf[idx:]
                break
            else:
                yield buf
                buf = ""
                break
    # Flush remaining buffer (strip any leftover tags)
    if buf:
        cleaned = _FUNC_CALL_RE.sub("", buf).strip()
        if cleaned:
            yield cleaned


class Assistant(Agent):
    def __init__(self) -> None:
        logger.info(
            "Initializing Assistant agent with tools: [open_url, navigate_to_section, get_product_info]")
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            tools=[open_url, navigate_to_section, get_product_info],
        )
        logger.info("Assistant agent initialized successfully")

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage,
    ) -> None:
        """Prune old conversation messages to keep context window bounded."""
        turn_ctx.truncate(max_items=MAX_HISTORY_ITEMS)

    async def tts_node(
        self, text: AsyncIterable[str], model_settings: ModelSettings,
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Strip leaked function-call syntax before sending text to TTS."""
        async for frame in Agent.default.tts_node(
            self, _strip_function_calls(text), model_settings
        ):
            yield frame


async def entrypoint(ctx: agents.JobContext):
    global shutdown_requested

    logger.info("Starting agent entrypoint")
    logger.info(f"Job context: {ctx}")

    try:
        # Wait for participant to connect and read their language attribute
        await ctx.connect()
        logger.info("Connected to context successfully")

        # Get language from the first remote participant's attributes
        language = "en"
        for p in ctx.room.remote_participants.values():
            lang_attr = p.attributes.get("language", "en")
            if lang_attr in LANGUAGE_CONFIG:
                language = lang_attr
            break

        # If no remote participant yet, also check local participant
        if language == "en" and ctx.room.local_participant:
            lang_attr = ctx.room.local_participant.attributes.get(
                "language", "en")
            if lang_attr in LANGUAGE_CONFIG:
                language = lang_attr

        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["en"])
        logger.info(
            f"Language detected: {language}, STT: {config['stt_lang']}, TTS voice: {config['tts_voice']}")

        session = AgentSession(
            stt=cartesia.STT(model="ink-whisper", language=config["stt_lang"]),
            llm=groq.LLM(
                model="llama-3.3-70b-versatile",
                temperature=0.6,
                parallel_tool_calls=False,
            ),
            tts=cartesia.TTS(
                model="sonic-3",
                voice=config["tts_voice"],
                language=config["tts_lang"],
            ),
            vad=silero.VAD.load(),
            turn_handling=TurnHandlingOptions(
                turn_detection=MultilingualModel(),
                interruption=InterruptionOptions(
                    enabled=True,
                    mode="adaptive",
                    min_duration=0.5,
                    min_words=0,
                    resume_false_interruption=True,
                    false_interruption_timeout=2.0,
                ),
            ),
            # 5.4 — Emit "away" state after 30s of user silence
            user_away_timeout=30.0,
        )

        # ── Session Event Listeners for observability ──

        @session.on("close")
        def on_session_close(ev=None):
            # 5.10 — Log session close reason and usage metrics
            reason = getattr(ev, "reason", "unknown") if ev else "unknown"
            error = getattr(ev, "error", None) if ev else None
            logger.info(f"[SESSION CLOSED] reason={reason}, error={error}")
            if reason == "error":
                logger.error(f"Session closed due to error: {error}")
            usage = session.usage
            if usage and usage.model_usage:
                for mu in usage.model_usage:
                    logger.info(f"[USAGE] Session totals: {mu}")

        @session.on("conversation_item_added")
        def on_conversation_item(ev: ConversationItemAddedEvent):
            item = ev.item
            role = getattr(item, "role", None)
            text = getattr(item, "text_content", None)
            if role is not None:
                logger.info(f"[CONVERSATION] {role}: {text}")

        @session.on("agent_state_changed")
        def on_agent_state(ev: AgentStateChangedEvent):
            logger.info(f"[STATE] Agent: {ev.old_state} → {ev.new_state}")

        @session.on("user_state_changed")
        def on_user_state(ev: UserStateChangedEvent):
            logger.info(f"[STATE] User: {ev.old_state} → {ev.new_state}")
            # 5.4 — Prompt idle users before they ghost
            if ev.new_state == "away":
                asyncio.ensure_future(
                    session.generate_reply(
                        instructions="The user has been silent for a while. Ask if they're still there or need any help."
                    )
                )

        @session.on("function_tools_executed")
        def on_tools_executed(ev: FunctionToolsExecutedEvent):
            for call, output in ev.zipped():
                logger.info(
                    f"[TOOL] {call.name}({call.arguments}) → {output.output if output else 'None'}")

        @session.on("user_input_transcribed")
        def on_transcription(ev):
            if ev.is_final:
                logger.info(f"[STT] Final: {ev.transcript}")

        logger.info(
            f"AgentSession created with Cartesia STT ({config['stt_lang']}) + Groq LLM (llama-3.3-70b-versatile) + Cartesia TTS (sonic-3) pipeline")

        agent = Assistant()
        logger.info("Assistant agent created")

        logger.info("Starting session with room and agent")
        await session.start(
            room=ctx.room,
            agent=agent,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    # LiveKit Cloud enhanced noise cancellation
                    # - If self-hosting, omit this parameter
                    # - For telephony applications, use `BVCTelephony` for best results
                    noise_cancellation=noise_cancellation.BVC(),
                ),
            ),
        )
        logger.info("Session started successfully")

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
