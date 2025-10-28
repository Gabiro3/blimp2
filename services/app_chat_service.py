"""
App Chat Service
Handles AI-powered chat interactions with user's connected apps
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai

from helpers.gmail_helpers import GMAIL_FUNCTIONS
from helpers.slack_helpers import SLACK_FUNCTIONS
from helpers.gcalendar_helpers import GCALENDAR_FUNCTIONS
from helpers.gdrive_helpers import GDRIVE_FUNCTIONS

logger = logging.getLogger(__name__)


class AppChatService:
    """Service for AI-powered app chat interactions"""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash-exp")
            logger.info("App Chat service initialized successfully")
        else:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            self.model = None

    def is_configured(self) -> bool:
        """Check if service is properly configured"""
        return self.model is not None

    async def analyze_query(
        self, query: str, inquiry_app: str, connected_apps: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze user query and determine what data to fetch

        Args:
            query: User's question/request
            inquiry_app: Primary app to query (gmail, slack, gcalendar)
            connected_apps: List of user's connected apps

        Returns:
            Dict with data fetching plan
        """
        try:
            if not self.model:
                return {"success": False, "error": "App Chat service not configured"}

            # Get available functions for the inquiry app
            available_functions = self._get_app_functions(inquiry_app)

            # Build system prompt
            system_prompt = self._build_query_analysis_prompt(
                inquiry_app=inquiry_app,
                available_functions=available_functions,
                connected_apps=connected_apps,
            )

            # Build user message
            user_message = f"""
User Query: {query}

Analyze this query and determine:
1. What data needs to be fetched from {inquiry_app}?
2. Which helper functions should be called?
3. What parameters should be used?
4. Should any actions be taken (e.g., send a reply)?

Respond in JSON format with:
{{
    "data_fetch_plan": {{
        "app": "app_name",
        "function": "function_name",
        "parameters": {{}},
        "description": "what data this will fetch"
    }},
    "actions": [
        {{
            "type": "send_message" or "create_event" etc.,
            "app": "app_name",
            "parameters": {{}},
            "description": "what this action does"
        }}
    ],
    "reasoning": "explanation of the plan"
}}
"""

            # Call Gemini
            response = self.model.generate_content(
                [system_prompt, user_message],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3, response_mime_type="application/json"
                ),
            )

            # Parse response
            result = json.loads(response.text)
            logger.info(f"Query analysis: {result.get('reasoning')}")

            return {
                "success": True,
                "data_fetch_plan": result["data_fetch_plan"],
                "actions": result.get("actions", []),
                "reasoning": result.get("reasoning"),
            }

        except Exception as e:
            logger.error(f"Error analyzing query: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def generate_response(
        self,
        query: str,
        fetched_data: List[Dict[str, Any]],
        data_type: str,
        inquiry_app: str = None,
        context: Optional[Dict[str, Any]] = None,
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
            if not self.model:
                return {"success": False, "error": "App Chat service not configured"}

            # Build prompt
            system_prompt = self._build_response_generation_prompt(
                inquiry_app, data_type
            )

            # Build user message
            user_message = f"""
User Query: {query}

Fetched Data ({data_type}):
{json.dumps(fetched_data, indent=2)}

Additional Context: {json.dumps(context) if context else "None"}

Based on the user's query and the fetched data, provide a helpful, accurate, and DETAILED response.
"""

            # Call Gemini
            response = self.model.generate_content(
                [system_prompt, user_message],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4, response_mime_type="application/json"
                ),
            )

            # Parse response
            result = json.loads(response.text)
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
            "google_drive": GDRIVE_FUNCTIONS,
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
2. Use 'time_min' and 'time_max' for date ranges (ISO 8601 format)
3. Use 'q' parameter for text search in event titles/descriptions
4. Set 'max_results' parameter (default: 10)
5. IMPORTANT: Include event title, start/end times, location, attendees, and description

Common Query Patterns:
- "Today's meetings" → list_events(time_min="2024-01-15T00:00:00Z", time_max="2024-01-15T23:59:59Z")
- "Meetings with [person]" → list_events(q="person name", max_results=10)
- "Next week's events" → list_events(time_min="start_of_week", time_max="end_of_week")
- "Create meeting" → create_event action

Example Response:
{{
    "data_fetch_plan": {{
        "app": "gcalendar",
        "function": "list_events",
        "parameters": {{"time_min": "2024-01-15T00:00:00Z", "time_max": "2024-01-22T23:59:59Z", "max_results": 20}},
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
        elif inquiry_app and inquiry_app.lower() == "gcalendar":
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

4. If no events match: Clearly state no matching events were found

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
