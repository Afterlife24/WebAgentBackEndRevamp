from livekit.agents import function_tool, RunContext
import webbrowser


@function_tool
async def open_url(url: str, context: RunContext) -> str:
    """
    Opens a URL in the user's default web browser.
    Use this when the user explicitly asks to open an external website or link.
    """
    try:
        webbrowser.open(url)
        return f"Opened {url} in your web browser."
    except Exception as e:
        return f"Failed to open {url}. Error: {str(e)}"


@function_tool
async def navigate_to_section(section: str, context: RunContext) -> str:
    """
    Navigates to a specific section or page on the Afterlife website.

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
    Always ask for user permission before navigating.

    Args:
        section: The section name to navigate to (e.g., "voice", "pricing", "about")

    Returns:
        A message indicating the navigation action
    """
    section = section.lower().strip()

    # Map sections to URLs and descriptions
    section_map = {
        "home": ("http://localhost:3000", "home page"),
        "products": ("http://localhost:3000", "products section"),
        "voice": ("http://localhost:3000?action=expand&section=voice", "Voice/Calling Agent section with details expanded"),
        "calling": ("http://localhost:3000?action=expand&section=voice", "Voice/Calling Agent section with details expanded"),
        "web": ("http://localhost:3000?action=expand&section=web", "Web Agent section with details expanded"),
        "whatsapp": ("http://localhost:3000?action=expand&section=whatsapp", "WhatsApp Agent section with details expanded"),
        "vision": ("http://localhost:3000?action=scroll&section=vision", "Vision section"),
        "services": ("http://localhost:3000?action=scroll&section=services", "Services section"),
        "testimonials": ("http://localhost:3000?action=scroll&section=testimonials", "Testimonials section"),
        "pricing": ("http://localhost:3000/pricing", "Pricing page"),
        "about": ("http://localhost:3000/about", "About page"),
    }

    if section not in section_map:
        available = ", ".join(section_map.keys())
        return f"Unknown section '{section}'. Available sections: {available}"

    url, description = section_map[section]

    try:
        webbrowser.open(url)
        return f"Navigated to the {description}. The page should now be open and automatically showing the relevant content."
    except Exception as e:
        return f"Failed to navigate to {description}. Error: {str(e)}"
