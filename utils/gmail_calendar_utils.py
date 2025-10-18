"""
Gmail to Google Calendar Utility Functions
Inter-app connector for automating email to calendar workflows
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
import re

from helpers.gmail_helpers import GmailHelpers
from helpers.gcalendar_helpers import GCalendarHelpers

logger = logging.getLogger(__name__)


class GmailCalendarUtils:
    """Utility functions for Gmail to Google Calendar automation"""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize with user credentials
        
        Args:
            credentials: Dict mapping app_type to credentials
        """
        self.gmail_creds = credentials.get("gmail", {}).get("credentials", {})
        self.calendar_creds = credentials.get("gcalendar", {}).get("credentials", {})
        
        self.gmail_token = self.gmail_creds.get("access_token")
        self.calendar_token = self.calendar_creds.get("access_token")
        
        if not self.gmail_token or not self.calendar_token:
            raise ValueError("Missing Gmail or Calendar credentials")
        
        logger.info("GmailCalendarUtils initialized")
    
    async def emails_to_calendar_events(
        self,
        max_emails: int = 10,
        query: str = "is:unread"
    ) -> Dict[str, Any]:
        """
        Get recent emails and create calendar events from them
        
        This function:
        1. Fetches recent emails matching the query
        2. Extracts relevant information (subject, body, dates)
        3. Creates calendar events for each email
        
        Args:
            max_emails: Maximum number of emails to process
            query: Gmail search query
            
        Returns:
            Dict with success status and created events
        """
        try:
            logger.info(f"Starting emails_to_calendar_events: max={max_emails}, query={query}")
            
            # Step 1: List emails
            emails_result = await GmailHelpers.list_messages(
                access_token=self.gmail_token,
                query=query,
                max_results=max_emails
            )
            
            if not emails_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to fetch emails: {emails_result.get('error')}"
                }
            
            messages = emails_result.get("messages", [])
            logger.info(f"Found {len(messages)} emails to process")
            
            if not messages:
                return {
                    "success": True,
                    "events_created": 0,
                    "message": "No emails found matching query"
                }
            
            # Step 2: Process each email and create calendar events
            created_events = []
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
                    
                    # Extract email information
                    subject = self._get_header(email_data, "Subject")
                    from_email = self._get_header(email_data, "From")
                    date_str = self._get_header(email_data, "Date")
                    body = self._extract_body(email_data)
                    
                    # Create calendar event
                    event_result = await self._create_event_from_email(
                        subject=subject,
                        from_email=from_email,
                        body=body,
                        email_date=date_str
                    )
                    
                    if event_result.get("success"):
                        created_events.append(event_result["event"])
                        logger.info(f"Created event for email: {subject}")
                    else:
                        errors.append(f"Failed to create event for: {subject}")
                
                except Exception as e:
                    logger.error(f"Error processing email {msg.get('id')}: {str(e)}")
                    errors.append(str(e))
            
            return {
                "success": True,
                "events_created": len(created_events),
                "events": created_events,
                "errors": errors,
                "message": f"Successfully created {len(created_events)} calendar events from {len(messages)} emails"
            }
            
        except Exception as e:
            logger.error(f"Error in emails_to_calendar_events: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _create_event_from_email(
        self,
        subject: str,
        from_email: str,
        body: str,
        email_date: str
    ) -> Dict[str, Any]:
        """
        Create a calendar event from email data
        
        Args:
            subject: Email subject
            from_email: Sender email
            body: Email body
            email_date: Email date string
            
        Returns:
            Dict with event creation result
        """
        try:
            # Parse email date or use current time
            try:
                # Simple date parsing - enhance as needed
                event_start = datetime.utcnow()
            except:
                event_start = datetime.utcnow()
            
            # Event duration: 1 hour by default
            event_end = event_start + timedelta(hours=1)
            
            # Format times as ISO 8601
            start_time = event_start.isoformat() + "Z"
            end_time = event_end.isoformat() + "Z"
            
            # Create event description
            description = f"From: {from_email}\n\n{body[:500]}"  # Limit body length
            
            # Create calendar event
            result = await GCalendarHelpers.create_event(
                access_token=self.calendar_token,
                summary=f"📧 {subject}",
                start_time=start_time,
                end_time=end_time,
                description=description,
                timezone="UTC"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating event from email: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_header(self, email_data: Dict[str, Any], header_name: str) -> str:
        """Extract header value from email data"""
        headers = email_data.get("payload", {}).get("headers", [])
        for header in headers:
            if header.get("name") == header_name:
                return header.get("value", "")
        return ""
    
    def _extract_body(self, email_data: Dict[str, Any]) -> str:
        """Extract body text from email data"""
        try:
            payload = email_data.get("payload", {})
            
            # Try to get plain text body
            if "parts" in payload:
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain":
                        body_data = part.get("body", {}).get("data", "")
                        if body_data:
                            import base64
                            return base64.urlsafe_b64decode(body_data).decode("utf-8")
            
            # Fallback to snippet
            return email_data.get("snippet", "")
            
        except Exception as e:
            logger.error(f"Error extracting email body: {str(e)}")
            return email_data.get("snippet", "")
