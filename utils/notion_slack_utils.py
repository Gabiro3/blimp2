"""
Notion to Slack Utility Functions
Inter-app connector for automating Notion to Slack workflows
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from helpers.notion_helpers import NotionHelpers
from helpers.slack_helpers import SlackHelpers

logger = logging.getLogger(__name__)


class NotionSlackUtils:
    """Utility functions for Notion to Slack automation"""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize with user credentials
        
        Args:
            credentials: Dict mapping app_type to credentials
        """
        self.notion_creds = credentials.get("notion", {}).get("credentials", {})
        self.slack_creds = credentials.get("slack", {}).get("credentials", {})
        
        self.notion_token = self.notion_creds.get("access_token")
        self.slack_token = self.slack_creds.get("access_token")
        
        if not self.notion_token or not self.slack_token:
            raise ValueError("Missing Notion or Slack credentials")
        
        logger.info("NotionSlackUtils initialized")
    
    async def notion_pages_to_slack_messages(
        self,
        database_id: str,
        channel: str,
        filter: Dict[str, Any] = None,
        max_pages: int = 10
    ) -> Dict[str, Any]:
        """
        Query Notion database and send pages as Slack messages
        
        This function:
        1. Queries a Notion database
        2. Formats each page as a Slack message
        3. Sends messages to specified Slack channel
        
        Args:
            database_id: Notion database ID to query
            channel: Slack channel ID or name
            filter: Notion query filter (optional)
            max_pages: Maximum number of pages to process
            
        Returns:
            Dict with success status and sent messages
        """
        try:
            logger.info(f"Starting notion_pages_to_slack_messages: database={database_id}, channel={channel}")
            
            # Step 1: Query Notion database
            query_result = await NotionHelpers.query_database(
                access_token=self.notion_token,
                database_id=database_id,
                filter=filter,
                page_size=max_pages
            )
            
            if not query_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to query Notion database: {query_result.get('error')}"
                }
            
            pages = query_result.get("results", [])
            logger.info(f"Found {len(pages)} Notion pages to process")
            
            if not pages:
                return {
                    "success": True,
                    "messages_sent": 0,
                    "message": "No pages found in database"
                }
            
            # Step 2: Send each page as Slack message
            sent_messages = []
            errors = []
            
            for page in pages:
                try:
                    # Extract page title
                    title = self._extract_page_title(page)
                    page_url = page.get("url", "")
                    
                    # Format Slack message
                    message_text = f"📄 *{title}*\n{page_url}"
                    
                    # Send to Slack
                    send_result = await SlackHelpers.send_message(
                        access_token=self.slack_token,
                        channel=channel,
                        text=message_text
                    )
                    
                    if send_result.get("success"):
                        sent_messages.append(send_result["message"])
                        logger.info(f"Sent Notion page to Slack: {title}")
                    else:
                        errors.append(f"Failed to send page: {title}")
                
                except Exception as e:
                    logger.error(f"Error processing Notion page: {str(e)}")
                    errors.append(str(e))
            
            return {
                "success": True,
                "messages_sent": len(sent_messages),
                "messages": sent_messages,
                "errors": errors,
                "message": f"Successfully sent {len(sent_messages)} Notion pages to Slack"
            }
            
        except Exception as e:
            logger.error(f"Error in notion_pages_to_slack_messages: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_page_title(self, page: Dict[str, Any]) -> str:
        """Extract title from Notion page properties"""
        try:
            properties = page.get("properties", {})
            
            # Try common title property names
            for prop_name in ["Name", "Title", "title", "name"]:
                if prop_name in properties:
                    prop = properties[prop_name]
                    if prop.get("type") == "title":
                        title_array = prop.get("title", [])
                        if title_array:
                            return title_array[0].get("plain_text", "Untitled")
            
            return "Untitled"
            
        except Exception as e:
            logger.error(f"Error extracting page title: {str(e)}")
            return "Untitled"
