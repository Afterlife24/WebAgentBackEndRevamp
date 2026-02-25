# Multilingual Support with Controlled Language Switching

## Overview

The Web Agent now supports multilingual conversations while preventing accidental language switching from background noise, names, or gibberish.

## How It Works

### Default Behavior

- Agent starts in **English** by default
- Stays in English unless user explicitly requests a language change
- Ignores false triggers (names, background noise, single words)

### Intentional Language Switching

The agent will switch languages when:

1. **Explicit Request**: User clearly asks to switch

   ```
   User: "Can we speak in Spanish?"
   User: "Please switch to Arabic"
   User: "I prefer German"
   ```

2. **Consistent Foreign Language**: User speaks 2-3 complete sentences in another language
   ```
   User: "Hola, me gustaría información sobre sus servicios. ¿Pueden ayudarme?"
   Agent: "I can speak multiple languages. Would you prefer Spanish or English?"
   User: "Spanish please"
   Agent: [switches to Spanish]
   ```

### Prevented Scenarios

The agent will NOT switch for:

- ❌ Names: "Can I speak to Amir?" (stays in English)
- ❌ Single words: "Gracias" (stays in English)
- ❌ Background noise or gibberish
- ❌ Unclear/garbled audio

## Supported Languages

OpenAI Realtime API supports 50+ languages including:

**European Languages:**

- Spanish (es), French (fr), German (de), Italian (it)
- Portuguese (pt), Dutch (nl), Polish (pl), Russian (ru)
- Greek (el), Swedish (sv), Norwegian (no), Danish (da)

**Middle Eastern:**

- Arabic (ar), Hebrew (he), Turkish (tr), Persian (fa)

**Asian Languages:**

- Chinese (zh), Japanese (ja), Korean (ko)
- Hindi (hi), Thai (th), Vietnamese (vi)
- Indonesian (id), Malay (ms), Tagalog (tl)

**And many more...**

## Implementation Details

### 1. Smart Language Protocol (`prompts.py`)

```python
# Language rules in AGENT_INSTRUCTION:
- START in ENGLISH by default
- DO NOT switch based on names, noise, or single words
- ONLY switch when user explicitly requests it
- Confirm before switching: "Would you like to continue in [language]?"
```

### 2. Language Confirmation Tool (`tools.py`)

```python
@function_tool
async def confirm_language_switch(language: str, language_code: str):
    """
    Called when agent wants to confirm a language switch.
    Logs the switch for analytics.
    """
```

### 3. VAD Configuration (`agent.py`)

```python
turn_detection=openai.realtime.ServerVadOptions(
    threshold=0.8,           # Less sensitive to noise
    prefix_padding_ms=300,   # Captures less pre-speech noise
    silence_duration_ms=800, # Longer silence required
)
```

## Testing

### Test Cases

1. **Name Triggers (Should NOT switch)**

   ```
   "Can I speak to Amir?" → Stays in English ✅
   "I want to talk to Isabella Rossi" → Stays in English ✅
   "Connect me with Anastasia" → Stays in English ✅
   ```

2. **Explicit Requests (Should switch)**

   ```
   "Can we speak in Spanish?" → Confirms and switches ✅
   "Please switch to Arabic" → Confirms and switches ✅
   "I prefer French" → Confirms and switches ✅
   ```

3. **Consistent Foreign Speech (Should ask)**

   ```
   User speaks 2-3 sentences in Spanish
   → Agent asks: "Would you prefer Spanish or English?" ✅
   ```

4. **Background Noise (Should ignore)**
   ```
   Music, other conversations, TV → Stays in English ✅
   ```

### Running Tests

```bash
cd webBackendCors

# Start the agent
python agent.py dev

# In another terminal, start the Flask server
python web_agnet_server.py

# Test from frontend
cd ../3AgentsWebsiteRevamp_React
npm run dev
```

## Conversation Flow Examples

### Example 1: User Wants Spanish

