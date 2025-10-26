"""
Notion to Gmail Utility Functions
Inter-app connector for automating Notion to Gmail workflows
"""

import logging
from typing import Dict, Any, List

from helpers.notion_helpers import NotionHelpers
from helpers.gmail_helpers import GmailHelpers

logger = logging.getLogger(__name__)


class NotionGmailUtils:
    """Utility functions for Notion to Gmail automation"""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize with user credentials
        
        Args:
            credentials: Dict mapping app_type to credentials
        """
        self.notion_creds = credentials.get("notion", {}).get("credentials", {})
        self.gmail_creds = credentials.get("gmail", {}).get("credentials", {})
        
        self.notion_token = self.notion_creds.get("access_token")
        self.gmail_token = self.gmail_creds.get("access_token")
        
        if not self.notion_token or not self.gmail_token:
            raise ValueError("Missing Notion or Gmail credentials")
        
        logger.info("NotionGmailUtils initialized")
    
    async def notion_pages_to_emails(
        self,
        database_id: str,
        recipient_email: str,
        filter: Dict[str, Any] = None,
        max_pages: int = 10
    ) -> Dict[str, Any]:
        """
        Query Notion database and send pages as emails
        
        This function:
        1. Queries a Notion database
        2. Formats each page as an email
        3. Sends emails via Gmail
        
        Args:
            database_id: Notion database ID to query
            recipient_email: Email recipient
            filter: Notion query filter (optional)
            max_pages: Maximum number of pages to process
            
        Returns:
            Dict with success status and sent emails
        """
        try:
            logger.info(f"Starting notion_pages_to_emails: database={database_id}, recipient={recipient_email}")
            
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
                    "emails_sent": 0,
                    "message": "No pages found in database"
                }
            
            # Step 2: Send each page as email
            sent_emails = []
            errors = []
            
            for page in pages:
                try:
                    # Extract page information
                    title = self._extract_page_title(page)
                    page_url = page.get("url", "")
                    
                    # Format email
                    subject = f"Notion Page: {title}"
                    body = f"Here's your Notion page:\n\n{title}\n\n{page_url}"
                    
                    # Send email
                    send_result = await GmailHelpers.send_message(
                        access_token=self.gmail_token,
                        to=recipient_email,
                        subject=subject,
                        body=body
                    )
                    
                    if send_result.get("success"):
                        sent_emails.append(send_result["message"])
                        logger.info(f"Sent Notion page as email: {title}")
                    else:
                        errors.append(f"Failed to send email for page: {title}")
                
                except Exception as e:
                    logger.error(f"Error processing Notion page: {str(e)}")
                    errors.append(str(e))
            
            return {
                "success": True,
                "emails_sent": len(sent_emails),
                "emails": sent_emails,
                "errors": errors,
                "message": f"Successfully sent {len(sent_emails)} Notion pages as emails"
            }
            
        except Exception as e:
            logger.error(f"Error in notion_pages_to_emails: {str(e)}", exc_info=True)
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
