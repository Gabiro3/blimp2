"""
Email Service - Handles email notifications using Resend
"""

import os
import logging
from typing import List, Dict, Any, Optional
import resend

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via Resend"""

    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")

        if not self.api_key:
            logger.warning("Resend API key not found in environment variables")
        else:
            resend.api_key = self.api_key
            logger.info("Email service initialized with Resend")

    async def send_team_workflow_invitation(
        self,
        invitee_email: str,
        inviter_name: str,
        workflow_title: str,
        workflow_description: str,
        invitation_link: str,
    ) -> Dict[str, Any]:
        """
        Send team workflow invitation email

        Args:
            invitee_email: Email address of the person being invited
            inviter_name: Name of the person sending the invitation
            workflow_title: Title of the workflow
            workflow_description: Description of what the workflow does
            invitation_link: Link to accept the invitation

        Returns:
            Dict with success status and message
        """
        try:
            if not self.api_key:
                return {"success": False, "error": "Email service not configured"}

            from_email = os.getenv("RESEND_FROM_EMAIL", "noreply@blimp.app")

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px;
                        border-radius: 10px 10px 0 0;
                        text-align: center;
                    }}
                    .content {{
                        background: #f9fafb;
                        padding: 30px;
                        border-radius: 0 0 10px 10px;
                    }}
                    .workflow-info {{
                        background: white;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                        border-left: 4px solid #667eea;
                    }}
                    .button {{
                        display: inline-block;
                        background: #667eea;
                        color: white;
                        padding: 12px 30px;
                        text-decoration: none;
                        border-radius: 6px;
                        margin: 20px 0;
                        font-weight: 600;
                    }}
                    .footer {{
                        text-align: center;
                        color: #6b7280;
                        font-size: 14px;
                        margin-top: 30px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🚀 Team Workflow Invitation</h1>
                </div>
                <div class="content">
                    <p>Hi there!</p>
                    <p><strong>{inviter_name}</strong> has invited you to join a team workflow on Blimp.</p>
                    
                    <div class="workflow-info">
                        <h3>{workflow_title}</h3>
                        <p>{workflow_description}</p>
                    </div>
                    
                    <p>By joining this workflow, you'll be able to:</p>
                    <ul>
                        <li>Collaborate with your team on automated tasks</li>
                        <li>Execute workflows that benefit the entire team</li>
                        <li>Stay in sync with team automation</li>
                    </ul>
                    
                    <center>
                        <a href="{invitation_link}" class="button">Accept Invitation</a>
                    </center>
                    
                    <p style="margin-top: 30px; font-size: 14px; color: #6b7280;">
                        If you didn't expect this invitation, you can safely ignore this email.
                    </p>
                </div>
                <div class="footer">
                    <p>Sent by Blimp - AI-Powered Workflow Automation</p>
                </div>
            </body>
            </html>
            """

            params = {
                "from": from_email,
                "to": [invitee_email],
                "subject": f"{inviter_name} invited you to join '{workflow_title}' on Blimp",
                "html": html_content,
            }

            email = resend.Emails.send(params)

            logger.info(
                f"Invitation email sent to {invitee_email} for workflow '{workflow_title}'"
            )

            return {
                "success": True,
                "email_id": email.get("id"),
                "message": f"Invitation sent to {invitee_email}",
            }

        except Exception as e:
            logger.error(f"Error sending invitation email: {str(e)}")
            return {"success": False, "error": str(e)}

    async def send_workflow_execution_notification(
        self,
        recipient_email: str,
        workflow_title: str,
        execution_status: str,
        execution_summary: str,
    ) -> Dict[str, Any]:
        """
        Send workflow execution notification

        Args:
            recipient_email: Email of the team member
            workflow_title: Title of the workflow
            execution_status: Status (success/failed)
            execution_summary: Summary of what happened

        Returns:
            Dict with success status
        """
        try:
            if not self.api_key:
                return {"success": False, "error": "Email service not configured"}

            from_email = os.getenv("RESEND_FROM_EMAIL", "noreply@blimp.app")

            status_color = "#10b981" if execution_status == "success" else "#ef4444"
            status_emoji = "✅" if execution_status == "success" else "❌"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: {status_color};
                        color: white;
                        padding: 30px;
                        border-radius: 10px 10px 0 0;
                        text-align: center;
                    }}
                    .content {{
                        background: #f9fafb;
                        padding: 30px;
                        border-radius: 0 0 10px 10px;
                    }}
                    .summary {{
                        background: white;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{status_emoji} Workflow Execution {execution_status.title()}</h1>
                </div>
                <div class="content">
                    <h3>{workflow_title}</h3>
                    <div class="summary">
                        <p>{execution_summary}</p>
                    </div>
                </div>
            </body>
            </html>
            """

            params = {
                "from": from_email,
                "to": [recipient_email],
                "subject": f"Workflow '{workflow_title}' - {execution_status.title()}",
                "html": html_content,
            }

            email = resend.Emails.send(params)

            return {"success": True, "email_id": email.get("id")}

        except Exception as e:
            logger.error(f"Error sending execution notification: {str(e)}")
            return {"success": False, "error": str(e)}
