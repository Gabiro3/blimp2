"""
Central registry of all available helper functions.
Used by Gemini to understand what operations are available.
"""

from helpers.gdrive_helpers import GDRIVE_FUNCTIONS
from helpers.gmail_helpers import GMAIL_FUNCTIONS
from helpers.gcalendar_helpers import GCALENDAR_FUNCTIONS
from helpers.google_docs_helpers import GOOGLE_DOCS_FUNCTIONS
from helpers.notion_helpers import NOTION_FUNCTIONS
from helpers.slack_helpers import SLACK_FUNCTIONS
from helpers.discord_helpers import DISCORD_FUNCTIONS
from helpers.trello_helpers import TRELLO_FUNCTIONS
from helpers.github_helpers import GITHUB_FUNCTIONS


# Map app names to their function registries
FUNCTION_REGISTRY = {
    "gmail": GMAIL_FUNCTIONS,
    "google_calendar": GCALENDAR_FUNCTIONS,
    "notion": NOTION_FUNCTIONS,
    "slack": SLACK_FUNCTIONS,
    "google_drive": GDRIVE_FUNCTIONS,
    "google_docs": GOOGLE_DOCS_FUNCTIONS,
    "discord": DISCORD_FUNCTIONS,
    "trello": TRELLO_FUNCTIONS,
    "github": GITHUB_FUNCTIONS,
}


def get_functions_for_apps(app_names: list[str]) -> dict:
    """
    Get function registry for specified apps.

    Args:
        app_names: List of app names (e.g., ["gmail", "gcalendar"])

    Returns:
        Dict mapping app names to their available functions
    """
    return {app: FUNCTION_REGISTRY.get(app.lower(), {}) for app in app_names}
