from livekit.agents import function_tool, RunContext
import logging
import json

logger = logging.getLogger(__name__)

# Product catalog — loaded once, served on-demand via tool call instead of
# bloating the system prompt with ~150 tokens every single LLM turn.
PRODUCT_CATALOG: dict[str, dict[str, str | list[str]]] = {
    "telecalling": {
        "name": "Telecalling Agent",
        "description": "Customers or leads call a phone number and speak directly with an AI agent using natural conversation.",
        "capabilities": [
            "Inbound and outbound calls",
            "Natural human-friendly voice",
            "Lead collection and qualification",
            "Appointment scheduling",
            "Product/service explanations",
            "24/7 availability",
            "CRM and workflow integration",
        ],
        "best_for": [
            "Customer support automation",
            "Lead qualification",
            "Appointment booking",
            "Sales follow-ups",
            "Call-heavy operations",
        ],
    },
    "web": {
        "name": "Web Agent",
        "description": "An interactive AI avatar on a company's website that helps users navigate and interact using voice or chat.",
        "capabilities": [
            "Guides visitors across the website",
            "Automatic page navigation",
            "Answers product/service questions",
            "Improves engagement and reduces bounce rate",
            "Converts visitors into leads",
            "Interactive browsing without manual typing",
        ],
        "best_for": [
            "E-commerce websites",
            "SaaS platforms",
            "Information-heavy websites",
            "Businesses wanting higher engagement and conversions",
        ],
    },
    "whatsapp": {
        "name": "WhatsApp Agent",
        "description": "Customers interact with businesses directly through WhatsApp using AI-driven automated conversation.",
        "capabilities": [
            "Instant customer support on WhatsApp",
            "FAQ handling",
            "Order and service request intake",
            "Updates and notifications",
            "Lead generation",
            "Multilingual conversation",
            "24/7 automated response",
        ],
        "best_for": [
            "E-commerce stores",
            "Service providers",
            "Local businesses",
            "Customer engagement and retention",
        ],
    },
}


@function_tool
async def get_product_info(product: str) -> str:
    """
    Get details about an Autonomiq AI agent product.
    Call with product = "telecalling", "web", "whatsapp", or "all".
    """
    product = product.lower().strip()
    logger.info(f"[TOOL] get_product_info called with product: {product}")

    if product == "all":
        lines: list[str] = []
        for key, info in PRODUCT_CATALOG.items():
            lines.append(f"{info['name']}: {info['description']}")
        return " | ".join(lines)

    info = PRODUCT_CATALOG.get(product)
    if not info:
        available = ", ".join(PRODUCT_CATALOG.keys())
        return f"Unknown product '{product}'. Available: {available}, or 'all'."

    caps = ", ".join(str(c) for c in info["capabilities"])
    fits = ", ".join(str(f) for f in info["best_for"])
    return f"{info['name']}: {info['description']} Capabilities: {caps}. Best for: {fits}."


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
    Open an external URL in the user's browser.
    Only for non-Autonomiq websites. For Autonomiq pages use navigate_to_section.
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
    Navigate to a page on the Autonomiq website.
    Use for all internal navigation. Ask permission first.

    The home page is a fullscreen 3D avatar landing — it has NO content sections.
    All content lives on separate pages.

    section must be one of: home, about, ai-assistants, teams, voice, calling,
    web, whatsapp, demo, ai-workforce, whatsapp-agent, web-agent, industries,
    solutions, additional-services, careers, blog.
    """
    section = section.lower().strip()
    logger.info(f"[TOOL] navigate_to_section called with section: {section}")

    # Map sections to (path, section_id, description)
    # path = React Router path, section_id = optional id for scroll within that page
    # Home ("/") has NO sections — it's just the avatar landing.
    section_map = {
        "home": ("/", None, "home page (avatar landing)"),
        "about": ("/about", None, "About page"),
        "vision": ("/about", None, "About page (includes company vision)"),
        "ai-assistants": ("/ai-assistants", None, "AI Assistants page"),
        "teams": ("/ai-assistants", None, "AI Assistants page"),
        "products": ("/ai-assistants", None, "AI Assistants page (product overview)"),
        "voice": ("/ai-assistants", None, "AI Assistants page (Voice/Calling Agent)"),
        "calling": ("/ai-assistants", None, "AI Assistants page (Voice/Calling Agent)"),
        "web": ("/ai-assistants", None, "AI Assistants page (Web Agent)"),
        "whatsapp": ("/ai-assistants", None, "AI Assistants page (WhatsApp Agent)"),
        "meet-assistants": ("/ai-assistants", None, "AI Assistants page"),
        "demo": ("/ai-assistants", "demo", "Featured Real Estate Demo section"),
        "ai-workforce": ("/ai-assistants", "ai-workforce", "AI Workforce grid"),
        "whatsapp-agent": ("/ai-assistants", "whatsapp-agent", "WhatsApp Agent details section"),
        "web-agent": ("/ai-assistants", "web-agent", "Web Agent details section"),
        "industries": ("/ai-assistants", "industries", "Industries section"),
        "services": ("/solutions", None, "Solutions page"),
        "solutions": ("/solutions", None, "Solutions page"),
        "additional-services": ("/solutions", None, "Solutions page"),
        "testimonials": ("/about", None, "About page (includes testimonials)"),
        "careers": ("/careers", None, "Careers page"),
        "blog": ("/blog", None, "Blog page"),
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
