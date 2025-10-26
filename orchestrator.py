"""
Workflow Orchestrator
Central coordinator for executing workflows and calling utility functions.
"""

import logging
from typing import Dict, Any, List
import importlib

from services.supabase_service import SupabaseService
from utils.gcalendar_slack_utils import GCalendarSlackUtils
from utils.gmail_calendar_utils import GmailCalendarUtils
from utils.gmail_gdrive_utils import GmailGDriveUtils
from utils.notion_discord_utils import NotionDiscordUtils
from utils.notion_gmail_utils import NotionGmailUtils
from utils.notion_slack_utils import NotionSlackUtils

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """Orchestrates workflow execution by coordinating utility function calls."""

    def __init__(self, supabase_service: SupabaseService):
        self.supabase = supabase_service

        self.utils_registry = {
            "gmail_calendar": GmailCalendarUtils,
            "gmail_gdrive": GmailGDriveUtils,
            "notion_slack": NotionSlackUtils,
            "notion_gmail": NotionGmailUtils,
            "notion_discord": NotionDiscordUtils,
            "gcalendar_slack": GCalendarSlackUtils,
        }

        logger.info(
            f"Orchestrator initialized with {len(self.utils_registry)} utility modules"
        )

    async def execute_workflow(
        self,
        workflow: Dict[str, Any],
        credentials: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a workflow by calling appropriate utility functions.

        Args:
            workflow: Workflow definition with name, description, required_apps
            credentials: User's app credentials
            parameters: Execution parameters

        Returns:
            Dict with execution results
        """
        try:
            workflow_name = workflow.get("name", "").lower()
            required_apps = workflow.get("required_apps", [])

            logger.info(f"Executing workflow: {workflow_name}")
            logger.info(f"Required apps: {required_apps}")

            # Determine which utility module to use based on required apps
            util_key = self._determine_util_module(required_apps)

            if not util_key:
                return {
                    "success": False,
                    "error": f"No utility module found for apps: {required_apps}",
                }

            util_class = self.utils_registry.get(util_key)
            if not util_class:
                return {
                    "success": False,
                    "error": f"Utility module '{util_key}' not registered",
                }

            # Initialize utility class with credentials
            util_instance = util_class(credentials)

            # Execute based on workflow type
            result = await self._execute_workflow_logic(
                util_instance=util_instance, workflow=workflow, parameters=parameters
            )

            logger.info(f"Workflow execution completed: {result.get('success')}")
            return result

        except Exception as e:
            logger.error(f"Error executing workflow: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _determine_util_module(self, required_apps: List[str]) -> str:
        """
        Determine which utility module to use based on required apps.

        Args:
            required_apps: List of required app names

        Returns:
            Utility module key
        """
        # Normalize app names
        apps = [app.lower() for app in required_apps]
        apps_set = set(apps)

        # Check for known combinations
        if {"gmail", "google calendar"}.issubset(apps_set):
            return "gmail_calendar"
        elif {"gmail", "google drive"}.issubset(apps_set):
            return "gmail_gdrive"
        elif {"notion", "slack"}.issubset(apps_set):
            return "notion_slack"
        elif {"notion", "gmail"}.issubset(apps_set):
            return "notion_gmail"
        elif {"notion", "discord"}.issubset(apps_set):
            return "notion_discord"
        elif {"google calendar", "slack"}.issubset(apps_set):
            return "gcalendar_slack"

        # Add more combinations as needed
        return None

    async def _execute_workflow_logic(
        self, util_instance: Any, workflow: Dict[str, Any], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the actual workflow logic using the utility instance.

        Args:
            util_instance: Initialized utility class instance
            workflow: Workflow definition
            parameters: Execution parameters

        Returns:
            Execution results
        """
        workflow_name_lower = workflow.get("name", "").lower()

        # Gmail/Email → Calendar workflows
        if (
            any(word in workflow_name_lower for word in ["gmail", "email"])
            and "calendar" in workflow_name_lower
        ):
            return await util_instance.emails_to_calendar_events(
                max_emails=parameters.get("max_emails", 10),
                query=parameters.get("query", "is:unread"),
                sender_email=parameters.get("sender_email"),
                email_subject=parameters.get("email_title"),
                email_labels=parameters.get("email_labels"),
                include_archived=parameters.get("include_archived", False),
                date_from=parameters.get("date_from"),
                date_to=parameters.get("date_to"),
            )

        # Gmail/Email → Drive workflows
        elif (
            any(word in workflow_name_lower for word in ["gmail", "email"])
            and "drive" in workflow_name_lower
        ):
            return await util_instance.save_attachments_to_drive(
                max_emails=parameters.get("max_emails", 10),
                folder_name=parameters.get("folder_name", "Email Attachments"),
                sender_email=parameters.get("sender_email"),
                email_labels=parameters.get("email_labels"),
                file_types=parameters.get("file_types"),
                min_file_size_kb=parameters.get("min_file_size_kb"),
                max_file_size_kb=parameters.get("max_file_size_kb"),
                date_from=parameters.get("date_from"),
                date_to=parameters.get("date_to"),
            )

        # Notion → Slack workflows
        elif "notion" in workflow_name_lower and "slack" in workflow_name_lower:
            return await util_instance.notion_pages_to_slack_messages(
                database_id=parameters.get("database_id"),
                channel=parameters.get("channel"),
                filter=parameters.get("filter"),
                max_pages=parameters.get("max_pages", 10),
            )

        # Notion → Gmail workflows
        elif "notion" in workflow_name_lower and any(
            word in workflow_name_lower for word in ["gmail", "email"]
        ):
            return await util_instance.notion_pages_to_emails(
                database_id=parameters.get("database_id"),
                recipient_email=parameters.get("recipient_email"),
                filter=parameters.get("filter"),
                max_pages=parameters.get("max_pages", 10),
            )

        # Notion → Discord workflows
        elif "notion" in workflow_name_lower and "discord" in workflow_name_lower:
            return await util_instance.notion_pages_to_discord_messages(
                database_id=parameters.get("database_id"),
                channel_id=parameters.get("channel_id"),
                filter=parameters.get("filter"),
                max_pages=parameters.get("max_pages", 10),
            )

        # Google Calendar → Slack workflows
        elif "calendar" in workflow_name_lower and "slack" in workflow_name_lower:
            return await util_instance.calendar_events_to_slack_messages(
                channel=parameters.get("channel"),
                time_min=parameters.get("time_min"),
                time_max=parameters.get("time_max"),
                max_events=parameters.get("max_events", 10),
            )

        # Add more workflow routing logic as needed
        return {
            "success": False,
            "error": f"No execution logic defined for workflow: {workflow_name_lower}",
        }
