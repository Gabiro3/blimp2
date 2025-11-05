"""
Team Workflow Orchestrator
Handles complex team workflow execution with advanced filtering and member management
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.supabase_service import SupabaseService
from services.email_service import EmailService
from utils.gmail_calendar_utils import GmailCalendarUtils
from utils.gmail_gdrive_utils import GmailGDriveUtils
from utils.notion_slack_utils import NotionSlackUtils
from utils.notion_gmail_utils import NotionGmailUtils
from utils.notion_discord_utils import NotionDiscordUtils
from utils.gcalendar_slack_utils import GCalendarSlackUtils

logger = logging.getLogger(__name__)


class TeamWorkflowOrchestrator:
    """Orchestrates team workflow execution with complex filtering and member coordination"""

    def __init__(self, supabase_service: SupabaseService, email_service: EmailService):
        self.supabase = supabase_service
        self.email_service = email_service

        self.utils_registry = {
            "gmail_calendar": GmailCalendarUtils,
            "gmail_gdrive": GmailGDriveUtils,
            "notion_slack": NotionSlackUtils,
            "notion_gmail": NotionGmailUtils,
            "notion_discord": NotionDiscordUtils,
            "gcalendar_slack": GCalendarSlackUtils,
        }

        logger.info(
            f"Team Orchestrator initialized with {len(self.utils_registry)} utility modules"
        )

    async def execute_team_workflow(
        self, workflow_id: str, admin_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a team workflow for all members

        Args:
            workflow_id: Team workflow ID
            admin_id: Admin user ID
            parameters: Execution parameters with filters

        Returns:
            Dict with execution results for all members
        """
        try:
            # Get team workflow details
            workflow = await self.supabase.get_team_workflow(workflow_id)
            if not workflow:
                return {"success": False, "error": "Team workflow not found"}

            # Get all team members
            members = workflow.get("members_json", [])
            if not members:
                return {"success": False, "error": "No team members found"}

            logger.info(f"Executing team workflow for {len(members)} members")

            # Parse workflow JSON
            workflow_json = workflow.get("workflow_json", {})
            steps = workflow_json.get("steps", [])

            # Determine required apps from steps
            required_apps = self._extract_required_apps(steps)

            # Apply complex filters based on parameters
            filtered_params = self._apply_complex_filters(parameters, required_apps)

            # Execute workflow for each member
            results = []
            errors = []

            for member in members:
                member_id = member.get("user_id")

                try:
                    # Get member credentials
                    member_creds = await self._get_member_credentials(
                        member_id, required_apps
                    )

                    if not member_creds:
                        errors.append(f"Missing credentials for member {member_id}")
                        continue

                    # Execute workflow for this member
                    result = await self._execute_for_member(
                        member_id=member_id,
                        workflow=workflow,
                        credentials=member_creds,
                        parameters=filtered_params,
                        required_apps=required_apps,
                    )

                    results.append({"member_id": member_id, "result": result})

                except Exception as e:
                    logger.error(f"Error executing for member {member_id}: {str(e)}")
                    errors.append(f"Member {member_id}: {str(e)}")

            # Send notifications if configured
            await self._send_team_notifications(
                workflow=workflow,
                parameters=parameters,
                results=results,
                admin_id=admin_id,
            )

            return {
                "success": True,
                "workflow_id": workflow_id,
                "members_processed": len(results),
                "results": results,
                "errors": errors,
                "message": f"Team workflow executed for {len(results)} members",
            }

        except Exception as e:
            logger.error(f"Error executing team workflow: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _extract_required_apps(self, steps: List[Dict[str, Any]]) -> List[str]:
        """Extract required apps from workflow steps"""
        apps = set()
        for step in steps:
            app_type = step.get("app_type", "")
            if app_type and app_type != "Trigger":
                apps.add(app_type)
        return list(apps)

    def _apply_complex_filters(
        self, parameters: Dict[str, Any], required_apps: List[str]
    ) -> Dict[str, Any]:
        """
        Apply complex filters based on app types and parameters

        Handles Gmail filters, Calendar filters, Slack filters, etc.
        """
        filtered_params = parameters.copy()

        if "Gmail" in required_apps:
            filtered_params = self._apply_gmail_filters(filtered_params)

        if "Google Calendar" in required_apps:
            filtered_params = self._apply_calendar_filters(filtered_params)

        if "Slack" in required_apps:
            filtered_params = self._apply_slack_filters(filtered_params)

        if "Notion" in required_apps:
            filtered_params = self._apply_notion_filters(filtered_params)

        if "Google Drive" in required_apps:
            filtered_params = self._apply_gdrive_filters(filtered_params)

        return filtered_params

    def _apply_gmail_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply complex Gmail filters

        Supports:
        - Sender email filtering
        - Subject filtering
        - Label filtering
        - Date range filtering
        - File type filtering (for attachments)
        - File size filtering
        - Read/unread status
        - Archived/inbox status
        """
        gmail_params = params.copy()

        # Build Gmail query string from filters
        query_parts = []

        # Sender filter
        if params.get("filter_sender"):
            query_parts.append(f"from:{params['filter_sender']}")

        # Subject filter
        if params.get("filter_subject"):
            query_parts.append(f"subject:{params['filter_subject']}")

        # Label filter
        if params.get("email_labels"):
            labels = params["email_labels"]
            if isinstance(labels, list):
                for label in labels:
                    query_parts.append(f"label:{label}")
            else:
                query_parts.append(f"label:{labels}")

        # Date range filter
        if params.get("date_from"):
            query_parts.append(f"after:{params['date_from']}")
        if params.get("date_to"):
            query_parts.append(f"before:{params['date_to']}")

        # Read/unread filter
        if params.get("only_unread", False):
            query_parts.append("is:unread")

        # Archived filter
        if not params.get("include_archived", True):
            query_parts.append("in:inbox")

        # Has attachment filter
        if params.get("has_attachment", False):
            query_parts.append("has:attachment")

        # File type filter (for attachment workflows)
        if params.get("file_types"):
            file_types = params["file_types"]
            if isinstance(file_types, list):
                for file_type in file_types:
                    query_parts.append(f"filename:{file_type}")

        # Combine all query parts
        if query_parts:
            gmail_params["query"] = " ".join(query_parts)
        else:
            gmail_params["query"] = params.get("query", "")

        # Add file size filters (processed separately in utility functions)
        if params.get("min_file_size_kb"):
            gmail_params["min_file_size_kb"] = params["min_file_size_kb"]
        if params.get("max_file_size_kb"):
            gmail_params["max_file_size_kb"] = params["max_file_size_kb"]

        # Max emails limit
        gmail_params["max_emails"] = params.get("max_emails", 10)

        logger.info(f"Applied Gmail filters: query='{gmail_params.get('query')}'")

        return gmail_params

    def _apply_calendar_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Google Calendar filters

        Supports:
        - Time range filtering
        - Calendar ID (for team calendars)
        - Event visibility
        - Attendee notifications
        """
        calendar_params = params.copy()

        # Team calendar ID
        if params.get("team_calendar_id"):
            calendar_params["calendar_id"] = params["team_calendar_id"]

        # Event visibility
        if params.get("event_visibility"):
            calendar_params["visibility"] = params["event_visibility"]

        # Notify attendees
        if params.get("notify_attendees") is not None:
            calendar_params["send_notifications"] = params["notify_attendees"]

        # Time range
        if params.get("time_min"):
            calendar_params["time_min"] = params["time_min"]
        if params.get("time_max"):
            calendar_params["time_max"] = params["time_max"]

        # Max events
        calendar_params["max_events"] = params.get("max_events", 10)

        logger.info(
            f"Applied Calendar filters: calendar_id={calendar_params.get('calendar_id')}"
        )

        return calendar_params

    def _apply_slack_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Slack filters

        Supports:
        - Channel filtering
        - Message templates
        - Team notifications
        """
        slack_params = params.copy()

        # Team channel
        if params.get("team_channel"):
            slack_params["channel"] = params["team_channel"]

        # Message template
        if params.get("message_template"):
            slack_params["template"] = params["message_template"]

        # Notify team
        if params.get("notify_team"):
            slack_params["notify_all"] = params["notify_team"]

        logger.info(f"Applied Slack filters: channel={slack_params.get('channel')}")

        return slack_params

    def _apply_notion_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Notion filters

        Supports:
        - Database filtering
        - Page assignment
        - Max pages limit
        """
        notion_params = params.copy()

        # Database ID
        if params.get("database_id"):
            notion_params["database_id"] = params["database_id"]

        # Assign to team member
        if params.get("assign_to"):
            notion_params["assignee"] = params["assign_to"]

        # Max pages
        notion_params["max_pages"] = params.get("max_pages", 10)

        logger.info(
            f"Applied Notion filters: database_id={notion_params.get('database_id')}"
        )

        return notion_params

    def _apply_gdrive_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Google Drive filters

        Supports:
        - Team folder
        - File sharing
        - Access level
        """
        gdrive_params = params.copy()

        # Team folder
        if params.get("team_folder"):
            gdrive_params["folder_name"] = params["team_folder"]

        # Share with team members
        if params.get("share_with"):
            gdrive_params["share_emails"] = params["share_with"]

        # Access level
        if params.get("access_level"):
            gdrive_params["permission_role"] = params["access_level"]

        logger.info(
            f"Applied GDrive filters: folder={gdrive_params.get('folder_name')}"
        )

        return gdrive_params

    async def _get_member_credentials(
        self, member_id: str, required_apps: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get and refresh credentials for a team member"""
        try:
            credentials = {}

            for app_name in required_apps:
                creds = await self.supabase.get_and_refresh_credentials(
                    user_id=member_id, app_name=app_name
                )

                if creds:
                    cred_key = app_name.lower().replace(" ", "_")
                    credentials[cred_key] = {"credentials": creds}

            return credentials if credentials else None

        except Exception as e:
            logger.error(f"Error getting member credentials: {str(e)}")
            return None

    async def _execute_for_member(
        self,
        member_id: str,
        workflow: Dict[str, Any],
        credentials: Dict[str, Any],
        parameters: Dict[str, Any],
        required_apps: List[str],
    ) -> Dict[str, Any]:
        """Execute workflow for a single team member"""
        try:
            # Determine utility module
            util_key = self._determine_util_module(required_apps)

            if not util_key:
                return {
                    "success": False,
                    "error": f"No utility module for apps: {required_apps}",
                }

            util_class = self.utils_registry.get(util_key)
            if not util_class:
                return {
                    "success": False,
                    "error": f"Utility module '{util_key}' not registered",
                }

            # Initialize utility instance
            util_instance = util_class(credentials)

            # Execute workflow logic
            result = await self._execute_workflow_logic(
                util_instance=util_instance,
                workflow=workflow,
                parameters=parameters,
                required_apps=required_apps,
            )

            return result

        except Exception as e:
            logger.error(f"Error executing for member {member_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    def _determine_util_module(self, required_apps: List[str]) -> Optional[str]:
        """Determine which utility module to use based on required apps"""
        apps = [app.lower() for app in required_apps]
        apps_set = set(apps)

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

        return None

    async def _execute_workflow_logic(
        self,
        util_instance: Any,
        workflow: Dict[str, Any],
        parameters: Dict[str, Any],
        required_apps: List[str],
    ) -> Dict[str, Any]:
        """Execute the actual workflow logic"""
        workflow_title = workflow.get("workflow_title", "").lower()

        # Gmail to Calendar workflows
        if "gmail" in workflow_title and "calendar" in workflow_title:
            return await util_instance.emails_to_calendar_events(
                max_emails=parameters.get("max_emails", 10),
                query=parameters.get("query", "is:unread"),
            )

        # Gmail to Drive workflows
        elif "gmail" in workflow_title and "drive" in workflow_title:
            return await util_instance.save_attachments_to_drive(
                max_emails=parameters.get("max_emails", 10),
                folder_name=parameters.get("folder_name", "Email Attachments"),
            )

        # Notion to Slack workflows
        elif "notion" in workflow_title and "slack" in workflow_title:
            return await util_instance.notion_pages_to_slack_messages(
                database_id=parameters.get("database_id"),
                channel=parameters.get("channel"),
                filter=parameters.get("filter"),
                max_pages=parameters.get("max_pages", 10),
            )

        # Add more workflow types as needed

        return {
            "success": False,
            "error": f"No execution logic for workflow: {workflow_title}",
        }

    async def _send_team_notifications(
        self,
        workflow: Dict[str, Any],
        parameters: Dict[str, Any],
        results: List[Dict[str, Any]],
        admin_id: str,
    ) -> None:
        """Send notifications to team members based on configuration.

        The function attempts to resolve each member's email using common
        SupabaseService helpers (for example `get_user_email`,
        `get_user_by_id`, or `get_user`). If none are available the member
        is skipped.
        """
        try:
            notification_mode = parameters.get("team_recipient_mode", "all")
            notification_emails = parameters.get("team_notification", "")
            workflow_title = workflow.get(
                "title", workflow.get("workflow_title", "Untitled Workflow")
            )
            execution_status = parameters.get("execution_status", "success")
            execution_summary = parameters.get(
                "execution_summary", "Workflow completed successfully."
            )

            if notification_mode == "all":
                # Notify all team members
                members = workflow.get("members_json", [])

                for member in members:
                    member_id = member.get("user_id")
                    if not member_id:
                        continue

                    recipient_email = None

                    # Try common SupabaseService helpers to resolve email
                    try:
                        if hasattr(self.supabase, "get_user_email"):
                            # expected to return an email string
                            recipient_email = await self.supabase.get_user_email(
                                member_id
                            )
                        elif hasattr(self.supabase, "get_user_by_id"):
                            user = await self.supabase.get_user_by_id(member_id)
                            recipient_email = user.get("email") if user else None
                        elif hasattr(self.supabase, "get_user"):
                            user = await self.supabase.get_user(member_id)
                            recipient_email = user.get("email") if user else None
                    except Exception:
                        recipient_email = None

                    if not recipient_email:
                        logger.warning(f"No email found for user {member_id}")
                        continue

                    # Send notification email
                    logger.info(f"Sending workflow notification to {recipient_email}")
                    await self.send_workflow_execution_notification(
                        recipient_email=recipient_email,
                        workflow_title=workflow_title,
                        execution_status=execution_status,
                        execution_summary=execution_summary,
                    )

            elif notification_mode == "specific" and notification_emails:
                # Notify specific members by email
                emails = [
                    e.strip() for e in notification_emails.split(",") if e.strip()
                ]
                for email in emails:
                    logger.info(f"Sending workflow notification to {email}")
                    await self.send_workflow_execution_notification(
                        recipient_email=email,
                        workflow_title=workflow_title,
                        execution_status=execution_status,
                        execution_summary=execution_summary,
                    )

            # Optionally notify admin of completion (resolve admin email similarly)
            if admin_id:
                admin_email = None
                try:
                    if hasattr(self.supabase, "get_user_email"):
                        admin_email = await self.supabase.get_user_email(admin_id)
                    elif hasattr(self.supabase, "get_user_by_id"):
                        auser = await self.supabase.get_user_by_id(admin_id)
                        admin_email = auser.get("email") if auser else None
                except Exception:
                    admin_email = None

                if admin_email:
                    logger.info(f"Sending admin notification to {admin_email}")
                    await self.send_workflow_execution_notification(
                        recipient_email=admin_email,
                        workflow_title=workflow_title,
                        execution_status=execution_status,
                        execution_summary=execution_summary,
                    )

            logger.info(f"Team workflow notifications completed. Admin: {admin_id}")

        except Exception as e:
            logger.error(f"Error sending team notifications: {str(e)}", exc_info=True)
