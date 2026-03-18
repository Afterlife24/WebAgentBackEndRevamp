from livekit.agents import function_tool, RunContext
import logging
import json

logger = logging.getLogger(__name__)


def _get_room_and_remote_identity(context: RunContext):
    """Helper to extract room and remote participant identity from context."""
    if not (hasattr(context, 'session') and hasattr(context.session, '_room_io')):
        return None, None
    room = context.session._room_io.room
    remote_identity = None
    for p in room.remote_participants.values():
        remote_identity = p.identity
        break
    return room, remote_identity


@function_tool
async def open_url(url: str, context: RunContext) -> str:
    """
    Opens a URL in the user's default web browser.

    IMPORTANT: Use this ONLY for external websites or links that are NOT part of the Afterlife website.
    DO NOT use this tool for internal Afterlife pages like about, home, ai-assistants, or any sections.
    For internal Afterlife website pages, ALWAYS use the navigate_to_section tool instead.

    Examples of when to use this:
    - User asks to open an external website (e.g., "open google.com")
    - User provides a specific external URL

    Examples of when NOT to use this:
    - User asks about the company → Use navigate_to_section("about") instead
    - User asks about AI assistants or the team → Use navigate_to_section("ai-assistants") instead
    - User wants to see any Afterlife page → Use navigate_to_section() instead
    """
    try:
        logger.info(f"[TOOL] open_url called with URL: {url}")

        room, remote_identity = _get_room_and_remote_identity(context)

        if not room or not remote_identity:
            logger.error("[TOOL] No room or remote participant found")
            return f"Unable to open {url}. Please try clicking this link manually: {url}"

        logger.info(f"[TOOL] Room: {room.name}, remote: {remote_identity}")

        payload = json.dumps({
            "type": "navigate",
            "action": "open_url",
            "url": url
        })
        await room.local_participant.perform_rpc(
            destination_identity=remote_identity,
            method="navigate",
            payload=payload
        )
        logger.info(f"[TOOL] RPC navigate sent for URL: {url}")
        return f"Opening {url} in your web browser now."
    except Exception as e:
        logger.error(f"[TOOL] Error in open_url: {str(e)}", exc_info=True)
        return f"Failed to open {url}. Error: {str(e)}"


@function_tool
async def navigate_to_section(section: str, context: RunContext) -> str:
    """
    Navigates to a specific section or page on the Afterlife website.

    CRITICAL: This is the PRIMARY tool to use when users ask to open, view, or navigate to ANY page
    on the Afterlife website. ALWAYS use this tool for internal pages, NEVER use open_url or web search.

    Available sections:
    - "home" or "products": Main page with all three agent products
    - "voice" or "calling": Voice/Calling Agent section on home page
    - "web": Web Agent section on home page
    - "whatsapp": WhatsApp Agent section on home page
    - "vision": Vision section (company mission and values)
    - "services": Services section (what we offer)
    - "testimonials": Customer testimonials section
    - "about": About us page - USE THIS when user asks about the company
    - "ai-assistants" or "teams": AI Assistants page showcasing the AI workforce
    - "meet-assistants": Meet Our AI Assistants CTA banner on the home page
    - "demo": Featured Real Estate Demo section on AI Assistants page
    - "ai-workforce": AI Workforce grid (receptionist, admin, sales agents) on AI Assistants page
    - "whatsapp-agent": WhatsApp Agent details section on AI Assistants page
    - "web-agent": Web Agent details section on AI Assistants page
    - "industries": Industries section on AI Assistants page

    When to use this tool:
    - User asks about "about us" or company info → Use navigate_to_section("about")
    - User asks about AI assistants, the team, or workforce → Use navigate_to_section("ai-assistants")
    - User asks about any Afterlife product or feature → Use navigate_to_section() with appropriate section
    - User wants to navigate to any page on the Afterlife website → Use this tool

    Always ask for user permission before navigating.

    Args:
        section: The section name to navigate to (e.g., "voice", "ai-assistants", "about")

    Returns:
        A message indicating the navigation action
    """
    section = section.lower().strip()
    logger.info(f"[TOOL] navigate_to_section called with section: {section}")

    # Map sections to (path, section_id, description)
    # path = React Router path, section_id = optional id for scroll/expand
    section_map = {
        "home": ("/", None, "home page"),
        "products": ("/", None, "products section"),
        "voice": ("/", "voice", "Voice/Calling Agent section"),
        "calling": ("/", "voice", "Voice/Calling Agent section"),
        "web": ("/", "web", "Web Agent section"),
        "whatsapp": ("/", "whatsapp", "WhatsApp Agent section"),
        "vision": ("/", "vision", "Vision section"),
        "services": ("/", "services", "Services section"),
        "testimonials": ("/", "testimonials", "Testimonials section"),
        "about": ("/about", None, "About page"),
        "ai-assistants": ("/ai-assistants", None, "AI Assistants page"),
        "teams": ("/ai-assistants", None, "AI Assistants page"),
        "meet-assistants": ("/", "meet-assistants", "Meet Our AI Assistants section"),
        "demo": ("/ai-assistants", "demo", "Featured Real Estate Demo section"),
        "ai-workforce": ("/ai-assistants", "ai-workforce", "AI Workforce grid"),
        "whatsapp-agent": ("/ai-assistants", "whatsapp-agent", "WhatsApp Agent details section"),
        "web-agent": ("/ai-assistants", "web-agent", "Web Agent details section"),
        "industries": ("/ai-assistants", "industries", "Industries section"),
    }

    if section not in section_map:
        available = ", ".join(section_map.keys())
        logger.warning(f"[TOOL] Unknown section: {section}")
        return f"Unknown section '{section}'. Available sections: {available}"

    path, section_id, description = section_map[section]
    logger.info(f"[TOOL] Mapped to path={path}, section_id={section_id}")

    try:
        room, remote_identity = _get_room_and_remote_identity(context)

        if not room or not remote_identity:
            logger.error("[TOOL] No room or remote participant found")
            return f"Unable to navigate automatically. Please go to the {description} manually."

        logger.info(f"[TOOL] Room: {room.name}, remote: {remote_identity}")

        # Build payload matching frontend NavigationHandler expectations
        payload_data = {
            "type": "navigate",
            "action": "navigate_same_tab",
            "path": path,
        }
        if section_id:
            payload_data["section"] = section_id

        await room.local_participant.perform_rpc(
            destination_identity=remote_identity,
            method="navigate",
            payload=json.dumps(payload_data)
        )
        logger.info(f"[TOOL] RPC navigate sent for section: {section}")
        return f"SUCCESS: Navigating to {description}. Now describe what the user should see on this page and guide them through the content."
    except Exception as e:
        logger.error(
            f"[TOOL] Error in navigate_to_section: {str(e)}", exc_info=True)
        return f"ERROR: Failed to navigate to {description}. Error: {str(e)}. Apologize to the user and offer an alternative."
