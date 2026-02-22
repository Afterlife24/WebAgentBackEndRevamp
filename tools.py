from livekit.agents import function_tool, RunContext
import logging
import json

logger = logging.getLogger(__name__)


@function_tool
async def open_url(url: str, context: RunContext) -> str:
    """
    Opens a URL in the user's default web browser.
    
    IMPORTANT: Use this ONLY for external websites or links that are NOT part of the Afterlife website.
    DO NOT use this tool for internal Afterlife pages like pricing, about, home, or any sections.
    For internal Afterlife website pages, ALWAYS use the navigate_to_section tool instead.
    
    Examples of when to use this:
    - User asks to open an external website (e.g., "open google.com")
    - User provides a specific external URL
    
    Examples of when NOT to use this:
    - User asks about pricing → Use navigate_to_section("pricing") instead
    - User asks about the company → Use navigate_to_section("about") instead
    - User wants to see any Afterlife page → Use navigate_to_section() instead
    """
    try:
        logger.info(f"[TOOL] open_url called with URL: {url}")
        
        # Get room from context.session._room_io
        if hasattr(context, 'session') and hasattr(context.session, '_room_io'):
            room_io = context.session._room_io
            room = room_io.room
            logger.info(f"[TOOL] Room found: {room.name}")
            
            # Send data message to all participants
            await room.local_participant.publish_data(
                json.dumps({
                    "type": "navigate",
                    "action": "open_url",
                    "url": url
                }).encode('utf-8'),
                reliable=True
            )
            logger.info(f"[TOOL] Successfully sent navigation command for URL: {url}")
            return f"Opening {url} in your web browser now."
        else:
            logger.error(f"[TOOL] No session._room_io found in context")
            return f"Unable to open {url}. Please try clicking this link manually: {url}"
    except Exception as e:
        logger.error(f"[TOOL] Error in open_url: {str(e)}", exc_info=True)
        return f"Failed to open {url}. Error: {str(e)}"


@function_tool
async def navigate_to_section(section: str, context: RunContext) -> str:
    """
    Navigates to a specific section or page on the Afterlife website (https://www.novaflux.afterlife.org.in/).
    
    CRITICAL: This is the PRIMARY tool to use when users ask to open, view, or navigate to ANY page
    on the Afterlife website. ALWAYS use this tool for internal pages, NEVER use open_url or web search.
    
    Available sections:
    - "home" or "products": Main page with all three agent products (https://www.novaflux.afterlife.org.in/)
    - "voice" or "calling": Voice/Calling Agent section on home page
    - "web": Web Agent section on home page
    - "whatsapp": WhatsApp Agent section on home page
    - "vision": Vision section (company mission and values)
    - "services": Services section (what we offer)
    - "testimonials": Customer testimonials section
    - "pricing": Pricing page (https://www.novaflux.afterlife.org.in//pricing) - USE THIS when user asks about pricing
    - "about": About us page (https://www.novaflux.afterlife.org.in//about) - USE THIS when user asks about the company
    
    When to use this tool:
    - User asks to "open pricing page" → Use navigate_to_section("pricing")
    - User asks about "pricing" → Use navigate_to_section("pricing")
    - User asks to "see pricing" → Use navigate_to_section("pricing")
    - User asks about "about us" or company info → Use navigate_to_section("about")
    - User asks about any Afterlife product or feature → Use navigate_to_section() with appropriate section
    - User wants to navigate to any page on the Afterlife website → Use this tool
    
    Always ask for user permission before navigating.

    Args:
        section: The section name to navigate to (e.g., "voice", "pricing", "about")

    Returns:
        A message indicating the navigation action
    """
    section = section.lower().strip()
    
    logger.info(f"[TOOL] navigate_to_section called with section: {section}")

    # Map sections to URLs and descriptions
    section_map = {
        "home": ("https://www.novaflux.afterlife.org.in/", "home page"),
        "products": ("https://www.novaflux.afterlife.org.in/", "products section"),
        "voice": ("https://www.novaflux.afterlife.org.in/?action=expand&section=voice", "Voice/Calling Agent section with details expanded"),
        "calling": ("https://www.novaflux.afterlife.org.in/?action=expand&section=voice", "Voice/Calling Agent section with details expanded"),
        "web": ("https://www.novaflux.afterlife.org.in/?action=expand&section=web", "Web Agent section with details expanded"),
        "whatsapp": ("https://www.novaflux.afterlife.org.in/?action=expand&section=whatsapp", "WhatsApp Agent section with details expanded"),
        "vision": ("https://www.novaflux.afterlife.org.in/?action=scroll&section=vision", "Vision section"),
        "services": ("https://www.novaflux.afterlife.org.in/?action=scroll&section=services", "Services section"),
        "testimonials": ("https://www.novaflux.afterlife.org.in/?action=scroll&section=testimonials", "Testimonials section"),
        "pricing": ("https://www.novaflux.afterlife.org.in/pricing", "Pricing page"),
        "about": ("https://www.novaflux.afterlife.org.in/about", "About page"),
    }

    if section not in section_map:
        available = ", ".join(section_map.keys())
        logger.warning(f"[TOOL] Unknown section requested: {section}")
        return f"Unknown section '{section}'. Available sections: {available}"

    url, description = section_map[section]
    logger.info(f"[TOOL] Mapped section '{section}' to URL: {url}")

    try:
        # Get room from context.session._room_io
        if hasattr(context, 'session') and hasattr(context.session, '_room_io'):
            room_io = context.session._room_io
            room = room_io.room
            logger.info(f"[TOOL] Room found: {room.name}")
            
            # Send data message to all participants
            await room.local_participant.publish_data(
                json.dumps({
                    "type": "navigate",
                    "action": "navigate_to_section",
                    "section": section,
                    "url": url,
                    "description": description
                }).encode('utf-8'),
                reliable=True
            )
            logger.info(f"[TOOL] Successfully sent navigation command for section: {section}")
            return f"SUCCESS: Navigating to {description}. Now describe what the user should see on this page and guide them through the content."
        else:
            logger.error(f"[TOOL] No session._room_io found in context")
            return f"Unable to navigate automatically. Please click this link: {url}"
    except Exception as e:
        logger.error(f"[TOOL] Error in navigate_to_section: {str(e)}", exc_info=True)
        return f"ERROR: Failed to navigate to {description}. Error: {str(e)}. Apologize to the user and offer an alternative."
