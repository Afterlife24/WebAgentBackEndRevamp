from livekit.agents import function_tool, RunContext, get_job_context
import logging
import json

logger = logging.getLogger(__name__)


@function_tool
async def confirm_language_switch(language: str, language_code: str, context: RunContext) -> str:
    """
    Called when you want to confirm a language switch with the user.
    Use this ONLY when the user explicitly requests to speak in another language
    or consistently speaks 2-3 complete sentences in another language.

    DO NOT call this for:
    - Names in other languages
    - Single words or phrases
    - Background noise
    - Unclear audio

    Args:
        language: Full language name (e.g., "Spanish", "Arabic", "German")
        language_code: ISO language code (e.g., "es", "ar", "de")

    Returns:
        Confirmation that language switch is approved
    """
    logger.info(f"Language switch requested: {language} ({language_code})")

    # Log the language switch for analytics
    return f"Language switch to {language} confirmed. You may now respond in {language}. Remember to maintain the same helpful, professional tone."


@function_tool
async def open_url(url: str, context: RunContext) -> str:
    """
    Opens a URL in a new browser tab.
    Use this when the user explicitly asks to open an external website or link.
    This is for external URLs only - use navigate_to_section for internal navigation.
    """
    try:
        # Get the room from job context
        job_ctx = get_job_context()
        room = job_ctx.room

        # Get the first remote participant (the user)
        if not room.remote_participants:
            logger.warning("No remote participants found for open_url")
            return f"I tried to open {url}, but no user is connected."

        participant_identity = next(iter(room.remote_participants))

        navigation_data = {
            "type": "navigate",
            "action": "open_url",
            "url": url
        }

        # Use RPC to call the frontend method
        try:
            response = await room.local_participant.perform_rpc(
                destination_identity=participant_identity,
                method="navigate",
                payload=json.dumps(navigation_data),
                response_timeout=5.0
            )
            logger.info(
                f"Sent open URL command via RPC: {navigation_data}, response: {response}")
            return f"Opening {url} in a new tab."
        except Exception as rpc_error:
            logger.error(f"RPC call failed for open_url: {rpc_error}")
            return f"I tried to open {url}, but the navigation feature is currently unavailable."

    except Exception as e:
        logger.error(f"Failed to open URL: {str(e)}")
        return f"Failed to open {url}. Error: {str(e)}"


@function_tool
async def navigate_to_section(section: str, context: RunContext) -> str:
    """
    Navigates to a specific section or page on the Afterlife website IN THE SAME TAB where the user is interacting.
    This provides a seamless experience without opening new tabs.

    Available sections:
    - "home" or "products": Main page with all three agent products
    - "voice" or "calling": Voice/Calling Agent section on home page
    - "web": Web Agent section on home page
    - "whatsapp": WhatsApp Agent section on home page
    - "vision": Vision section (company mission and values)
    - "services": Services section (what we offer)
    - "testimonials": Customer testimonials section
    - "pricing": Pricing page
    - "about": About us page

    Use this tool when users ask about specific features, products, or want to learn more about Afterlife.
    The navigation happens in the same tab, so the user stays in context with the agent.

    Args:
        section: The section name to navigate to (e.g., "voice", "pricing", "about")

    Returns:
        A message indicating the navigation action
    """
    section = section.lower().strip()

    # Map sections to React Router paths and descriptions
    section_map = {
        "home": ("/", "home page", None),
        "products": ("/", "products section", None),
        "voice": ("/", "Voice/Calling Agent section", "voice"),
        "calling": ("/", "Voice/Calling Agent section", "voice"),
        "web": ("/", "Web Agent section", "web"),
        "whatsapp": ("/", "WhatsApp Agent section", "whatsapp"),
        "vision": ("/", "Vision section", "vision"),
        "services": ("/", "Services section", "services"),
        "testimonials": ("/", "Testimonials section", "testimonials"),
        "pricing": ("/pricing", "Pricing page", None),
        "about": ("/about", "About page", None),
    }

    if section not in section_map:
        available = ", ".join(section_map.keys())
        return f"Unknown section '{section}'. Available sections: {available}"

    path, description, scroll_to = section_map[section]

    try:
        # Get the room from job context
        job_ctx = get_job_context()
        room = job_ctx.room

        # Get the first remote participant (the user)
        if not room.remote_participants:
            logger.warning(
                "No remote participants found for navigate_to_section")
            return f"I can help you navigate to the {description}, but no user is connected."

        participant_identity = next(iter(room.remote_participants))

        navigation_data = {
            "type": "navigate",
            "action": "navigate_same_tab",
            "path": path,
            "section": scroll_to,
            "description": description
        }

        # Use RPC to call the frontend method
        try:
            response = await room.local_participant.perform_rpc(
                destination_identity=participant_identity,
                method="navigate",
                payload=json.dumps(navigation_data),
                response_timeout=5.0
            )
            logger.info(
                f"Sent same-tab navigation command via RPC: {navigation_data}, response: {response}")
            return f"Navigating to the {description}. The page will update shortly."
        except Exception as rpc_error:
            logger.error(
                f"RPC call failed for navigate_to_section: {rpc_error}")
            return f"I can help you navigate to the {description}, but the navigation feature is currently unavailable. You can manually navigate using the menu."

    except Exception as e:
        logger.error(f"Failed to send navigation command: {str(e)}")
        return f"I tried to navigate to the {description}, but encountered an issue. You can manually navigate using the menu."
