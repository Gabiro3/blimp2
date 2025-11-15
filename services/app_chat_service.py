"""
App Chat Service
Handles AI-powered chat interactions with user's connected apps
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from helpers.gmail_helpers import GMAIL_FUNCTIONS
from helpers.google_docs_helpers import GOOGLE_DOCS_FUNCTIONS
from helpers.slack_helpers import SLACK_FUNCTIONS
from helpers.gcalendar_helpers import GCALENDAR_FUNCTIONS
from helpers.gdrive_helpers import GDRIVE_FUNCTIONS
from helpers.trello_helpers import TRELLO_FUNCTIONS
from helpers.github_helpers import GITHUB_FUNCTIONS

from services.gemini_service import GeminiService
from services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)


class AppChatService:
    """Service for AI-powered app chat interactions"""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_service = GeminiService()
        self.supabase_service = SupabaseService()
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            logger.info("App Chat service initialized successfully")
        else:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            self.model = None

    def is_configured(self) -> bool:
        """Check if service is properly configured"""
        return self.gemini_service.is_configured()

    async def analyze_query(
        self, query: str, inquiry_app: str, connected_apps: List[str], user_id: str
    ) -> Dict[str, Any]:
        """
        Analyze user query and determine what data to fetch,
        with automatic detection of the user's timezone for time-specific reasoning.
        """
        try:
            if not self.gemini_service.is_configured():
                return {"success": False, "error": "App Chat service not configured"}

            # Get available functions for the inquiry app
            available_functions = self._get_app_functions(inquiry_app)

            # 🕒 Detect user's timezone (fallback to UTC)
            try:
                user_profile = await self.supabase_service.get_user_profile(user_id)
                user_timezone = (
                    user_profile.get("timezone")
                    if user_profile and user_profile.get("timezone")
                    else "UTC"
                )
            except Exception:
                user_timezone = "UTC"

            try:
                local_tz = ZoneInfo(user_timezone)
            except Exception:
                logger.warning(
                    f"Invalid timezone '{user_timezone}', falling back to UTC"
                )
                local_tz = timezone.utc

            now_local = datetime.now(local_tz)
            now_utc = now_local.astimezone(timezone.utc)

            # Build current datetime context for the model
            current_context = f"""
    CURRENT DATE/TIME CONTEXT:
    - User Timezone: {user_timezone}
    - Local Time: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}
    - UTC Time: {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}
    - Day of Week: {now_local.strftime('%A')}
    - Today is {now_local.strftime('%B %d, %Y')}
    """

            # Build system prompt with temporal context
            system_prompt = f"""{self._build_query_analysis_prompt(
                inquiry_app=inquiry_app,
                available_functions=available_functions,
                connected_apps=connected_apps,
            )}

    {current_context}

    If the user's query includes relative time expressions (e.g., "tomorrow", "next week", "later today"),
    resolve them based on the user's local timezone and convert to ISO 8601 UTC format (e.g., 2025-11-14T15:00:00Z).
    """

            # Build user message
            user_message = f"""
    User Query: "{query}"

    TASK: Analyze this query and determine the appropriate response strategy.

    IMPORTANT RULES:
    1. Resolve all relative time references using the user's timezone ({user_timezone}).
    2. When specifying any datetime in the output, always return it in ISO 8601 UTC format.
    3. Follow all structural and functional instructions from the system prompt.

    RESPONSE FORMAT:
    IMPORTANT RULES:
1. If the query is INFORMATIONAL (asking for data), return a data_fetch_plan
2. If the query is ACTIONABLE (creating, sending, scheduling something), return an actions list
3. If the query is BOTH (e.g., "check if I'm free, then schedule a meeting"), return BOTH data_fetch_plan AND actions
4. ONLY use functions that exist in the available_functions registry provided in the system prompt
5. Ensure ALL required parameters for each function are included
6. Use proper data types for parameters (strings, numbers, booleans, lists)
7. If the user does not provide a specific event title or event duration (for Google Calendar events), use their query to generate a title and set the duration to 1 hour as default and if no specific duration was provided.
8. Be innovative and creative with the slack messages. For example: if a user says to send a welcome message to a certain slack channel, you can come up with welcome messages like 'Welcome everyone!', 'Welcome to the channele guys!' etc. not 'Welcome message' as it.

RESPONSE FORMAT:
Return a valid JSON object with this EXACT structure:

{{
    "query_type": "informational" | "actionable" | "conditional",
    "data_fetch_plan": {{
        "app": "app_name",
        "function": "exact_function_name_from_registry",
        "parameters": {{
            "param1": "value1",
            "param2": "value2"
        }},
        "description": "what data this will fetch"
    }},
    "actions": [
        {{
            "type": "action_type",
            "app": "app_name",
            "function": "exact_function_name_from_registry",
            "parameters": {{
                "param1": "value1"
            }},
            "description": "what this action does",
            "condition": "only include if action is conditional based on fetched data"
        }}
    ],
    "reasoning": "step-by-step explanation of your analysis"
}}

