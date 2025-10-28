"""
App Chat Orchestrator
Coordinates data fetching and AI response generation for app chat
"""

import logging
from typing import Dict, Any, List, Optional

from services.supabase_service import SupabaseService
from services.app_chat_service import AppChatService
from services.security_filter import SecurityFilter
from helpers.gmail_helpers import GmailHelpers
from helpers.slack_helpers import SlackHelpers
from helpers.gcalendar_helpers import GCalendarHelpers
from helpers.gdrive_helpers import GDriveHelpers

logger = logging.getLogger(__name__)


class AppChatOrchestrator:
    """Orchestrates app chat operations"""

    def __init__(self):
        self.supabase_service = SupabaseService()
        self.app_chat_service = AppChatService()
        self.security_filter = SecurityFilter()

    async def process_query(
        self, user_id: str, query: str, inquiry_app: str
    ) -> Dict[str, Any]:
        """
        Process user query and determine data fetching plan

        Args:
            user_id: User ID
            query: User's question
            inquiry_app: App to query

        Returns:
            Dict with data fetching plan
        """
        try:
            # Get user's connected apps
            connected_apps_result = await self.supabase_service.get_user_connected_apps(
                user_id
            )
            if not connected_apps_result:
                return {"success": False, "error": "Failed to get connected apps"}

            connected_apps = [
                app.lower().replace(" ", "_") for app in connected_apps_result
            ]

            # Check if inquiry app is connected
            if inquiry_app.lower() not in [app.lower() for app in connected_apps]:
                return {
                    "success": False,
                    "error": f"{inquiry_app} is not connected. Please connect it first.",
                }

            # Analyze query with Gemini
            analysis_result = await self.app_chat_service.analyze_query(
                query=query, inquiry_app=inquiry_app, connected_apps=connected_apps
            )

            if not analysis_result.get("success"):
                return analysis_result

            return {
                "success": True,
                "data_fetch_plan": analysis_result["data_fetch_plan"],
                "actions": analysis_result.get("actions", []),
                "reasoning": analysis_result.get("reasoning"),
            }

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def execute_query(
        self,
        user_id: str,
        query: str,
        data_fetch_plan: Dict[str, Any],
        actions: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute data fetching and generate AI response

        Args:
            user_id: User ID
            query: User's original query
            data_fetch_plan: Plan for fetching data
            actions: Optional actions to perform

        Returns:
            Dict with AI response and execution results
        """
        try:
            app_name = data_fetch_plan["app"]
            function_name = data_fetch_plan["function"]
            parameters = data_fetch_plan.get("parameters", {})

            # Get and refresh user credentials
            credentials = await self.supabase_service.get_and_refresh_credentials(
                user_id=user_id, app_name=app_name
            )

            if not credentials:
                return {
                    "success": False,
                    "error": f"No credentials found for {app_name}",
                }

            # Fetch data from the app
            fetched_data = await self._fetch_app_data(
                app_name=app_name,
                function_name=function_name,
                parameters=parameters,
                credentials=credentials,
            )

            if not fetched_data.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to fetch data: {fetched_data.get('error')}",
                }

            # Determine data type and extract items
            data_type, items = self._extract_data_items(app_name, fetched_data)

            # Filter sensitive information
            filtered_items = self.security_filter.filter_data_list(items, data_type)

            logger.info(f"Fetched {len(filtered_items)} {data_type}(s) from {app_name}")

            # Generate AI response
            response_result = await self.app_chat_service.generate_response(
                query=query,
                fetched_data=filtered_items,
                data_type=data_type,
                inquiry_app=app_name,
            )

            if not response_result.get("success"):
                return response_result

            # Execute actions if any
            action_results = []
            if actions:
                action_results = await self._execute_actions(
                    user_id=user_id, actions=actions, credentials=credentials
                )

            # Build resource URLs
            resource_urls = self._build_resource_urls(
                app_name=app_name,
                items=response_result.get("relevant_items", []),
                raw_items=filtered_items,
            )

            return {
                "success": True,
                "answer": response_result["answer"],
                "confidence": response_result.get("confidence"),
                "data_found": response_result.get("data_found"),
                "relevant_items": response_result.get("relevant_items", []),
                "resource_urls": resource_urls,
                "actions_taken": action_results,
                "suggested_actions": response_result.get("suggested_actions", []),
            }

        except Exception as e:
            logger.error(f"Error executing query: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _fetch_app_data(
        self,
        app_name: str,
        function_name: str,
        parameters: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch data from app using helper functions"""

        try:
            if app_name.lower() == "gmail":
                helper = GmailHelpers()

                # First, list messages to get IDs
                if function_name == "list_messages":
                    list_result = await helper.list_messages(
                        access_token=credentials.get("access_token"),
                        credentials=credentials,
                        **parameters,
                    )

                    if not list_result.get("success"):
                        return list_result

                    messages = list_result.get("messages", [])

                    # Fetch full details for each message
                    full_messages = []
                    for msg in messages:
                        msg_id = msg.get("id")
                        if msg_id:
                            msg_result = await helper.get_message(
                                access_token=credentials.get("access_token"),
                                credentials=credentials,
                                message_id=msg_id,
                                format="full",
                            )

                            if msg_result.get("success"):
                                full_msg = msg_result.get("message", {})

                                # Extract email details
                                headers = {
                                    h["name"]: h["value"]
                                    for h in full_msg.get("payload", {}).get(
                                        "headers", []
                                    )
                                }

                                email_data = {
                                    "id": full_msg.get("id"),
                                    "threadId": full_msg.get("threadId"),
                                    "subject": headers.get("Subject", "No Subject"),
                                    "from": headers.get("From", "Unknown"),
                                    "to": headers.get("To", ""),
                                    "date": headers.get("Date", ""),
                                    "snippet": full_msg.get("snippet", ""),
                                    "labelIds": full_msg.get("labelIds", []),
                                    "internalDate": full_msg.get("internalDate", ""),
                                }

                                # Try to extract body
                                body = self._extract_email_body(
                                    full_msg.get("payload", {})
                                )
                                if body:
                                    email_data["body"] = body

                                full_messages.append(email_data)

                    return {
                        "success": True,
                        "messages": full_messages,
                        "result_size_estimate": len(full_messages),
                    }
                else:
                    # For other functions, use the original approach
                    func = getattr(helper, function_name, None)
                    if func:
                        return await func(
                            access_token=credentials.get("access_token"),
                            credentials=credentials,
                            **parameters,
                        )

            elif app_name.lower() == "slack":
                helper = SlackHelpers()
                func = getattr(helper, function_name, None)
                if func:
                    return await func(
                        access_token=credentials.get("access_token"), **parameters
                    )

            elif app_name.lower() == "google_calendar":
                helper = GCalendarHelpers()
                func = getattr(helper, function_name, None)
                if func:
                    return await func(
                        access_token=credentials.get("access_token"), **parameters
                    )

            elif app_name.lower() == "google_drive":
                helper = GDriveHelpers()
                func = getattr(helper, function_name, None)
                if func:
                    return await func(
                        access_token=credentials.get("access_token"), **parameters
                    )

            return {
                "success": False,
                "error": f"Unsupported app or function: {app_name}.{function_name}",
            }

        except Exception as e:
            logger.error(f"Error fetching app data: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """
        Extract email body from Gmail message payload

        Args:
            payload: Gmail message payload

        Returns:
            Email body text
        """
        try:
            # Check if body is in the main payload
            if "body" in payload and payload["body"].get("data"):
                import base64

                body_data = payload["body"]["data"]
                return base64.urlsafe_b64decode(body_data).decode(
                    "utf-8", errors="ignore"
                )

            # Check parts for multipart messages
            if "parts" in payload:
                for part in payload["parts"]:
                    # Look for text/plain or text/html
                    mime_type = part.get("mimeType", "")

                    if mime_type == "text/plain" and part.get("body", {}).get("data"):
                        import base64

                        body_data = part["body"]["data"]
                        return base64.urlsafe_b64decode(body_data).decode(
                            "utf-8", errors="ignore"
                        )

                    # Recursively check nested parts
                    if "parts" in part:
                        body = self._extract_email_body(part)
                        if body:
                            return body

            return ""

        except Exception as e:
            logger.error(f"Error extracting email body: {str(e)}")
            return ""

    def _extract_data_items(
        self, app_name: str, fetched_data: Dict[str, Any]
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Extract data items and determine type"""

        if app_name.lower() == "gmail":
            messages = fetched_data.get("messages", [])
            return "email", messages

        elif app_name.lower() == "slack":
            messages = fetched_data.get("messages", [])
            return "message", messages

        elif app_name.lower() == "google_drive":
            events = fetched_data.get("events", [])
            return "event", events

        elif app_name.lower() == "google_drive":
            # Handle different response types from GDrive functions
            if "recent_changes" in fetched_data:
                files = fetched_data.get("recent_changes", [])
            elif "shared_files" in fetched_data:
                files = fetched_data.get("shared_files", [])
            else:
                files = fetched_data.get("files", [])
            return "file", files

        return "unknown", []

    async def _execute_actions(
        self, user_id: str, actions: List[Dict[str, Any]], credentials: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute actions like sending messages"""

        results = []

        for action in actions:
            try:
                action_type = action.get("type")
                app_name = action.get("app")
                parameters = action.get("parameters", {})

                if action_type == "send_message" and app_name.lower() == "gmail":
                    result = await GmailHelpers.send_message(
                        access_token=credentials.get("access_token"),
                        credentials=credentials,
                        **parameters,
                    )
                    results.append(
                        {
                            "action": action_type,
                            "app": app_name,
                            "success": result.get("success"),
                            "description": action.get("description"),
                        }
                    )

                # Add more action types as needed

            except Exception as e:
                logger.error(f"Error executing action: {str(e)}", exc_info=True)
                results.append(
                    {"action": action.get("type"), "success": False, "error": str(e)}
                )

        return results

    def _build_resource_urls(
        self,
        app_name: str,
        items: List[Dict[str, Any]],
        raw_items: List[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Build resource URLs for items"""

        urls = []

        for item in items:
            item_id = item.get("id")
            if not item_id:
                continue

            url = None

            if app_name.lower() == "gmail":
                # The ID from Gmail API is the correct format for URLs
                url = f"https://mail.google.com/mail/u/0/#inbox/{item_id}"

            elif app_name.lower() == "google_calendar":
                url = f"https://calendar.google.com/calendar/event?eid={item_id}"

            elif app_name.lower() == "slack":
                # Slack URLs need channel ID and message timestamp
                channel_id = item.get("channel_id", "")
                if channel_id and item_id:
                    url = f"https://app.slack.com/client/{channel_id}/thread/{item_id}"

            elif app_name.lower() == "google_drive":
                # Google Drive file URL
                url = f"https://drive.google.com/file/d/{item_id}/view"

            if url:
                urls.append(
                    {"id": item_id, "summary": item.get("summary", ""), "url": url}
                )

        return urls
