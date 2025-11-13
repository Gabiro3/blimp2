"""
Google Docs helper functions using Google API Python Client.
Provides CRUD operations for Google Docs documents, content manipulation, etc.

IMPORTANT: This module uses the 'drive.file' OAuth scope (https://www.googleapis.com/auth/drive.file)
instead of the restricted 'drive' and 'documents' scopes. This means the app can only access:
1. Documents created by the app
2. Documents explicitly opened/selected by the user via Google Picker

This is a non-restricted scope that doesn't require security assessment.
Google Docs are stored in Drive, so drive.file scope provides both Docs API and Drive API access.
"""

from typing import Dict, List, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class GoogleDocsHelpers:
    """
    Helper class for Google Docs operations using drive.file scope.

    Scope: https://www.googleapis.com/auth/drive.file
    - Can create new documents
    - Can only access documents created by this app or explicitly selected by user
    - No verification required (non-restricted scope)
    - Works for both Docs API and Drive API operations on documents
    """

    @staticmethod
    def _get_service(credentials_dict: Dict[str, Any]):
        """Create Google Docs API service with credentials."""
        credentials = Credentials(
            token=credentials_dict.get("access_token"),
            refresh_token=credentials_dict.get("refresh_token"),
            token_uri=credentials_dict.get("token_uri"),
            client_id=credentials_dict.get("client_id"),
            client_secret=credentials_dict.get("client_secret"),
        )
        return build("docs", "v1", credentials=credentials)

    @staticmethod
    def _get_drive_service(credentials_dict: Dict[str, Any]):
        """Create Google Drive API service with credentials."""
        credentials = Credentials(
            token=credentials_dict.get("access_token"),
            refresh_token=credentials_dict.get("refresh_token"),
            token_uri=credentials_dict.get("token_uri"),
            client_id=credentials_dict.get("client_id"),
            client_secret=credentials_dict.get("client_secret"),
        )
        return build("drive", "v3", credentials=credentials)

    @staticmethod
    def _parse_markdown_to_requests(
        content: str, start_index: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Parse markdown content and convert to Google Docs API requests.

        Converts markdown formatting (headers, bold) to proper Google Docs formatting.

        Args:
            content: Markdown formatted content
            start_index: Starting index in the document

        Returns:
            List of Google Docs API requests
        """
        requests = []
        current_index = start_index

        # Split content into lines for processing
        lines = content.split("\n")

        for line in lines:
            if not line.strip():
                # Empty line - just add newline
                requests.append(
                    {"insertText": {"text": "\n", "location": {"index": current_index}}}
                )
                current_index += 1
                continue

            # Check for headers (##, ###, etc.)
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                level = len(header_match.group(1))
                text = header_match.group(2).strip()

                # Remove any remaining markdown formatting from header text
                text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # Remove bold
                text = re.sub(r"\*(.+?)\*", r"\1", text)  # Remove italic

                # Insert header text
                requests.append(
                    {
                        "insertText": {
                            "text": text + "\n",
                            "location": {"index": current_index},
                        }
                    }
                )

                # Apply heading style
                heading_style = f"HEADING_{level}" if level <= 6 else "HEADING_6"
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": current_index,
                                "endIndex": current_index + len(text),
                            },
                            "paragraphStyle": {"namedStyleType": heading_style},
                            "fields": "namedStyleType",
                        }
                    }
                )

                current_index += len(text) + 1
                continue

            # Process inline formatting (bold, italic)
            processed_line = line
            formatting_ranges = []

            # Find bold text (**text**)
            for match in re.finditer(r"\*\*(.+?)\*\*", line):
                start = match.start()
                end = match.end()
                text = match.group(1)
                # Adjust for already removed asterisks
                actual_start = start - (len(formatting_ranges) * 4)
                formatting_ranges.append(
                    {
                        "type": "bold",
                        "start": actual_start,
                        "end": actual_start + len(text),
                    }
                )

            # Remove markdown syntax
            processed_line = re.sub(r"\*\*(.+?)\*\*", r"\1", processed_line)  # Bold
            processed_line = re.sub(r"\*(.+?)\*", r"\1", processed_line)  # Italic

            # Insert the text
            requests.append(
                {
                    "insertText": {
                        "text": processed_line + "\n",
                        "location": {"index": current_index},
                    }
                }
            )

            # Apply formatting
            for fmt in formatting_ranges:
                if fmt["type"] == "bold":
                    requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": current_index + fmt["start"],
                                    "endIndex": current_index + fmt["end"],
                                },
                                "textStyle": {"bold": True},
                                "fields": "bold",
                            }
                        }
                    )

            current_index += len(processed_line) + 1

        return requests

    @staticmethod
    async def search_documents(
        access_token: str,
        query: str = "",
        max_results: int = 10,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search for Google Docs documents accessible to this app.

        With drive.file scope, only returns documents that were:
        - Created by this app, OR
        - Explicitly selected by user via Google Picker

        Args:
            access_token: User's access token (deprecated)
            query: Search query
            max_results: Maximum number of results
            credentials: Full OAuth credentials

        Returns:
            Dict with search results
        """
        try:
            if credentials:
                service = GoogleDocsHelpers._get_drive_service(credentials)
            else:
                service = GoogleDocsHelpers._get_drive_service(
                    {"access_token": access_token}
                )

            # Search for Google Docs files
            query_str = (
                f"mimeType='application/vnd.google-apps.document' and {query}"
                if query
                else "mimeType='application/vnd.google-apps.document'"
            )

            results = (
                service.files()
                .list(
                    q=query_str,
                    pageSize=max_results,
                    fields="files(id, name, modifiedTime, createdTime, webViewLink, owners)",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )

            files = results.get("files", [])

            return {"success": True, "documents": files, "count": len(files)}

        except HttpError as error:
            logger.error(f"Google Docs API error searching documents: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def create_document(
        access_token: str,
        title: str,
        content: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new Google Docs document.

        Documents created via this method are automatically accessible with drive.file scope.

        Args:
            access_token: User's access token (deprecated)
            title: Document title
            content: Initial document content (supports markdown - ##, ###, **)
            credentials: Full OAuth credentials

        Returns:
            Dict with document details
        """
        try:
            if credentials:
                service = GoogleDocsHelpers._get_service(credentials)
            else:
                service = GoogleDocsHelpers._get_service({"access_token": access_token})

            doc = service.documents().create(body={"title": title}).execute()

            doc_id = doc["documentId"]

            # Add initial content if provided
            if content:
                # Parse markdown and create formatting requests
                requests = GoogleDocsHelpers._parse_markdown_to_requests(
                    content, start_index=1
                )

                if requests:
                    service.documents().batchUpdate(
                        documentId=doc_id, body={"requests": requests}
                    ).execute()

            return {
                "success": True,
                "document": doc,
                "document_id": doc_id,
                "web_link": f"https://docs.google.com/document/d/{doc_id}/edit",
            }

        except HttpError as error:
            logger.error(f"Google Docs API error creating document: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def append_to_document(
        access_token: str,
        document_id: str,
        content: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Append content to a Google Docs document.

        Can only append to documents created by this app or explicitly granted access to.

        Args:
            access_token: User's access token (deprecated)
            document_id: ID of the document
            content: Content to append (supports markdown - ##, ###, **)
            credentials: Full OAuth credentials

        Returns:
            Dict with operation status
        """
        try:
            if credentials:
                service = GoogleDocsHelpers._get_service(credentials)
            else:
                service = GoogleDocsHelpers._get_service({"access_token": access_token})

            # Get document to find the end position
            doc = service.documents().get(documentId=document_id).execute()

            # Calculate the actual end index
            end_index = 1
            for element in doc.get("body", {}).get("content", []):
                if "endIndex" in element:
                    end_index = max(end_index, element["endIndex"])

            # Parse markdown and create formatting requests
            # Add a separator before new content
            separator = "\n\n"
            requests = GoogleDocsHelpers._parse_markdown_to_requests(
                separator + content, start_index=end_index - 1
            )

            if requests:
                result = (
                    service.documents()
                    .batchUpdate(documentId=document_id, body={"requests": requests})
                    .execute()
                )

                return {"success": True, "replies": result.get("replies", [])}

            return {"success": True, "message": "No content to append"}

        except HttpError as error:
            logger.error(f"Google Docs API error appending to document: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_document_content(
        access_token: str,
        document_id: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get full content of a Google Docs document.

        Can only access documents created by this app or explicitly granted access to.

        Args:
            access_token: User's access token (deprecated)
            document_id: ID of the document
            credentials: Full OAuth credentials

        Returns:
            Dict with document content
        """
        try:
            if credentials:
                service = GoogleDocsHelpers._get_service(credentials)
            else:
                service = GoogleDocsHelpers._get_service({"access_token": access_token})

            doc = service.documents().get(documentId=document_id).execute()

            # Extract text content
            text_content = ""
            for element in doc.get("body", {}).get("content", []):
                if "paragraph" in element:
                    for run in element["paragraph"].get("elements", []):
                        if "textRun" in run:
                            text_content += run["textRun"].get("content", "")

            return {
                "success": True,
                "document_id": document_id,
                "title": doc.get("title", ""),
                "content": text_content,
                "revision_id": doc.get("revisionId", ""),
            }

        except HttpError as error:
            logger.error(f"Google Docs API error getting document: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def share_document(
        access_token: str,
        document_id: str,
        email: str,
        role: str = "reader",
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Share a Google Docs document with someone.

        Can only share documents created by this app or explicitly granted access to.

        Args:
            access_token: User's access token (deprecated)
            document_id: ID of the document
            email: Email to share with
            role: Permission role (reader, commenter, writer)
            credentials: Full OAuth credentials

        Returns:
            Dict with sharing status
        """
        try:
            if credentials:
                service = GoogleDocsHelpers._get_drive_service(credentials)
            else:
                service = GoogleDocsHelpers._get_drive_service(
                    {"access_token": access_token}
                )

            permission = (
                service.permissions()
                .create(
                    fileId=document_id,
                    body={"type": "user", "role": role, "emailAddress": email},
                    fields="id",
                )
                .execute()
            )

            return {
                "success": True,
                "permission_id": permission.get("id"),
                "message": f"Document shared with {email}",
            }

        except HttpError as error:
            logger.error(f"Google Docs API error sharing document: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_document_comments(
        access_token: str,
        document_id: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get comments from a Google Docs document.

        Can only access comments from documents created by this app
        or explicitly granted access to.

        Args:
            access_token: User's access token (deprecated)
            document_id: ID of the document
            credentials: Full OAuth credentials

        Returns:
            Dict with comments
        """
        try:
            if credentials:
                service = GoogleDocsHelpers._get_service(credentials)
            else:
                service = GoogleDocsHelpers._get_service({"access_token": access_token})

            comments = service.documents().getComments(documentId=document_id).execute()

            comment_list = []
            for comment_id, comment_data in comments.get("comments", {}).items():
                comment_list.append(
                    {
                        "id": comment_id,
                        "author": comment_data.get("author", {}).get(
                            "displayName", "Unknown"
                        ),
                        "content": comment_data.get("content", ""),
                        "created": comment_data.get("createTime", ""),
                        "resolved": comment_data.get("resolved", False),
                    }
                )

            return {
                "success": True,
                "comments": comment_list,
                "count": len(comment_list),
            }

        except HttpError as error:
            logger.error(f"Google Docs API error getting comments: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_recent_documents(
        access_token: str,
        max_results: int = 10,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get user's recently modified documents accessible to this app.

        With drive.file scope, only returns documents created by app
        or explicitly selected by user.

        Args:
            access_token: User's access token (deprecated)
            max_results: Maximum number of results
            credentials: Full OAuth credentials

        Returns:
            Dict with recent documents
        """
        try:
            if credentials:
                service = GoogleDocsHelpers._get_drive_service(credentials)
            else:
                service = GoogleDocsHelpers._get_drive_service(
                    {"access_token": access_token}
                )

            results = (
                service.files()
                .list(
                    q="mimeType='application/vnd.google-apps.document'",
                    pageSize=max_results,
                    fields="files(id, name, modifiedTime, createdTime, webViewLink, owners, sharedWithMe)",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )

            files = results.get("files", [])

            return {"success": True, "documents": files, "count": len(files)}

        except HttpError as error:
            logger.error(f"Google Docs API error getting recent documents: {error}")
            return {"success": False, "error": str(error)}


# Function registry for Gemini
GOOGLE_DOCS_FUNCTIONS = {
    "search_documents": {
        "name": "search_documents",
        "description": "Search for Google Docs documents accessible to this app (created by app or selected by user)",
        "parameters": {
            "query": "Search query for document names",
            "max_results": "Maximum number of results (default: 10)",
        },
    },
    "create_document": {
        "name": "create_document",
        "description": "Create a new Google Docs document (will be accessible to app)",
        "parameters": {
            "title": "Document title",
            "content": "Initial document content with markdown support (optional)",
        },
    },
    "append_to_document": {
        "name": "append_to_document",
        "description": "Append content to an existing document (only documents accessible to app)",
        "parameters": {
            "document_id": "ID of the document",
            "content": "Content to append with markdown support",
        },
    },
    "get_document_content": {
        "name": "get_document_content",
        "description": "Get the full content of a Google Docs document (only documents accessible to app)",
        "parameters": {"document_id": "ID of the document"},
    },
    "share_document": {
        "name": "share_document",
        "description": "Share a Google Docs document with someone (only documents accessible to app)",
        "parameters": {
            "document_id": "ID of the document",
            "email": "Email address to share with",
            "role": "Permission role (reader, commenter, writer)",
        },
    },
    "get_document_comments": {
        "name": "get_document_comments",
        "description": "Get all comments from a Google Docs document (only documents accessible to app)",
        "parameters": {"document_id": "ID of the document"},
    },
    "get_recent_documents": {
        "name": "get_recent_documents",
        "description": "Get user's recently modified Google Docs documents accessible to this app",
        "parameters": {"max_results": "Maximum number of results (default: 10)"},
    },
}