QUERY TYPE DEFINITIONS:
- "informational": User is asking for information (e.g., "What emails did I get from John?")
- "actionable": User wants to create/send/schedule something (e.g., "Schedule a meeting with Sonia tomorrow at 3PM")
- "conditional": User wants to check something THEN take action (e.g., "Am I free tomorrow 2-4pm? If yes, schedule meeting with Kevin")

EXAMPLES:

Example 1 - Simple Actionable Query:
User: "Schedule a calendar meeting with Sonia tomorrow 3PM @Google Calendar"
Response:
{{
    "query_type": "actionable",
    "data_fetch_plan": [],
    "actions": [
        {{
            "type": "create_event",
            "app": "google_calendar",
            "function": "create_event",
            "parameters": {{
                "summary": "Meeting with Sonia",
                "start_time": "2025-01-16T15:00:00Z",
                "end_time": "2025-01-16T16:00:00Z",
                "attendees": ["sonia@example.com"]
            }},
            "description": "Create a calendar event for meeting with Sonia tomorrow at 3PM"
        }}
    ],
    "reasoning": "User explicitly wants to schedule a meeting. This is a pure action request, no data fetching needed. Using create_event function with Sonia as attendee and tomorrow 3PM as time."
}}

Example 2 - Informational Query:
User: "Show me emails from Simon about funding"
Response:
{{
    "query_type": "informational",
    "data_fetch_plan": {{
        "app": "gmail",
        "function": "list_messages",
        "parameters": {{
            "query": "from:simon subject:funding",
            "max_results": 10
        }},
        "description": "Fetch emails from Simon that contain 'funding' in subject"
    }},
    "actions": [],
    "reasoning": "User is requesting information about existing emails. Using list_messages with Gmail query syntax to filter by sender (from:simon) and subject (subject:funding)."
}}

Example 3 - Conditional Query (Check Then Act):
User: "Am I available tomorrow from 2 to 4pm? if yes, schedule a meeting with Kevin @Google Calendar"
Response:
{{
    "query_type": "conditional",
    "data_fetch_plan": {{
        "app": "google_calendar",
        "function": "list_events",
        "parameters": {{
            "time_min": "2025-01-16T14:00:00Z",
            "time_max": "2025-01-16T16:00:00Z",
            "max_results": 10
        }},
        "description": "Check calendar for conflicts between 2-4PM tomorrow"
    }},
    "actions": [
        {{
            "type": "create_event",
            "app": "google_calendar",
            "function": "create_event",
            "parameters": {{
                "summary": "Meeting with Kevin",
                "start_time": "2025-01-16T14:00:00Z",
                "end_time": "2025-01-16T16:00:00Z",
                "attendees": ["kevin@example.com"]
            }},
            "description": "Create meeting with Kevin if no conflicts found",
            "condition": "only_if_available"
        }}
    ],
    "reasoning": "User wants to check availability first, then conditionally create a meeting. First, fetch events in the 2-4PM tomorrow timeframe. If no conflicts exist, then create the meeting with Kevin. The orchestrator will handle the conditional logic."
}}

Example 4 - Send Slack Message:
User: "Send a message to #engineering saying 'Deploy is ready'"
Response:
{{
    "query_type": "actionable",
    "data_fetch_plan": [],
    "actions": [
        {{
            "type": "send_message",
            "app": "slack",
            "function": "send_message",
            "parameters": {{
                "channel": "#engineering",
                "message": "Deploy is ready"
            }},
            "description": "Send message to engineering channel"
        }}
    ],
    "reasoning": "User wants to send a Slack message. This is a direct action with no data fetching required. Using send_message function with channel and message text."
}}

