"""
Google Calendar to Slack Utility Functions
Inter-app connector for automating Google Calendar to Slack workflows
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from helpers.gcalendar_helpers import GCalendarHelpers
from helpers.slack_helpers import SlackHelpers

logger = logging.getLogger(__name__)


class GCalendarSlackUtils:
    """Utility functions for Google Calendar to Slack automation"""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize with user credentials
        
        Args:
            credentials: Dict mapping app_type to credentials
        """
        self.calendar_creds = credentials.get("gcalendar", {}).get("credentials", {})
        self.slack_creds = credentials.get("slack", {}).get("credentials", {})
        
        self.calendar_token = self.calendar_creds.get("access_token")
        self.slack_token = self.slack_creds.get("access_token")
        
        if not self.calendar_token or not self.slack_token:
            raise ValueError("Missing Google Calendar or Slack credentials")
        
        logger.info("GCalendarSlackUtils initialized")
    
    async def calendar_events_to_slack_messages(
        self,
        channel: str,
        time_min: str = None,
        time_max: str = None,
        max_events: int = 10
    ) -> Dict[str, Any]:
        """
        Get calendar events and send them as Slack messages
        
        This function:
        1. Fetches upcoming calendar events
        2. Formats each event as a Slack message
        3. Sends messages to specified Slack channel
        
        Args:
            channel: Slack channel ID or name
            time_min: Start time for events (ISO format)
            time_max: End time for events (ISO format)
            max_events: Maximum number of events to process
            
        Returns:
            Dict with success status and sent messages
        """
        try:
            logger.info(f"Starting calendar_events_to_slack_messages: channel={channel}")
            
            # Default to today's events if no time range specified
            if not time_min:
                time_min = datetime.utcnow().isoformat() + "Z"
            if not time_max:
                time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
            
            # Step 1: List calendar events
            events_result = await GCalendarHelpers.list_events(
                access_token=self.calendar_token,
                time_min=time_min,
                time_max=time_max,
                max_results=max_events
            )
            
            if not events_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to fetch calendar events: {events_result.get('error')}"
                }
            
            events = events_result.get("events", [])
            logger.info(f"Found {len(events)} calendar events to process")
            
            if not events:
                return {
                    "success": True,
                    "messages_sent": 0,
                    "message": "No calendar events found"
                }
            
            # Step 2: Send each event as Slack message
            sent_messages = []
            errors = []
            
            for event in events:
                try:
                    # Extract event information
                    summary = event.get("summary", "No Title")
                    start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
                    end = event.get("end", {}).get("dateTime", event.get("end", {}).get("date", ""))
                    description = event.get("description", "")
                    html_link = event.get("htmlLink", "")
                    
                    # Format Slack message
                    message_text = self._format_event_message(
                        summary=summary,
                        start=start,
                        end=end,
                        description=description,
                        link=html_link
                    )
                    
                    # Send to Slack
                    send_result = await SlackHelpers.send_message(
                        access_token=self.slack_token,
                        channel=channel,
                        text=message_text
                    )
                    
                    if send_result.get("success"):
                        sent_messages.append(send_result["message"])
                        logger.info(f"Sent calendar event to Slack: {summary}")
                    else:
                        errors.append(f"Failed to send event: {summary}")
                
                except Exception as e:
                    logger.error(f"Error processing calendar event: {str(e)}")
                    errors.append(str(e))
            
            return {
                "success": True,
                "messages_sent": len(sent_messages),
                "messages": sent_messages,
                "errors": errors,
                "message": f"Successfully sent {len(sent_messages)} calendar events to Slack"
            }
            
        except Exception as e:
            logger.error(f"Error in calendar_events_to_slack_messages: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_event_message(
        self,
        summary: str,
        start: str,
        end: str,
        description: str,
        link: str
    ) -> str:
        """Format calendar event as Slack message"""
        try:
            # Parse and format dates
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            
            start_formatted = start_dt.strftime("%B %d, %Y at %I:%M %p")
            end_formatted = end_dt.strftime("%I:%M %p")
            
            message = f"📅 *{summary}*\n"
            message += f"🕐 {start_formatted} - {end_formatted}\n"
            
            if description:
                message += f"📝 {description[:200]}\n"
            
            if link:
                message += f"🔗 <{link}|View in Calendar>"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting event message: {str(e)}")
            return f"📅 *{summary}*\nStart: {start}\nEnd: {end}"
