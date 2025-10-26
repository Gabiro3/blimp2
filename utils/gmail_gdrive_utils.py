"""
Gmail to Google Drive Utility Functions
Inter-app connector for saving email attachments to Google Drive
"""

import logging
from typing import Dict, Any, List, Optional
import base64
import os

from helpers.gmail_helpers import GmailHelpers
from helpers.gdrive_helpers import GDriveHelpers

logger = logging.getLogger(__name__)


class GmailGDriveUtils:
    """Utility functions for Gmail to Google Drive automation"""

    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize with user credentials

        Args:
            credentials: Dict mapping app_type to credentials
        """
        base_creds = credentials.get("gmail", {}).get("credentials", {})

        # Construct the full credentials object
        self.gmail_creds = {
            **base_creds,
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "token_uri": "https://oauth2.googleapis.com/token",  # standard Google token refresh endpoint
        }
        self.gdrive_creds = credentials.get("google_drive", {}).get("credentials", {})

        if not self.gmail_creds or not self.gmail_creds.get("access_token"):
            raise ValueError("Missing Gmail credentials")

        if not self.gdrive_creds or not self.gdrive_creds.get("access_token"):
            raise ValueError("Missing Google Drive credentials")

        logger.info("GmailGDriveUtils initialized")

    async def save_attachments_to_drive(
        self,
        max_emails: int = 10,
        folder_name: str = "Email Attachments",
        sender_email: Optional[str] = None,
        email_labels: Optional[str] = None,
        file_types: Optional[str] = None,  # comma-separated extensions
        min_file_size_kb: Optional[int] = None,
        max_file_size_kb: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_archived: bool = False,
        unread_only: bool = True,
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
            sender_email: Filter by sender email
            email_labels: Gmail label to filter
            file_types: Comma-separated file extensions to include (e.g. ".pdf, .jpg")
            min_file_size_kb: Minimum file size (KB)
            max_file_size_kb: Maximum file size (KB)
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)
            include_archived: Whether to include archived emails
            unread_only: Whether to include only unread emails

        Returns:
            Dict with success status and saved files
        """
        try:
            logger.info(
                f"Starting save_attachments_to_drive: max={max_emails}, folder={folder_name}"
            )
            query_parts = ["has:attachment"]

            if sender_email:
                query_parts.append(f"from:{sender_email}")

            if email_labels:
                query_parts.append(f"label:{email_labels}")

            if unread_only:
                query_parts.append("is:unread")

            if not include_archived:
                query_parts.append("in:inbox")

            if date_from:
                query_parts.append(f"after:{date_from}")

            if date_to:
                query_parts.append(f"before:{date_to}")

            final_query = " ".join(query_parts)
            logger.info(f"Gmail query built: {final_query}")

            folder_result = await GDriveHelpers.find_folder(
                access_token=self.gdrive_creds.get("access_token"),
                refresh_token=self.gdrive_creds.get("refresh_token"),
                folder_name=folder_name,
            )

            folder_id = None
            if folder_result.get("success") and folder_result.get("folder"):
                folder_id = folder_result["folder"]["id"]
                logger.info(f"Found existing folder: {folder_id}")
            else:
                # Create the folder
                create_result = await GDriveHelpers.create_folder(
                    access_token=self.gdrive_creds.get("access_token"),
                    refresh_token=self.gdrive_creds.get("refresh_token"),
                    folder_name=folder_name,
                )
                if create_result.get("success"):
                    folder_id = create_result["folder"]["id"]
                    logger.info(f"Created new folder: {folder_id}")
                else:
                    logger.warning(
                        f"Could not create folder: {create_result.get('error')}"
                    )

            # Step 1: List emails with attachments
            emails_result = await GmailHelpers.list_messages(
                access_token=self.gmail_creds.get("access_token"),
                credentials=self.gmail_creds,
                query=final_query,
                max_results=max_emails,
            )

            if not emails_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to fetch emails: {emails_result.get('error')}",
                }

            messages = emails_result.get("messages", [])
            logger.info(f"Found {len(messages)} emails with attachments")

            if not messages:
                return {
                    "success": True,
                    "files_saved": 0,
                    "message": "No emails with attachments found",
                }

            # Step 2: Process attachments
            saved_files = []
            errors = []

            for msg in messages:
                try:
                    # Get full email details
                    email_result = await GmailHelpers.get_message(
                        access_token=self.gmail_creds.get("access_token"),
                        credentials=self.gmail_creds,
                        message_id=msg["id"],
                    )

                    if not email_result.get("success"):
                        errors.append(f"Failed to get email {msg['id']}")
                        continue

                    email_data = email_result["message"]

                    # Extract and save attachments
                    attachments = self._extract_attachments(email_data)

                    for attachment in attachments:
                        filename = attachment.get("filename", "")
                        try:
                            # Download attachment data from Gmail
                            if file_types:
                                allowed_exts = [
                                    ext.strip().lower() for ext in file_types.split(",")
                                ]
                                if not any(
                                    filename.lower().endswith(ext)
                                    for ext in allowed_exts
                                ):
                                    logger.debug(
                                        f"Skipping {filename}: type not in {allowed_exts}"
                                    )
                                continue
                            attachment_result = await GmailHelpers.get_attachment(
                                access_token=self.gmail_creds.get("access_token"),
                                credentials=self.gmail_creds,
                                message_id=msg["id"],
                                attachment_id=attachment["attachmentId"],
                            )

                            if not attachment_result.get("success"):
                                errors.append(
                                    f"Failed to download attachment {attachment['filename']}"
                                )
                                continue

                            # Decode base64 attachment data
                            attachment_data = attachment_result["attachment"].get(
                                "data", ""
                            )
                            file_content = base64.urlsafe_b64decode(attachment_data)

                            # Upload to Google Drive
                            upload_result = await GDriveHelpers.upload_file(
                                access_token=self.gdrive_creds.get("access_token"),
                                refresh_token=self.gdrive_creds.get("refresh_token"),
                                file_name=attachment["filename"],
                                file_content=file_content,
                                mime_type=attachment["mimeType"],
                                folder_id=folder_id,
                            )

                            if upload_result.get("success"):
                                logger.info(
                                    f"Successfully uploaded: {attachment['filename']}"
                                )
                                saved_files.append(
                                    {
                                        "filename": attachment["filename"],
                                        "size": attachment["size"],
                                        "drive_file_id": upload_result["file"]["id"],
                                        "web_view_link": upload_result["file"].get(
                                            "webViewLink"
                                        ),
                                    }
                                )
                            else:
                                errors.append(
                                    f"Failed to upload {attachment['filename']}: {upload_result.get('error')}"
                                )

                        except Exception as e:
                            logger.error(
                                f"Error processing attachment {attachment.get('filename')}: {str(e)}"
                            )
                            errors.append(
                                f"Error with {attachment.get('filename')}: {str(e)}"
                            )

                except Exception as e:
                    logger.error(f"Error processing email {msg.get('id')}: {str(e)}")
                    errors.append(str(e))

            return {
                "success": True,
                "files_saved": len(saved_files),
                "files": saved_files,
                "errors": errors,
                "folder_id": folder_id,
                "message": f"Saved {len(saved_files)} attachments from {len(messages)} emails to Google Drive",
            }

        except Exception as e:
            logger.error(f"Error in save_attachments_to_drive: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _extract_attachments(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract real (non-inline) attachments from Gmail email data.

        Args:
            email_data: Dict containing Gmail message data

        Returns:
            List of attachment metadata dictionaries containing:
                - filename: Name of the attachment
                - mimeType: MIME type of the attachment
                - size: Size in bytes
                - attachmentId: Gmail attachment ID
        """
        attachments = []

        def walk_parts(parts: List[Dict[str, Any]]) -> None:
            """
            Recursively walk through email parts to find attachments.

            Args:
                parts: List of email message parts to process
            """
            for part in parts:
                filename = part.get("filename")
                mime_type = part.get("mimeType")
                body = part.get("body", {})
                headers = {h["name"]: h["value"] for h in part.get("headers", [])}

                # Skip inline attachments (images, signatures)
                if headers.get("Content-Disposition", "").startswith("inline"):
                    if "parts" in part:
                        walk_parts(part["parts"])
                    continue

                # If this part is an attachment
                if filename and "attachmentId" in body:
                    attachments.append(
                        {
                            "filename": filename,
                            "mimeType": mime_type,
                            "size": body.get("size", 0),
                            "attachmentId": body["attachmentId"],
                        }
                    )

                # If there are nested parts, recurse
                if "parts" in part:
                    walk_parts(part["parts"])

        try:
            payload = email_data.get("payload", {})
            if "parts" in payload:
                walk_parts(payload["parts"])
            return attachments

        except Exception as e:
            logger.error(f"Error extracting attachments: {e}")
            return []
