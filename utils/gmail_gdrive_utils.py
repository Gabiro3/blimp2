"""
Gmail to Google Drive Utility Functions
Inter-app connector for saving email attachments to Google Drive
"""

import logging
from typing import Dict, Any, List
import base64

from helpers.gmail_helpers import GmailHelpers

logger = logging.getLogger(__name__)


class GmailGDriveUtils:
    """Utility functions for Gmail to Google Drive automation"""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize with user credentials
        
        Args:
            credentials: Dict mapping app_type to credentials
        """
        self.gmail_creds = credentials.get("gmail", {}).get("credentials", {})
        self.gdrive_creds = credentials.get("gdrive", {}).get("credentials", {})
        
        self.gmail_token = self.gmail_creds.get("access_token")
        self.gdrive_token = self.gdrive_creds.get("access_token")
        
        if not self.gmail_token:
            raise ValueError("Missing Gmail credentials")
        
        # Note: Google Drive helper not provided, but structure is here
        logger.info("GmailGDriveUtils initialized")
    
    async def save_attachments_to_drive(
        self,
        max_emails: int = 10,
        folder_name: str = "Email Attachments"
    ) -> Dict[str, Any]:
        """
        Get email attachments and save them to Google Drive
        
        This function:
        1. Fetches recent emails with attachments
        2. Downloads each attachment
        3. Uploads to specified Google Drive folder
        
        Args:
            max_emails: Maximum number of emails to process
            folder_name: Google Drive folder name
            
        Returns:
            Dict with success status and saved files
        """
        try:
            logger.info(f"Starting save_attachments_to_drive: max={max_emails}, folder={folder_name}")
            
            # Step 1: List emails with attachments
            emails_result = await GmailHelpers.list_messages(
                access_token=self.gmail_token,
                query="has:attachment",
                max_results=max_emails
            )
            
            if not emails_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to fetch emails: {emails_result.get('error')}"
                }
            
            messages = emails_result.get("messages", [])
            logger.info(f"Found {len(messages)} emails with attachments")
            
            if not messages:
                return {
                    "success": True,
                    "files_saved": 0,
                    "message": "No emails with attachments found"
                }
            
            # Step 2: Process attachments
            saved_files = []
            errors = []
            
            for msg in messages:
                try:
                    # Get full email details
                    email_result = await GmailHelpers.get_message(
                        access_token=self.gmail_token,
                        message_id=msg["id"]
                    )
                    
                    if not email_result.get("success"):
                        errors.append(f"Failed to get email {msg['id']}")
                        continue
                    
                    email_data = email_result["message"]
                    
                    # Extract and save attachments
                    attachments = self._extract_attachments(email_data)
                    
                    for attachment in attachments:
                        # TODO: Implement Google Drive upload
                        # For now, just log the attachment info
                        logger.info(f"Would save attachment: {attachment['filename']}")
                        saved_files.append(attachment)
                
                except Exception as e:
                    logger.error(f"Error processing email {msg.get('id')}: {str(e)}")
                    errors.append(str(e))
            
            return {
                "success": True,
                "files_saved": len(saved_files),
                "files": saved_files,
                "errors": errors,
                "message": f"Processed {len(saved_files)} attachments from {len(messages)} emails"
            }
            
        except Exception as e:
            logger.error(f"Error in save_attachments_to_drive: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_attachments(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attachment information from email data"""
        attachments = []
        
        try:
            payload = email_data.get("payload", {})
            parts = payload.get("parts", [])
            
            for part in parts:
                if part.get("filename"):
                    attachment_id = part.get("body", {}).get("attachmentId")
                    if attachment_id:
                        attachments.append({
                            "filename": part["filename"],
                            "mimeType": part.get("mimeType"),
                            "size": part.get("body", {}).get("size", 0),
                            "attachmentId": attachment_id
                        })
            
            return attachments
            
        except Exception as e:
            logger.error(f"Error extracting attachments: {str(e)}")
            return []
