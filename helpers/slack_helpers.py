"""
Slack helper functions using Slack SDK.
Provides operations for sending messages, managing channels, etc.
"""

from typing import Dict, List, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging

logger = logging.getLogger(__name__)


class SlackHelpers:
    """Helper class for Slack operations."""

    @staticmethod
    def _get_client(access_token: str) -> WebClient:
        """Create Slack client with access token."""
        return WebClient(token=access_token)

    @staticmethod
    async def send_message(
        access_token: str,
        channel: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a Slack message.

        Args:
            access_token: User's Slack access token
            channel: Channel ID or name
            text: Message text
            blocks: Message blocks for rich formatting
            thread_ts: Thread timestamp to reply to

        Returns:
            Dict with sent message data
        """
        try:
            client = SlackHelpers._get_client(access_token)

            params = {"channel": channel, "text": text}

            if blocks:
                params["blocks"] = blocks
            if thread_ts:
                params["thread_ts"] = thread_ts

            response = client.chat_postMessage(**params)

            return {"success": True, "message": response.data}

        except SlackApiError as error:
            logger.error(f"Slack API error sending message: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def list_channels(
        access_token: str,
        types: str = "public_channel,private_channel",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        List Slack channels.

        Args:
            access_token: User's Slack access token
            types: Channel types to include
            limit: Maximum number of channels to return

        Returns:
            Dict with channels list
        """
        try:
            client = SlackHelpers._get_client(access_token)

            response = client.conversations_list(types=types, limit=limit)

            return {"success": True, "channels": response.data.get("channels", [])}

        except SlackApiError as error:
            logger.error(f"Slack API error listing channels: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_channel_history(
        access_token: str, channel: str, limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get message history from a Slack channel.

        Args:
            access_token: User's Slack access token
            channel: Channel ID
            limit: Maximum number of messages to return

        Returns:
            Dict with channel messages
        """
        try:
            client = SlackHelpers._get_client(access_token)

            response = client.conversations_history(channel=channel, limit=limit)

            messages = response.data.get("messages", [])

            return {"success": True, "messages": messages, "count": len(messages)}

        except SlackApiError as error:
            logger.error(f"Slack API error getting channel history: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def search_messages(
        access_token: str, query: str, count: int = 20
    ) -> Dict[str, Any]:
        """
        Search for messages in Slack workspace.

        Args:
            access_token: User's Slack access token
            query: Search query
            count: Number of results to return

        Returns:
            Dict with search results
        """
        try:
            client = SlackHelpers._get_client(access_token)

            response = client.search_messages(query=query, count=count)

            matches = response.data.get("messages", {}).get("matches", [])

            return {"success": True, "messages": matches, "count": len(matches)}

        except SlackApiError as error:
            logger.error(f"Slack API error searching messages: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_user_info(access_token: str, user_id: str) -> Dict[str, Any]:
        """
        Get information about a Slack user.

        Args:
            access_token: User's Slack access token
            user_id: User ID

        Returns:
            Dict with user information
        """
        try:
            client = SlackHelpers._get_client(access_token)

            response = client.users_info(user=user_id)

            return {"success": True, "user": response.data.get("user", {})}

        except SlackApiError as error:
            logger.error(f"Slack API error getting user info: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_recent_mentions(
        access_token: str, user_id: str, limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get recent messages where the user was mentioned.

        Args:
            access_token: User's Slack access token
            user_id: User ID to search for mentions
            limit: Maximum number of messages to return

        Returns:
            Dict with messages containing mentions
        """
        try:
            # Search for messages mentioning the user
            query = f"<@{user_id}>"

            result = await SlackHelpers.search_messages(
                access_token=access_token, query=query, count=limit
            )

            if result.get("success"):
                return {
                    "success": True,
                    "mentions": result.get("messages", []),
                    "count": result.get("count", 0),
                }

            return result

        except Exception as error:
            logger.error(f"Error getting recent mentions: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_unread_messages(access_token: str, channel: str) -> Dict[str, Any]:
        """
        Get unread messages from a channel.

        Args:
            access_token: User's Slack access token
            channel: Channel ID

        Returns:
            Dict with unread messages
        """
        try:
            client = SlackHelpers._get_client(access_token)

            # Get channel info to find last read timestamp
            channel_info = client.conversations_info(channel=channel)
            last_read = channel_info.data.get("channel", {}).get("last_read", "0")

            # Get messages after last read
            response = client.conversations_history(
                channel=channel, oldest=last_read, limit=100
            )

            messages = response.data.get("messages", [])

            return {
                "success": True,
                "unread_messages": messages,
                "count": len(messages),
            }

        except SlackApiError as error:
            logger.error(f"Slack API error getting unread messages: {error}")
            return {"success": False, "error": str(error)}


# Function registry for Gemini
SLACK_FUNCTIONS = {
    "send_message": {
        "name": "send_message",
        "description": "Send a Slack message",
        "parameters": {
            "channel": "Channel ID or name",
            "text": "Message text",
            "blocks": "Message blocks for rich formatting (optional)",
            "thread_ts": "Thread timestamp to reply to (optional)",
        },
    },
    "list_channels": {
        "name": "list_channels",
        "description": "List Slack channels",
        "parameters": {
            "types": "Channel types to include (default: 'public_channel,private_channel')",
            "limit": "Maximum number of channels to return (default: 100)",
        },
    },
    "get_channel_history": {
        "name": "get_channel_history",
        "description": "Get message history from a Slack channel",
        "parameters": {
            "channel": "Channel ID",
            "limit": "Maximum number of messages to return (default: 20)",
        },
    },
    "search_messages": {
        "name": "search_messages",
        "description": "Search for messages in Slack workspace",
        "parameters": {
            "query": "Search query",
            "count": "Number of results to return (default: 20)",
        },
    },
    "get_user_info": {
        "name": "get_user_info",
        "description": "Get information about a Slack user",
        "parameters": {"user_id": "User ID"},
    },
    "get_recent_mentions": {
        "name": "get_recent_mentions",
        "description": "Get recent messages where the user was mentioned",
        "parameters": {
            "user_id": "User ID to search for mentions",
            "limit": "Maximum number of messages to return (default: 20)",
        },
    },
    "get_unread_messages": {
        "name": "get_unread_messages",
        "description": "Get unread messages from a channel",
        "parameters": {"channel": "Channel ID"},
    },
}