NOW ANALYZE THE USER'S QUERY AND RESPOND WITH VALID JSON:
    """

            # Call Gemini service for structured JSON response
            response = self.gemini_service.generate_content(
                prompt=user_message,
                system_instruction=system_prompt,
                temperature=0.3,
                response_format="json",
            )

            if not response.get("success"):
                return {
                    "success": False,
                    "error": response.get("error", "Failed to analyze query"),
                }

            try:
                parsed = json.loads(response["content"])
                return {"success": True, **parsed}
            except json.JSONDecodeError:
                logger.error("Invalid JSON returned from Gemini analyze_query response")
                return {
                    "success": False,
                    "error": "Invalid JSON response from Gemini",
                }

        except Exception as e:
            logger.error(f"Error analyzing query: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def generate_response(
        self,
        query: str,
        fetched_data: List[Dict[str, Any]],
        data_type: str,
        inquiry_app: str = None,
        context: Optional[Dict[str, Any]] = None,
        query_type: str = "informational",
        actions_taken: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI response based on fetched data

        Args:
            query: User's original query
            fetched_data: Data fetched from the app
            data_type: Type of data (email, message, event)
            inquiry_app: The app being queried
            context: Additional context

        Returns:
            Dict with AI-generated response
        """
        try:
            if not self.gemini_service.is_configured():
                return {"success": False, "error": "App Chat service not configured"}

            # Build prompt
            system_prompt = self._build_response_generation_prompt(
                inquiry_app, data_type
            )

            # Build user message based on query type
            if query_type == "actionable" and actions_taken:
                # For pure actions, focus on confirming what was done
                user_message = f"""
User Query: "{query}"
Query Type: {query_type}

Actions Taken:
{json.dumps(actions_taken, indent=2)}

TASK: Generate a confirmation response for the user.

RESPONSE REQUIREMENTS:
1. Confirm the action was completed successfully
2. Include specific details (e.g., "Meeting scheduled for tomorrow at 3PM with Sonia")
3. Keep it concise and friendly
4. Set "actionable_insights" to "action_completed" since this was an action

Respond in this JSON format:
{{
    "answer": "Confirmation message with specific details",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [],
    "actionable_insights": "action_completed",
    "suggested_actions": []
}}
"""
            else:
                # For informational or conditional queries
                user_message = f"""
User Query: "{query}"
Query Type: {query_type}

Fetched Data ({data_type}):
{json.dumps(fetched_data, indent=2)}

Actions Taken:
{json.dumps(actions_taken, indent=2) if actions_taken else "None"}

Additional Context: {json.dumps(context) if context else "None"}

TASK: Generate a comprehensive response based on the data and any actions taken.

RESPONSE REQUIREMENTS:
1. Answer the user's question directly with specific details
2. Reference the fetched data explicitly (dates, names, subjects, etc.)
3. If actions were taken, confirm them
4. If this was a conditional query and action was taken, explain why
5. Include relevant_items with proper IDs for linking
6. Set "actionable_insights" to "action_completed" if actions were successfully taken
7. Suggest next steps if appropriate

Respond in JSON format as specified in the system prompt.
"""

            # Call Gemini
            response = self.gemini_service.generate_content(
                prompt=user_message,
                system_instruction=system_prompt,
                temperature=0.4,
                response_format="json",
            )

            # Parse response
            result = json.loads(response["content"])
            logger.info(
                f"Generated response with confidence: {result.get('confidence')}"
            )

            return {
                "success": True,
                "answer": result["answer"],
                "confidence": result.get("confidence", "medium"),
                "data_found": result.get("data_found", True),
                "relevant_items": result.get("relevant_items", []),
                "suggested_actions": result.get("suggested_actions", []),
            }

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _get_app_functions(self, app_name: str) -> Dict[str, Any]:
        """Get available functions for an app"""
        function_map = {
            "gmail": GMAIL_FUNCTIONS,
            "slack": SLACK_FUNCTIONS,
            "google_calendar": GCALENDAR_FUNCTIONS,
            "google_docs": GOOGLE_DOCS_FUNCTIONS,
            "google_drive": GDRIVE_FUNCTIONS,
            "trello": TRELLO_FUNCTIONS,
            "github": GITHUB_FUNCTIONS,
        }
        return function_map.get(app_name.lower(), {})

    def _build_query_analysis_prompt(
        self,
        inquiry_app: str,
        available_functions: Dict[str, Any],
        connected_apps: List[str],
    ) -> str:
        """Build system prompt for query analysis"""

        connected_apps_str = ", ".join(connected_apps) if connected_apps else "None"

        base_prompt = f"""You are an AI assistant for Blimp's App Chat feature. Your role is to help users query and interact with their connected apps.

Primary App: {inquiry_app}
User's Connected Apps: {connected_apps_str}

Available Functions for {inquiry_app}:
{json.dumps(available_functions, indent=2)}

Your task is to analyze user queries and determine:
1. What data to fetch from the app
2. Which helper functions to call with what parameters
3. Whether any actions should be taken (like sending a reply)
"""

        # Add app-specific instructions
        if inquiry_app.lower() == "gmail":
            app_specific = """
GMAIL-SPECIFIC INSTRUCTIONS:
1. Always use the 'list_messages' function to fetch emails
2. Use the 'query' parameter with Gmail search syntax:
   - "from:name@example.com" to search by sender
   - "subject:topic" to search by subject
   - "after:2024/01/01" for date ranges
   - Combine with spaces: "from:simon subject:funding"
3. Set 'max_results' parameter (default: 10, max: 50)
4. For "recent emails", use max_results without query
5. For specific senders, extract the name and use "from:name"
6. IMPORTANT: The response must include the message ID (the long alphanumeric string, NOT the numeric ID)

Common Query Patterns:
- "Recent emails" → list_messages(max_results=10)
- "Emails from [person]" → list_messages(query="from:person", max_results=10)
- "Has [person] sent me [topic]?" → list_messages(query="from:person subject:topic", max_results=10)
- "Send [person] a reply" → First fetch context, then send_message action

Example Response:
{{
    "data_fetch_plan": {{
        "app": "gmail",
        "function": "list_messages",
        "parameters": {{"query": "from:simon", "max_results": 10}},
        "description": "Fetch recent emails from Simon"
    }},
    "actions": [],
    "reasoning": "User wants to find emails from Simon, so we'll search with from:simon query"
}}
"""
        elif inquiry_app.lower() == "slack":
            app_specific = """
SLACK-SPECIFIC INSTRUCTIONS:
1. Use 'search_messages' to find messages by query
2. Use 'list_channels' to get available channels
3. Use 'get_channel_history' to get recent messages from a specific channel
4. Extract keywords and user mentions from the query
5. IMPORTANT: Include full message text, timestamp, channel name, and user info in results

Common Query Patterns:
- "Recent messages" → get_channel_history(channel_id="general", limit=10)
- "Messages about [topic]" → search_messages(query="topic", count=10)
- "Did [person] message me?" → search_messages(query="from:@person", count=10)
- "Send message to [channel]" → send_message action

Example Response:
{{
    "data_fetch_plan": {{
        "app": "slack",
        "function": "search_messages",
        "parameters": {{"query": "funding round", "count": 10}},
        "description": "Search for messages about funding round"
    }},
    "actions": [],
    "reasoning": "User wants to find Slack messages about funding, so we'll search with relevant keywords"
}}
"""
        elif inquiry_app.lower() == "google_calendar":
            app_specific = """
GOOGLE CALENDAR-SPECIFIC INSTRUCTIONS:
1. Use 'list_events' to fetch calendar events
2. Use 'start_time' and 'end_time' for date ranges (ISO 8601 format)
3. Use 'q' parameter for text search in event titles/descriptions
4. Set 'max_results' parameter (default: 10)
5. IMPORTANT: Include event title, start/end times, location, attendees, and description

Common Query Patterns:
- "Today's meetings" → list_events(start_time="2024-01-15T00:00:00Z", end_time="2024-01-15T23:59:59Z")
- "Meetings with [person]" → list_events(q="person name", max_results=10)
- "Next week's events" → list_events(start_time="start_of_week", end_time="end_of_week")
- "Create meeting" → create_event action

Example Response:
{{
    "data_fetch_plan": {{
        "app": "google_calendar",
        "function": "list_events",
        "parameters": {{"start_time": "2024-01-15T00:00:00Z", "end_time": "2024-01-22T23:59:59Z", "max_results": 20}},
        "description": "Fetch events for next week"
    }},
    "actions": [],
    "reasoning": "User wants to see next week's calendar events, so we'll fetch events in that date range"
}}
"""
        elif inquiry_app.lower() == "google_drive":
            app_specific = """
GOOGLE DRIVE-SPECIFIC INSTRUCTIONS:
1. Use 'get_recent_changes' to fetch recently modified files
2. Use 'list_files' to list files with optional search query
3. Use 'get_shared_with_me' to get files shared with the user
4. Use 'search_files_by_type' to find files by type (document, spreadsheet, pdf, image, etc.)
5. Use 'find_folder' to locate folders by name
6. IMPORTANT: Include file name, type, modified time, size, and file ID in results

Common Query Patterns:
- "Recent changes" or "What changed recently" → get_recent_changes(days=7, max_results=20)
- "Files shared with me" → get_shared_with_me(max_results=20)
- "Find my documents" → search_files_by_type(file_type="document", max_results=20)
- "Find folder named [name]" → find_folder(folder_name="name")
- "List all files" → list_files(page_size=20)
- "Files modified in last [X] days" → get_recent_changes(days=X, max_results=20)

Parameter Guidelines:
- For "recent changes", use get_recent_changes with appropriate 'days' parameter
- For file type searches, use search_files_by_type with file_type: 'document', 'spreadsheet', 'presentation', 'pdf', 'image', or 'folder'
- For general file listing, use list_files with optional query parameter
- Default max_results to 20 unless user specifies otherwise

Example Response:
{{
    "data_fetch_plan": {{
        "app": "google_drive",
        "function": "get_recent_changes",
        "parameters": {{"days": 7, "max_results": 20}},
        "description": "Fetch files modified in the last 7 days"
    }},
    "actions": [],
    "reasoning": "User wants to see recent changes to their Google Drive, so we'll fetch recently modified files from the past week"
}}
"""
        elif inquiry_app.lower() == "google_docs":
            app_specific = """
    GOOGLE DOCS-SPECIFIC INSTRUCTIONS:
    1. Use 'search_documents' to find documents by name or content
    2. Use 'create_document' to create new documents with optional initial content
    3. Use 'append_to_document' to add content to existing documents
    4. Use 'get_document_content' to retrieve full document text
    5. Use 'get_recent_documents' to fetch recently modified documents
    6. Use 'share_document' to share documents with specific users
    7. IMPORTANT: Include document title, ID, content, and modification date in results

    CRITICAL: RESEARCH AND CONTENT GENERATION WORKFLOW
    When the user asks to "research [topic] and insert/add to Google Docs":
    1. This is a CONTENT GENERATION task, NOT a data fetching task
    2. Set data_fetch_plan.function to "generate_and_insert_content" (special marker)
    3. Include the research topic in parameters
    4. The system will:
    a) Generate research content using Gemini
    b) Format it properly with references
    c) Either create a new document OR append to existing one
    5. DO NOT use search_documents or get_recent_documents for these queries

    Example for Research Query:
    {{
    "data_fetch_plan": {{
        "app": "google_docs",
        "function": "generate_and_insert_content",
        "parameters": {{
            "research_topic": "9-to-5 workweek",
            "action": "create_new",
            "document_title": "Research: 9-to-5 Workweek"
        }},
        "description": "Generate research content about 9-to-5 workweek and create a new document"
    }},
    "actions": [],
    "reasoning": "User wants to research a topic and insert it into Google Docs. This requires content generation, not data fetching."
    }}

    Example for Append to Existing:
    {{
    "data_fetch_plan": {{
        "app": "google_docs",
        "function": "generate_and_insert_content",
        "parameters": {{
            "research_topic": "remote work trends",
            "action": "append_to_existing",
            "document_name": "Work Research"
        }},
        "description": "Generate research content about remote work and append to existing document"
    }},
    "actions": [],
    "reasoning": "User wants to add research to an existing document. We'll generate content and append it."
    }}

    Common Query Patterns:
    - "Find documents about [topic]" → search_documents(query="name contains 'topic'", max_results=10)
    - "Create a document about [topic]" → create_document(title="Topic Document", content="...")
    - "Add [content] to document [name]" → First search_documents to find ID, then append_to_document(document_id="id", content="...")
    - "Research [topic] and insert into Google Docs" → generate_and_insert_content(research_topic="topic", action="create_new")
    - "Recent documents" → get_recent_documents(max_results=10)
    - "Get content of [document]" → get_document_content(document_id="id")
    - "Share [document] with [email]" → share_document(document_id="id", email="user@example.com", role="writer")

    Parameter Guidelines:
    - For searching, use query parameter with Google Drive search syntax: "name contains 'keyword'"
    - For creating documents, always provide a title and optional initial content
    - For appending content, you need the document_id (use search first if needed)
    - Default max_results to 10 unless user specifies otherwise
    - For sharing, role can be: "reader", "commenter", or "writer"
    - For research queries, use generate_and_insert_content with research_topic parameter
    """

        elif inquiry_app.lower() == "trello":
            app_specific = """
TRELLO-SPECIFIC INSTRUCTIONS:
1. Use 'get_boards' to fetch user's boards
2. Use 'get_lists' to fetch lists within a board
3. Use 'get_cards' to fetch cards within a list
4. Use 'get_card_details' to get detailed information about a card
5. Use 'search_cards' to search for cards by query
6. IMPORTANT: Include board name, list name, card name, card ID, and card details in results

Common Query Patterns:
- "List all boards" → get_boards()
- "Cards in [list]" → get_cards(list_id="list_id")
- "Details of card [name]" → get_card_details(card_id="card_id")
- "Search for [topic]" → search_cards(query="topic")

Example Response:
{{
    "data_fetch_plan": {{
        "app": "trello",
        "function": "search_cards",
        "parameters": {{"query": "funding round"}},
        "description": "Search for cards related to funding round"
    }},
    "actions": [],
    "reasoning": "User wants to find Trello cards about funding, so we'll search with relevant keywords"
}}
"""
        elif inquiry_app.lower() == "github":
            app_specific = """
GITHUB-SPECIFIC INSTRUCTIONS:
1. Use 'list_repositories' to fetch user's repositories
2. Use 'list_issues' to fetch issues within a repository
3. Use 'list_pull_requests' to fetch pull requests in a repository
4. Use 'search_issues' to search for issues by query
5. Use 'get_recent_push' to get the most recent commit/push to a repository branch
6. Use 'check_all_prs_merged' to check if all pull requests have been merged
7. Use 'find_pr_by_title' to find pull request(s) by title (supports partial matching)
8. Use 'get_pr_comments' to get comments for a pull request (can find PR by number or title)
9. IMPORTANT: Include repository name (owner/repo format), issue/PR title, IDs, and details in results

Common Query Patterns:
- "List all repositories" → list_repositories(per_page=20)
- "Issues in [repo]" → list_issues(repo="owner/repo", state="all", per_page=10)
- "Pull requests in [repo]" → list_pull_requests(repo="owner/repo", state="all", per_page=10)
- "Search for [topic]" → search_issues(query="topic", per_page=10)
- "Most recent push to [repo]" → get_recent_push(repo="owner/repo", branch="main")
- "Are all PRs merged in [repo]?" → check_all_prs_merged(repo="owner/repo", state="all")
- "Find PR titled [title]" → find_pr_by_title(repo="owner/repo", title="PR title", state="all")
- "Comments on PR [title]" → get_pr_comments(repo="owner/repo", pr_title="PR title")
- "Comments on PR #[number]" → get_pr_comments(repo="owner/repo", pr_number=123)

Example Response for Recent Push:
{{
    "data_fetch_plan": {{
        "app": "github",
        "function": "get_recent_push",
        "parameters": {{"repo": "owner/repo", "branch": "main"}},
        "description": "Get the most recent push to the repository"
    }},
    "actions": [],
    "reasoning": "User wants to know the most recent push, so we'll fetch the latest commit"
}}

Example Response for PR Comments:
{{
    "data_fetch_plan": {{
        "app": "github",
        "function": "get_pr_comments",
        "parameters": {{"repo": "owner/repo", "pr_title": "Add new feature"}},
        "description": "Get comments for the pull request with title 'Add new feature'"
    }},
    "actions": [],
    "reasoning": "User wants to see comments on a specific PR, so we'll find it by title and get comments"
}}
"""
        else:
            app_specific = """
GENERAL INSTRUCTIONS:
1. Be specific about search parameters
2. Limit data fetching to what's necessary (default max 10 items)
3. Extract key information from the query (names, dates, keywords)
4. Suggest actions only when explicitly requested or clearly implied
"""

        return base_prompt + app_specific

    def _build_response_generation_prompt(
        self, inquiry_app: str, data_type: str
    ) -> str:
        """Build app-specific prompt for response generation"""

        base_prompt = """You are an AI assistant helping users understand their app data. Provide detailed, accurate responses based on the fetched data."""

        if inquiry_app and inquiry_app.lower() == "gmail":
            return (
                base_prompt
                + """

GMAIL RESPONSE INSTRUCTIONS:
1. ALWAYS include detailed email information:
   - Subject line
   - Sender name and email
   - Date/time received
   - Brief summary of email content (2-3 sentences)
   - Message ID (the long alphanumeric string like "FMfcgzQcqQzQWvKBtVpkZrHzsbtVgNnJ")

2. For each relevant email in relevant_items, include:
   - "id": The MESSAGE ID (long string, NOT numeric ID)
   - "summary": Subject + brief content summary
   - "sender": Sender name and email
   - "date": When it was received
   - "snippet": First few lines of the email

3. Answer format:
   - Start with direct answer to the query
   - List relevant emails with full details
   - Include context about what was found

4. If no emails match: Clearly state no matching emails were found

Example Response:
{
    "answer": "Yes, Simon sent you 2 emails about the Series A funding. The most recent one (Jan 15) discusses the term sheet details and asks for your feedback by Friday. The earlier email (Jan 12) was an introduction to the funding opportunity.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "FMfcgzQcqQzQWvKBtVpkZrHzsbtVgNnJ",
            "summary": "Series A Term Sheet - Review Needed",
            "sender": "Simon Chen <simon@vc-firm.com>",
            "date": "2024-01-15T10:30:00Z",
            "snippet": "Hi, I've attached the term sheet for our Series A discussion. Please review the valuation and equity terms..."
        }
    ],
    "suggested_actions": [
        {
            "action": "Reply to Simon's email",
            "type": "send_message"
        }
    ]
}
"""
            )
        elif inquiry_app and inquiry_app.lower() == "slack":
            return (
                base_prompt
                + """

SLACK RESPONSE INSTRUCTIONS:
1. ALWAYS include detailed message information:
   - Message text (full content)
   - Sender name and username
   - Channel name
   - Timestamp
   - Any reactions or thread replies

2. For each relevant message in relevant_items, include:
   - "id": Message timestamp or ID
   - "summary": Message content summary
   - "sender": User who sent it
   - "channel": Channel name
   - "text": Full message text

3. Answer format:
   - Direct answer to the query
   - Quote relevant messages
   - Provide context about the conversation

4. If no messages match: Clearly state no matching messages were found

Example Response:
{
    "answer": "Yes, Sarah messaged you about the product launch in #marketing channel yesterday. She asked if you could review the launch timeline and mentioned the deadline is next Friday.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "1705334400.123456",
            "summary": "Product launch timeline review request",
            "sender": "Sarah Johnson (@sarah)",
            "channel": "#marketing",
            "text": "Hey team, can someone review the product launch timeline? We need feedback by Friday for the stakeholder meeting."
        }
    ]
}
"""
            )
        elif inquiry_app and inquiry_app.lower() == "google_calendar":
            return (
                base_prompt
                + """

GOOGLE CALENDAR RESPONSE INSTRUCTIONS:
1. ALWAYS include detailed event information:
   - Event title
   - Start and end date/time
   - Location (if any)
   - Attendees list
   - Description/notes
   - Event ID

2. For each relevant event in relevant_items, include:
   - "id": Event ID
   - "summary": Event title and brief description
   - "start": Start date/time
   - "end": End date/time
   - "location": Where it's happening
   - "attendees": Who's invited

3. Answer format:
   - Direct answer about the events
   - List events chronologically
   - Include timing and location details

4. If no events match: Tell them that they are free.

Example Response:
{
    "answer": "You have 3 meetings tomorrow. Your day starts with a 1:1 with Sarah at 9am, followed by the product review at 11am, and ends with the team standup at 4pm.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "abc123eventid",
            "summary": "1:1 with Sarah - Q1 Planning",
            "start": "2024-01-16T09:00:00Z",
            "end": "2024-01-16T09:30:00Z",
            "location": "Conference Room A",
            "attendees": ["sarah@company.com", "you@company.com"]
        }
    ]
}
"""
            )
        elif inquiry_app and inquiry_app.lower() == "google_drive":
            return (
                base_prompt
                + """

GOOGLE DRIVE RESPONSE INSTRUCTIONS:
1. ALWAYS include detailed file information:
   - File name
   - File type/MIME type
   - Size (in human-readable format)
   - Last modified date/time
   - Created date/time
   - File ID

2. For each relevant file in relevant_items, include:
   - "id": File ID
   - "summary": File name and brief description
   - "name": Full file name
   - "type": File type (document, spreadsheet, pdf, etc.)
   - "size": File size
   - "modified": Last modified date
   - "created": Created date

3. Answer format:
   - Direct answer to the query
   - List files with full details
   - Group by type or date if relevant
   - Include context about what was found

4. If no files match: Clearly state no matching files were found

5. For recent changes: Organize chronologically and highlight what changed

Example Response:
{
    "answer": "You have 5 files that were recently modified in your Google Drive. The most recent change was to 'Q4 Report.docx' which was updated 2 hours ago. You also have 3 spreadsheets and 1 presentation that were modified this week.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "1abc123xyz",
            "summary": "Q4 Report - Financial analysis document",
            "name": "Q4 Report.docx",
            "type": "document",
            "size": "2.5 MB",
            "modified": "2024-01-15T14:30:00Z",
            "created": "2024-01-10T09:00:00Z"
        }
    ],
    "suggested_actions": [
        {
            "action": "Open Q4 Report",
            "type": "open_file"
        }
    ]
}
"""
            )
        elif inquiry_app and inquiry_app.lower() == "trello":
            return (
                base_prompt
                + """

TRELLO RESPONSE INSTRUCTIONS:
1. ALWAYS include detailed card information:
   - Card name
   - Board name
   - List name
   - Card ID
   - Card description
   - Labels
   - Due date

2. For each relevant card in relevant_items, include:
   - "id": Card ID
   - "summary": Card name and brief description
   - "board": Board name
   - "list": List name
   - "description": Card description
   - "labels": List of labels
   - "due": Due date

3. Answer format:
   - Direct answer to the query
   - List cards with full details
   - Include context about what was found

4. If no cards match: Clearly state no matching cards were found

Example Response:
{
    "answer": "You have 2 cards related to the funding round on the 'Project Management' board. One is titled 'Research Funding Sources' and the other is 'Schedule Meeting with Investors'. Both are due next week.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "card123",
            "summary": "Research Funding Sources",
            "board": "Project Management",
            "list": "To Do",
            "description": "Find potential funding sources for our Series A round",
            "labels": ["funding", "research"],
            "due": "2024-01-20"
        }
    ]
}
"""
            )
        elif inquiry_app and inquiry_app.lower() == "github":
            return (
                base_prompt
                + """

GITHUB RESPONSE INSTRUCTIONS:
1. ALWAYS include detailed information based on the query type:
   - For issues: title, repository, ID, description, labels, assignees, dates
   - For pull requests: title, repository, number, state, merged status, author, dates
   - For commits: message, author, date, SHA, repository, branch
   - For comments: user, body, date, type (comment/review), PR number
   - For merge status: total PRs, merged count, open count, unmerged PRs list

2. For each relevant item in relevant_items, include:
   - "id": Item ID (issue ID, PR number, commit SHA, comment ID)
   - "summary": Title/description summary
   - "repo": Repository name (owner/repo format)
   - Additional fields based on item type

3. Answer format:
   - Direct answer to the query
   - List items with full details
   - Include context about what was found
   - For merge status queries, clearly state if all PRs are merged or list unmerged ones

4. If no items match: Clearly state no matching items were found

Example Response for Recent Push:
{
    "answer": "The most recent push to the 'myrepo' repository (main branch) was made by John Doe on January 15, 2024. The commit message was 'Fix authentication bug' (SHA: abc123).",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "abc123",
            "summary": "Fix authentication bug",
            "repo": "owner/myrepo",
            "author": "John Doe",
            "date": "2024-01-15T10:30:00Z"
        }
    ]
}

Example Response for PR Merge Status:
{
    "answer": "In the 'myrepo' repository, not all pull requests are merged. You have 5 total PRs: 3 merged, 1 open, and 1 closed but not merged. The open PR is #42 titled 'Add new feature'.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "merge_status",
            "summary": "PR Merge Status for myrepo",
            "repo": "owner/myrepo",
            "all_merged": false,
            "total_prs": 5,
            "merged_count": 3,
            "open_count": 1
        }
    ]
}

Example Response for PR Comments:
{
    "answer": "The pull request 'Add new feature' (#42) has 3 comments. The most recent comment was from Sarah on January 14, asking about test coverage. There's also a review comment from John requesting changes.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "comment123",
            "summary": "Comment by Sarah on PR #42",
            "repo": "owner/myrepo",
            "pr_number": 42,
            "user": "sarah",
            "body": "Can you add test coverage for this?",
            "type": "comment"
        }
    ]
}
"""
            )
        elif inquiry_app and inquiry_app.lower() == "google_docs":
            return (
                base_prompt
                + """

GOOGLE DOCS RESPONSE INSTRUCTIONS:
1. ALWAYS include detailed document information:
   - Document title
   - Document ID
   - Content summary or full content
   - Last modified date
   - Created date
   - Web link to the document

2. For each relevant document in relevant_items, include:
   - "id": Document ID (the long alphanumeric string)
   - "summary": Document title and brief content summary
   - "title": Full document title
   - "modified": Last modified date
   - "created": Created date
   - "content_preview": First few paragraphs of content

3. Answer format:
   - Direct answer to the query
   - List documents with full details
   - Include content previews when relevant
   - Provide web links for easy access

4. If no documents match: Clearly state no matching documents were found

5. For content insertion: Confirm what was added and where

Example Response for Search:
{
    "answer": "I found 2 documents related to your research. The most recent one is 'Market Analysis 2024' which was updated yesterday and contains competitive research data. The other document 'Industry Trends' has background information from last week.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "1abc123xyz456",
            "summary": "Market Analysis 2024 - Competitive research and market trends",
            "title": "Market Analysis 2024",
            "modified": "2024-01-15T14:30:00Z",
            "created": "2024-01-10T09:00:00Z",
            "content_preview": "This document contains comprehensive market analysis including competitor positioning, market size estimates, and growth projections..."
        }
    ],
    "suggested_actions": [
        {
            "action": "Open Market Analysis document",
            "type": "open_document"
        }
    ]
}

Example Response for Content Insertion:
{
    "answer": "I've successfully added the research content to your document '9-to-5 Workweek Research'. The document now includes detailed findings about the history of the 9-to-5 workweek, its impact on productivity, and modern alternatives, along with references to academic studies.",
    "confidence": "high",
    "data_found": true,
    "relevant_items": [
        {
            "id": "1xyz789abc",
            "summary": "9-to-5 Workweek Research - Updated with new research findings",
            "title": "9-to-5 Workweek Research",
            "modified": "2024-01-15T16:45:00Z",
            "content_preview": "Research about the 9-to-5 workweek:\\n\\nHistory: The 9-to-5 workweek originated in the early 20th century..."
        }
    ],
    "suggested_actions": [
        {
            "action": "Review the updated document",
            "type": "open_document"
        }
    ]
}
"""
            )
        else:
            return (
                base_prompt
                + """

GENERAL RESPONSE INSTRUCTIONS:
1. Answer the user's question directly and concisely
2. Reference specific data from the fetched results with details
3. If the data doesn't contain the answer, say so clearly
4. Provide relevant details like dates, names, subjects, etc.
5. If applicable, suggest next steps or actions

Respond in JSON format with:
{
    "answer": "your detailed response to the user",
    "confidence": "high/medium/low",
    "data_found": boolean,
    "relevant_items": [
        {
            "id": "item_id",
            "summary": "detailed summary with key information"
        }
    ],
    "suggested_actions": [
        {
            "action": "action description",
            "type": "send_message/create_event/etc."
        }
    ]
}
"""
            )
