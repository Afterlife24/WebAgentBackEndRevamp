# Language Detection Issue - Solutions

## Problem Summary

The OpenAI Realtime API agent automatically switches languages based on:

- Background noise misinterpreted as speech
- Names that sound like other languages (e.g., "Amir" → Arabic, "Isabella" → Italian)
- The model's aggressive multilingual capabilities

## Solution 1: Enhanced Realtime Model Configuration (IMPLEMENTED ✅)

### Changes Made:

1. **Strict Prompt Instructions** (`prompts.py`)
   - Added CRITICAL LANGUAGE RULES at the top of AGENT_INSTRUCTION
   - Explicit instructions to NEVER switch languages
   - Clear guidance to ignore names, background noise, and single words

2. **VAD Configuration** (`agent.py`)
   - Increased `threshold` to 0.8 (less sensitive to background noise)
   - Reduced `prefix_padding_ms` to 300ms (captures less pre-speech noise)
   - Increased `silence_duration_ms` to 800ms (requires longer silence before turn ends)

### Testing:

```bash
cd webBackendCors
python agent.py dev
```

Test with phrases like:

- "Can I speak to Amir?"
- "I want to talk to Isabella Rossi"
- Background noise scenarios

### Expected Behavior:

- Agent stays in English regardless of names mentioned
- Less sensitive to background noise
- Politely declines if user speaks another language

---

## Solution 2: Add Language Detection Tool (Optional Enhancement)

If you need controlled multilingual support later, add this tool:

```python
# Add to tools.py

from livekit.agents import function_tool
import logging

logger = logging.getLogger(__name__)

@function_tool
async def detect_user_language(language_code: str) -> str:
    """
    Called when you detect the user is speaking a different language.

    Args:
        language_code: ISO language code (en, es, ar, it, etc.)

    Returns:
        Instruction on how to proceed
    """
    logger.info(f"Language detection triggered: {language_code}")

    # Force English only
    if language_code != "en":
        return "User is speaking a different language. Politely respond in ENGLISH: 'I apologize, but I can only communicate in English. How can I help you today?'"

    return "Continue in English"
```

Then add to Assistant class:

```python
from tools import open_url, navigate_to_section, detect_user_language

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            tools=[open_url, navigate_to_section, detect_user_language],
        )
```

---

## Solution 3: Switch to STT-LLM-TTS Pipeline (Alternative Architecture)

If the Realtime API continues to have issues, you can switch to a traditional pipeline:

### Pros:

- Complete control over each component
- Can lock STT to English-only
- More predictable behavior
- Can use different providers for each component

### Cons:

- Higher latency (~200-500ms vs ~100ms)
- More complex to maintain
- Loses some natural conversation flow

### Implementation:

```python
# agent.py - STT-LLM-TTS version

from livekit.plugins import openai, deepgram, elevenlabs
from livekit.agents import AgentSession

async def entrypoint(ctx: agents.JobContext):
    # STT: Deepgram with English-only
    stt = deepgram.STT(
        model="nova-2",
        language="en",  # Lock to English
        detect_language=False,  # Disable auto-detection
    )

    # LLM: OpenAI GPT-4
    llm = openai.LLM(
        model="gpt-4-turbo",
        temperature=0.2,
    )

    # TTS: OpenAI or ElevenLabs
    tts = openai.TTS(
        voice="alloy",
    )

    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
    )

    # Rest of the code remains the same
    await session.start(room=ctx.room, agent=agent)
```

### Required Changes:

1. Update `requirements.txt`:

   ```
   livekit-plugins-deepgram
   livekit-plugins-elevenlabs  # optional
   ```

2. Add API keys to `.env`:
   ```
   DEEPGRAM_API_KEY=...
   ELEVENLABS_API_KEY=...  # if using ElevenLabs
   ```

---

## Solution 4: Hybrid Approach (Best of Both Worlds)

Use Realtime API with text-only mode + separate TTS:

```python
session = AgentSession(
    llm=openai.realtime.RealtimeModel(
        voice="alloy",
        temperature=0.2,
        modalities=["text"],  # Text-only mode
    ),
    tts=openai.TTS(voice="alloy"),  # Separate TTS
)
```

This gives you:

- Realtime comprehension benefits
- Complete control over TTS output
- Can force TTS language independently

---

## Recommendation

**Start with Solution 1** (already implemented). This should resolve 80-90% of false language switching.

**If issues persist:**

1. Try Solution 4 (Hybrid) - keeps low latency
2. Only switch to Solution 3 (STT-LLM-TTS) if latency is acceptable for your use case

**Monitor:**

- Check `KMS/logs/` for conversation logs
- Look for patterns in when language switching occurs
- Adjust VAD thresholds based on your environment

---

## Testing Checklist

- [ ] Test with common names from different languages
- [ ] Test with background noise (music, other conversations)
- [ ] Test with silence periods
- [ ] Test with fast speech
- [ ] Test with accented English
- [ ] Verify latency is still acceptable
- [ ] Check conversation logs for unexpected language switches

---

## Rollback

If you need to revert changes:

```bash
cd webBackendCors
git diff prompts.py agent.py
git checkout prompts.py agent.py  # if needed
```
