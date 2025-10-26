"""
Notion to Discord Utility Functions
Inter-app connector for automating Notion to Discord workflows
"""

import logging
from typing import Dict, Any, List

from helpers.notion_helpers import NotionHelpers
from helpers.discord_helpers import DiscordHelpers

logger = logging.getLogger(__name__)


class NotionDiscordUtils:
    """Utility functions for Notion to Discord automation"""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize with user credentials
        
        Args:
            credentials: Dict mapping app_type to credentials
        """
        self.notion_creds = credentials.get("notion", {}).get("credentials", {})
        self.discord_creds = credentials.get("discord", {}).get("credentials", {})
        
        self.notion_token = self.notion_creds.get("access_token")
        self.discord_token = self.discord_creds.get("access_token")
        
        if not self.notion_token or not self.discord_token:
            raise ValueError("Missing Notion or Discord credentials")
        
        logger.info("NotionDiscordUtils initialized")
    
    async def notion_pages_to_discord_messages(
        self,
        database_id: str,
        channel_id: str,
        filter: Dict[str, Any] = None,
        max_pages: int = 10
    ) -> Dict[str, Any]:
        """
        Query Notion database and send pages as Discord messages
        
        This function:
        1. Queries a Notion database
        2. Formats each page as a Discord message with embed
        3. Sends messages to specified Discord channel
        
        Args:
            database_id: Notion database ID to query
            channel_id: Discord channel ID
            filter: Notion query filter (optional)
            max_pages: Maximum number of pages to process
            
        Returns:
            Dict with success status and sent messages
        """
        try:
            logger.info(f"Starting notion_pages_to_discord_messages: database={database_id}, channel={channel_id}")
            
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
            
            # Step 2: Send each page as Discord message
            sent_messages = []
            errors = []
            
            for page in pages:
                try:
                    # Extract page information
                    title = self._extract_page_title(page)
                    page_url = page.get("url", "")
                    
                    # Create Discord embed
                    embed = {
                        "title": title,
                        "url": page_url,
                        "color": 0x5865F2,  # Discord blurple
                        "footer": {
                            "text": "From Notion"
                        }
                    }
                    
                    # Send to Discord
                    send_result = await DiscordHelpers.send_message(
                        access_token=self.discord_token,
                        channel_id=channel_id,
                        content=f"📄 New Notion page: **{title}**",
                        embeds=[embed]
                    )
                    
                    if send_result.get("success"):
                        sent_messages.append(send_result["message"])
                        logger.info(f"Sent Notion page to Discord: {title}")
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
                "message": f"Successfully sent {len(sent_messages)} Notion pages to Discord"
            }
            
        except Exception as e:
            logger.error(f"Error in notion_pages_to_discord_messages: {str(e)}", exc_info=True)
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