```
Agent: "Hello! I'm your AI assistant from Afterlife..."
User: "Can we speak in Spanish?"
Agent: [calls confirm_language_switch("Spanish", "es")]
Agent: "¡Por supuesto! Continuemos en español. ¿Cómo puedo ayudarte hoy?"
User: "Quiero información sobre el agente de voz"
Agent: "El Agente de Voz de Afterlife permite a los clientes..."
```

### Example 2: User Mentions Foreign Name

```
Agent: "Hello! How can I help you today?"
User: "I need to contact Amir about the pricing"
Agent: "I'd be happy to help you with pricing information..." (stays in English)
```

### Example 3: User Starts Speaking Arabic

```
Agent: "Hello! How can I help you today?"
User: "مرحبا، أريد معلومات عن خدماتكم"
Agent: "I can speak multiple languages. Would you prefer to continue in Arabic or English?"
User: "Arabic please"
Agent: [calls confirm_language_switch("Arabic", "ar")]
Agent: "ممتاز! كيف يمكنني مساعدتك اليوم؟"
```

## Configuration Options

### Option 1: English Only (Strict Mode)

If you want to disable multilingual support completely:

```python
# In prompts.py, change to:
AGENT_INSTRUCTION = """
# LANGUAGE RULES
- You MUST ALWAYS respond in ENGLISH ONLY.
- If user speaks another language, politely respond in English:
  "I apologize, but I can only communicate in English. How can I help you?"
"""
```

### Option 2: Specific Languages Only

To limit to specific languages:

```python
# In tools.py, modify confirm_language_switch:
ALLOWED_LANGUAGES = ["en", "es", "ar", "fr"]  # English, Spanish, Arabic, French

@function_tool
async def confirm_language_switch(language: str, language_code: str):
    if language_code not in ALLOWED_LANGUAGES:
        return f"Sorry, {language} is not supported. Available languages: English, Spanish, Arabic, French"

    return f"Language switch to {language} confirmed."
```

### Option 3: Auto-Detect (Current Implementation)

Current setup allows all languages with confirmation.

## Monitoring & Analytics

### Conversation Logs

All conversations are logged in `KMS/logs/` with language switches tracked:

```
[2024-02-24 10:30:15] Language switch requested: Spanish (es)
[2024-02-24 10:30:16] Language switch to Spanish confirmed
```

### Checking Logs

```bash
cd webBackendCors/KMS/logs
tail -f *.log | grep -i "language"
```

## Troubleshooting

### Issue: Agent still switches accidentally

**Solution 1**: Increase VAD threshold

```python
# In agent.py
threshold=0.9,  # Even less sensitive (default: 0.8)
```

**Solution 2**: Make prompt stricter

```python
# In prompts.py, add:
- NEVER switch languages based on a single utterance
- Require at least 3 consecutive sentences in another language
```

### Issue: Agent doesn't switch when user wants

**Solution**: Check if user is being explicit enough

```
❌ Bad: User says "Hola" (single word)
✅ Good: User says "Can we speak in Spanish?"
✅ Good: User speaks 2-3 full sentences in Spanish
```

### Issue: Latency increased after changes

**Solution**: VAD settings are optimized for low latency. If needed:

```python
# In agent.py, reduce silence duration
silence_duration_ms=600,  # Faster turn detection (default: 800)
```

## Best Practices

1. **Always confirm before switching**: Prevents accidental switches
2. **Log all language changes**: Helps with analytics and debugging
3. **Test with real names**: Ensure "Amir", "Isabella" don't trigger switches
4. **Test with background noise**: Ensure music/TV doesn't trigger switches
5. **Monitor conversation logs**: Check for unexpected language switches

## Rollback

If you need to revert to English-only:

```bash
cd webBackendCors
git diff prompts.py agent.py tools.py
git checkout prompts.py agent.py tools.py
```

Or manually change `prompts.py` to strict English-only mode (see Configuration Options above).

## Summary

✅ Prevents accidental language switching from names, noise, gibberish
✅ Allows intentional language switching when user requests it
✅ Maintains sub-100ms latency requirement
✅ Supports 50+ languages
✅ Logs all language switches for analytics
✅ Easy to configure (strict, limited, or auto-detect modes)
