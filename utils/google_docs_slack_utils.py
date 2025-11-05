"""
Google Docs to Slack integration
Converts and shares Google Docs documents to Slack
"""

import logging
from typing import Dict, Any, Optional
from helpers.google_docs_helpers import GoogleDocsHelpers
from helpers.slack_helpers import SlackHelpers

logger = logging.getLogger(__name__)


class GoogleDocsSlackUtils:
    """Utility class for Google Docs to Slack workflows"""

    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials
        self.google_docs_helpers = GoogleDocsHelpers()
        self.slack_helpers = SlackHelpers()

    async def share_document_summary_to_slack(
        self, document_id: str, channel: str, title: str = "", message_prefix: str = ""
    ) -> Dict[str, Any]:
        """
        Get Google Docs content and share summary to Slack

        Args:
            document_id: ID of the Google Docs document
            channel: Slack channel to post to
            title: Optional custom title
            message_prefix: Optional message prefix

        Returns:
            Dict with operation results
        """
        try:
            logger.info(f"Sharing document {document_id} to Slack channel {channel}")

            # Get document content
            doc_result = await self.google_docs_helpers.get_document_content(
                credentials=self.credentials.get("google_docs", {}).get(
                    "credentials", {}
                )
            )

            if not doc_result.get("success"):
                return doc_result

            doc_title = doc_result.get("title", "Untitled Document")
            content = doc_result.get("content", "")[:1000]  # First 1000 chars

            # Build Slack message
            message = f"{message_prefix}\n📄 *{title or doc_title}*\n{content}\n<https://docs.google.com/document/d/{document_id}/edit|View Document>"

            # Send to Slack
            slack_result = await self.slack_helpers.send_message(
                channel=channel,
                text=message,
                credentials=self.credentials.get("slack", {}).get("credentials", {}),
            )

            return slack_result

        except Exception as e:
            logger.error(f"Error sharing document to Slack: {str(e)}")
            return {"success": False, "error": str(e)}

    async def post_slack_message_to_document(
        self, channel: str, document_id: str, message_count: int = 10
    ) -> Dict[str, Any]:
        """
        Fetch recent Slack messages and append to Google Docs

        Args:
            channel: Slack channel to read from
            document_id: Google Docs document to append to
            message_count: Number of recent messages to fetch

        Returns:
            Dict with operation results
        """
        try:
            logger.info(
                f"Fetching messages from {channel} and appending to document {document_id}"
            )

            # Get recent Slack messages
            messages_result = await self.slack_helpers.get_channel_history(
                channel=channel,
                limit=message_count,
                credentials=self.credentials.get("slack", {}).get("credentials", {}),
            )

            if not messages_result.get("success"):
                return messages_result

            # Format messages
            content = f"\n\n--- Slack Messages from {channel} ({message_count} messages) ---\n"
            for msg in messages_result.get("messages", []):
                content += f"\n[{msg.get('user')}]: {msg.get('text')}\n"

            # Append to document
            append_result = await self.google_docs_helpers.append_to_document(
                document_id=document_id,
                content=content,
                credentials=self.credentials.get("google_docs", {}).get(
                    "credentials", {}
                ),
            )

            return append_result

        except Exception as e:
            logger.error(f"Error posting Slack messages to document: {str(e)}")
            return {"success": False, "error": str(e)}
