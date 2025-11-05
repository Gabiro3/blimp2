"""
Trello to Gmail integration utilities
"""

import logging
from typing import Dict, Any
from helpers.trello_helpers import TrelloHelpers
from helpers.gmail_helpers import GmailHelpers

logger = logging.getLogger(__name__)


class TrelloGmailUtils:
    """Utilities for integrating Trello with Gmail"""

    def __init__(self, trello_creds: Dict[str, Any], gmail_creds: Dict[str, Any]):
        """Initialize with credentials"""
        self.trello_creds = trello_creds
        self.gmail_creds = gmail_creds

    async def send_board_summary_via_email(
        self, board_id: str, recipient_email: str
    ) -> Dict[str, Any]:
        """Send Trello board summary via email"""
        try:
            lists_result = await TrelloHelpers.get_board_lists(
                access_token=self.trello_creds.get("access_token"), board_id=board_id
            )

            if not lists_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to fetch board: {lists_result.get('error')}",
                }

            lists = lists_result.get("lists", [])
            subject = f"Trello Board Summary"
            body = f"Board Summary\n\nLists:\n"

            for list_item in lists:
                body += f"- {list_item['name']}\n"

            gmail_helper = GmailHelpers()
            send_result = await gmail_helper.send_message(
                access_token=self.gmail_creds.get("access_token"),
                credentials=self.gmail_creds,
                to=recipient_email,
                subject=subject,
                body=body,
            )

            if not send_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to send email: {send_result.get('error')}",
                }

            logger.info(f"Sent board summary to {recipient_email}")
            return {"success": True, "message": "Board summary sent via email"}

        except Exception as e:
            logger.error(
                f"Error in send_board_summary_via_email: {str(e)}", exc_info=True
            )
            return {"success": False, "error": str(e)}
