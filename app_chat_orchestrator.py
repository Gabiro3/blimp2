"""
App Chat Orchestrator
Coordinates data fetching and AI response generation for app chat
"""

import logging
from typing import Dict, Any, List, Optional

from helpers.notion_helpers import NotionHelpers
from services.supabase_service import SupabaseService
from services.app_chat_service import AppChatService
from services.security_filter import SecurityFilter
from helpers.gmail_helpers import GmailHelpers
from helpers.slack_helpers import SlackHelpers
from helpers.gcalendar_helpers import GCalendarHelpers
from helpers.gdrive_helpers import GDriveHelpers
from helpers.trello_helpers import TrelloHelpers
from helpers.github_helpers import GitHubHelpers
from helpers.google_docs_helpers import GoogleDocsHelpers

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
                "query_type": analysis_result.get("query_type", "informational"),
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
        query_type: str,
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
            if not data_fetch_plan["function"] and actions and len(actions) > 0:
                function_name = actions[0].get("type")
                if not app_name and actions[0].get("app"):
                    app_name = actions[0]["app"]
                logger.info(
                    f"No function in data_fetch_plan; using fallback from actions: {function_name}"
                )
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

            if (
                app_name == "google_docs"
                and function_name == "generate_and_insert_content"
            ):
                return await self._handle_google_docs_content_generation(
                    user_id=user_id,
                    query=query,
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
                query_type=query_type,
                actions_taken=action_results,
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
                        access_token=credentials.get("access_token"),
                        refresh_token=credentials.get("refresh_token"),
                        **parameters,
                    )

            elif app_name.lower() == "google_docs":
                helper = GoogleDocsHelpers()
                func = getattr(helper, function_name, None)
                if func:
                    return await func(
                        access_token=credentials.get("access_token"),
                        credentials=credentials,
                        **parameters,
                    )

            elif app_name.lower() == "trello":
                helper = TrelloHelpers()
                func = getattr(helper, function_name, None)
                if func:
                    return await func(
                        access_token=credentials.get("access_token"), **parameters
                    )

            elif app_name.lower() == "github":
                helper = GitHubHelpers()
                func = getattr(helper, function_name, None)
                if func:
                    return await func(
                        access_token=credentials.get("access_token"), **parameters
                    )

            return {
                "success": False,
                "error": f"Unsupported function: {function_name}",
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

        elif app_name.lower() == "google_calendar":
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

        elif app_name.lower() == "google_docs":
            documents = fetched_data.get("documents", [])
            # Handle different response types from Google Docs functions
            if "document" in fetched_data and not documents:
                # Single document from create_document or get_document_content
                documents = [fetched_data.get("document", {})]
            return "document", documents

        elif app_name.lower() == "trello":
            boards = fetched_data.get("boards", [])
            return "board", boards

        elif app_name.lower() == "github":
            repositories = fetched_data.get("repositories", [])
            return "repository", repositories

        return "unknown", []

    async def _execute_actions(
        self,
        user_id: str,
        actions: List[Dict[str, Any]],
        credentials: Dict[str, Any],
        fetched_data: List[Dict[str, Any]] = None,
        query_type: str = "actionable",
    ) -> List[Dict[str, Any]]:
        """
        Execute actions like sending messages, creating events, etc.

        Args:
            user_id: User ID
            actions: List of actions to execute
            credentials: User credentials
            fetched_data: Data fetched in previous step (for conditional actions)
            query_type: Type of query (to determine if conditional check needed)

        Returns:
            List of action results
        """

        results = []

        for action in actions:
            try:
                action_type = action.get("type")
                app_name = action.get("app")
                function_name = action.get("function")
                parameters = action.get("parameters", {})
                condition = action.get("condition")

                if condition == "only_if_available" and query_type == "conditional":
                    # Check if user is available based on fetched calendar data
                    if fetched_data and len(fetched_data) > 0:
                        # User has events in the requested time slot - NOT available
                        logger.info(
                            f"Conditional action skipped: User has {len(fetched_data)} conflicting events"
                        )
                        results.append(
                            {
                                "action": action_type,
                                "app": app_name,
                                "success": False,
                                "skipped": True,
                                "reason": "Time slot not available - conflicts found",
                                "description": action.get("description"),
                            }
                        )
                        continue
                    else:
                        # User is available - proceed with action
                        logger.info("Conditional action proceeding: User is available")

                # Execute the action based on app
                if app_name.lower() == "gmail":
                    helper = GmailHelpers()
                    func = getattr(helper, function_name, None)
                    if func:
                        result = await func(
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
                                "result": result,
                            }
                        )

                elif app_name.lower() == "slack":
                    helper = SlackHelpers()
                    func = getattr(helper, function_name, None)
                    if func:
                        result = await func(
                            access_token=credentials.get("access_token"), **parameters
                        )
                        results.append(
                            {
                                "action": action_type,
                                "app": app_name,
                                "success": result.get("success"),
                                "description": action.get("description"),
                                "result": result,
                            }
                        )
                elif app_name.lower() == "notion":
                    helper = NotionHelpers()
                    func = getattr(helper, function_name, None)
                    if func:
                        result = await func(
                            access_token=credentials.get("access_token"), **parameters
                        )
                        results.append(
                            {
                                "action": action_type,
                                "app": app_name,
                                "success": result.get("success"),
                                "description": action.get("description"),
                                "result": result,
                            }
                        )
                elif app_name.lower() == "github":
                    helper = GitHubHelpers()
                    func = getattr(helper, function_name, None)
                    if func:
                        result = await func(
                            access_token=credentials.get("access_token"), **parameters
                        )
                        results.append(
                            {
                                "action": action_type,
                                "app": app_name,
                                "success": result.get("success"),
                                "description": action.get("description"),
                                "result": result,
                            }
                        )

                elif app_name.lower() == "trello":
                    helper = TrelloHelpers()
                    func = getattr(helper, function_name, None)
                    if func:
                        result = await func(
                            access_token=credentials.get("access_token"), **parameters
                        )
                        results.append(
                            {
                                "action": action_type,
                                "app": app_name,
                                "success": result.get("success"),
                                "description": action.get("description"),
                                "result": result,
                            }
                        )

                elif app_name.lower() == "google_calendar":
                    helper = GCalendarHelpers()
                    func = getattr(helper, function_name, None)
                    if func:
                        result = await func(
                            access_token=credentials.get("access_token"), **parameters
                        )
                        results.append(
                            {
                                "action": action_type,
                                "app": app_name,
                                "success": result.get("success"),
                                "description": action.get("description"),
                                "result": result,
                            }
                        )

                elif app_name.lower() == "google_drive":
                    helper = GDriveHelpers()
                    func = getattr(helper, function_name, None)
                    if func:
                        result = await func(
                            access_token=credentials.get("access_token"), **parameters
                        )
                        results.append(
                            {
                                "action": action_type,
                                "app": app_name,
                                "success": result.get("success"),
                                "description": action.get("description"),
                                "result": result,
                            }
                        )

                elif app_name.lower() == "google_docs":
                    helper = GoogleDocsHelpers()
                    func = getattr(helper, function_name, None)
                    if func:
                        result = await func(
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
                                "result": result,
                            }
                        )

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

            elif app_name.lower() == "google_docs":
                # Google Docs document URL
                url = f"https://docs.google.com/document/d/{item_id}/edit"

            elif app_name.lower() == "trello":
                # Trello URLs need board ID and card ID
                board_id = item.get("board_id", "")
                card_id = item.get("card_id", "")
                if board_id and card_id:
                    url = f"https://trello.com/c/{card_id}"

            elif app_name.lower() == "github":
                # GitHub URLs need repository owner and name
                owner = item.get("owner", "")
                repo_name = item.get("repo_name", "")
                if owner and repo_name:
                    url = f"https://github.com/{owner}/{repo_name}"

            if url:
                urls.append(
                    {"id": item_id, "summary": item.get("summary", ""), "url": url}
                )

        return urls

    async def _handle_google_docs_content_generation(
        self,
        user_id: str,
        query: str,
        parameters: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle Google Docs content generation (research and insert)

        Args:
            user_id: User ID
            query: User's original query
            parameters: Parameters including research_topic, action, etc.
            credentials: User credentials

        Returns:
            Dict with operation results
        """
        try:
            research_topic = parameters.get("research_topic", "")
            action = parameters.get("action", "create_new")
            document_title = parameters.get(
                "document_title", f"Research: {research_topic}"
            )
            document_name = parameters.get("document_name", "")

            logger.info(f"Generating research content for topic: {research_topic}")

            # Generate research content using Gemini
            research_content = await self._generate_research_content(research_topic)

            if not research_content.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to generate research content: {research_content.get('error')}",
                }

            content = research_content.get("content", "")

            # Determine action: create new or append to existing
            if action == "create_new":
                # Create a new document
                result = await GoogleDocsHelpers.create_document(
                    access_token=credentials.get("access_token"),
                    title=document_title,
                    content=content,
                    credentials=credentials,
                )

                if not result.get("success"):
                    return {
                        "success": False,
                        "error": f"Failed to create document: {result.get('error')}",
                    }

                doc_id = result.get("document_id")
                web_link = result.get("web_link")

                return {
                    "success": True,
                    "answer": f"I've successfully created a new Google Doc titled '{document_title}' with comprehensive research about {research_topic}. The document includes detailed findings with references and citations.",
                    "confidence": "high",
                    "data_found": True,
                    "relevant_items": [
                        {
                            "id": doc_id,
                            "summary": f"{document_title} - Research document with {len(content.split())} words",
                            "title": document_title,
                            "content_preview": (
                                content[:500] + "..." if len(content) > 500 else content
                            ),
                        }
                    ],
                    "resource_urls": [
                        {"id": doc_id, "summary": document_title, "url": web_link}
                    ],
                    "suggested_actions": [
                        {
                            "action": "Open the document to review",
                            "type": "open_document",
                        }
                    ],
                }

            elif action == "append_to_existing":
                # Search for the document first
                search_result = await GoogleDocsHelpers.search_documents(
                    access_token=credentials.get("access_token"),
                    query=f"name contains '{document_name}'",
                    max_results=5,
                    credentials=credentials,
                )

                if not search_result.get("success") or not search_result.get(
                    "documents"
                ):
                    return {
                        "success": False,
                        "error": f"Could not find document named '{document_name}'. Please check the document name or create a new one.",
                    }

                # Use the first matching document
                doc = search_result.get("documents", [])[0]
                doc_id = doc.get("id")
                doc_title = doc.get("name", document_name)

                # Append content to the document
                append_result = await GoogleDocsHelpers.append_to_document(
                    access_token=credentials.get("access_token"),
                    document_id=doc_id,
                    content=f"\n\n--- Research about {research_topic} ---\n\n{content}",
                    credentials=credentials,
                )

                if not append_result.get("success"):
                    return {
                        "success": False,
                        "error": f"Failed to append content: {append_result.get('error')}",
                    }

                web_link = f"https://docs.google.com/document/d/{doc_id}/edit"

                return {
                    "success": True,
                    "answer": f"I've successfully added research about {research_topic} to your document '{doc_title}'. The new content includes detailed findings with references and has been appended to the end of the document.",
                    "confidence": "high",
                    "data_found": True,
                    "relevant_items": [
                        {
                            "id": doc_id,
                            "summary": f"{doc_title} - Updated with research about {research_topic}",
                            "title": doc_title,
                            "content_preview": (
                                content[:500] + "..." if len(content) > 500 else content
                            ),
                        }
                    ],
                    "resource_urls": [
                        {"id": doc_id, "summary": doc_title, "url": web_link}
                    ],
                    "suggested_actions": [
                        {
                            "action": "Review the updated document",
                            "type": "open_document",
                        }
                    ],
                }

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(
                f"Error handling Google Docs content generation: {str(e)}",
                exc_info=True,
            )
            return {"success": False, "error": str(e)}

    async def _generate_research_content(self, topic: str) -> Dict[str, Any]:
        """
        Generate research content about a topic using Gemini

        Args:
            topic: Research topic

        Returns:
            Dict with generated content
        """
        try:
            import google.generativeai as genai
            import os

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {"success": False, "error": "GEMINI_API_KEY not configured"}

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            prompt = f"""You are a research assistant. Generate comprehensive, well-researched content about the following topic:

Topic: {topic}

Requirements:
1. Provide detailed, factual information with proper context
2. Include historical background if relevant
3. Discuss current trends and developments
4. Include multiple perspectives or viewpoints
5. Add references and citations (use realistic academic/news sources)
6. Structure the content with clear sections
7. Aim for 800-1200 words
8. Use professional, academic tone
9. Include statistics and data points where appropriate

IMPORTANT FORMATTING RULES:
- Use ## for main section headings (e.g., ## Introduction)
- Use ### for subsection headings (e.g., ### Historical Context)
- Use **text** ONLY for emphasis on key terms or important phrases
- Write in clear paragraphs with proper line breaks
- Do NOT overuse bold formatting - only for truly important terms
- Keep formatting minimal and clean for readability

Structure:
## [Title of Research/Document]

[Introduction paragraph]

## Main Section 1
[Content with paragraphs]

### Subsection if needed
[Content]

## Main Section 2
[Content]

## Conclusion
[Summary]

## References
[List of sources]

Generate the research content now:"""

            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7, max_output_tokens=2048
                ),
            )

            content = response.text

            logger.info(
                f"Generated {len(content)} characters of research content for topic: {topic}"
            )

            return {
                "success": True,
                "content": content,
                "word_count": len(content.split()),
            }

        except Exception as e:
            logger.error(f"Error generating research content: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
