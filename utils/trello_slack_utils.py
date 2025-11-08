"""
Trello to Slack integration utilities
"""

import logging
from typing import Dict, Any, Optional
from helpers.trello_helpers import TrelloHelpers
from helpers.slack_helpers import SlackHelpers

logger = logging.getLogger(__name__)


class TrelloSlackUtils:
    """Utilities for integrating Trello with Slack"""

    def __init__(self, trello_creds: Dict[str, Any], slack_creds: Dict[str, Any]):
        """Initialize with credentials"""
        self.trello_creds = trello_creds
        self.slack_creds = slack_creds

    async def send_board_updates_to_slack(
        self, board_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Send Trello board updates to Slack"""
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
            message = f"📊 *Trello Board Update*\n\nBoard has {len(lists)} lists:\n"

            for list_item in lists:
                message += f"• *{list_item['name']}*\n"

            slack_helper = SlackHelpers()
            send_result = await slack_helper.send_message(
                access_token=self.slack_creds.get("access_token"),
                channel_id=channel_id,
                text=message,
            )

            if not send_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to send message: {send_result.get('error')}",
                }

            logger.info(f"Sent board update to Slack")
            return {"success": True, "message": "Board update sent to Slack"}

        except Exception as e:
            logger.error(
                f"Error in send_board_updates_to_slack: {str(e)}", exc_info=True
            )
            return {"success": False, "error": str(e)}
