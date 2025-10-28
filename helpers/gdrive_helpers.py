"""
Google Drive helper functions using Google API Python Client.
Provides CRUD operations for Google Drive files and folders.
"""

import os
from typing import Dict, List, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io
import logging

logger = logging.getLogger(__name__)


class GDriveHelpers:
    """Helper class for Google Drive operations."""

    @staticmethod
    def _get_service(
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: str = "https://oauth2.googleapis.com/token",
    ):
        """Create Drive API service with access token."""
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
        )
        return build("drive", "v3", credentials=credentials)

    @staticmethod
    async def list_files(
        access_token: str,
        refresh_token: str,
        query: Optional[str] = None,
        page_size: int = 10,
        order_by: str = "modifiedTime desc",
    ) -> Dict[str, Any]:
        """
        List Google Drive files.

        Args:
            access_token: User's Google Drive access token
            query: Search query (e.g., "name contains 'report'")
            page_size: Maximum number of files to return
            order_by: Sort order

        Returns:
            Dict with files list
        """
        try:
            service = GDriveHelpers._get_service(access_token, refresh_token)

            params = {
                "pageSize": page_size,
                "orderBy": order_by,
                "fields": "files(id, name, mimeType, size, createdTime, modifiedTime)",
            }

            if query:
                params["q"] = query

            results = service.files().list(**params).execute()
            files = results.get("files", [])

            return {"success": True, "files": files, "count": len(files)}

        except HttpError as error:
            logger.error(f"Drive API error listing files: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def upload_file(
        access_token: str,
        refresh_token: str,
        file_name: str,
        file_content: bytes,
        mime_type: str,
        folder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Drive.

        Args:
            access_token: User's Google Drive access token
            file_name: Name of the file
            file_content: File content as bytes
            mime_type: MIME type of the file
            folder_id: Parent folder ID (optional)

        Returns:
            Dict with uploaded file data
        """
        try:
            service = GDriveHelpers._get_service(access_token, refresh_token)

            file_metadata = {"name": file_name}
            if folder_id:
                file_metadata["parents"] = [folder_id]

            media = MediaIoBaseUpload(
                io.BytesIO(file_content), mimetype=mime_type, resumable=True
            )

            file = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name, mimeType, size, webViewLink",
                )
                .execute()
            )

            return {"success": True, "file": file}

        except HttpError as error:
            logger.error(f"Drive API error uploading file: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def create_folder(
        access_token: str,
        refresh_token: str,
        folder_name: str,
        parent_folder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a folder in Google Drive.

        Args:
            access_token: User's Google Drive access token
            folder_name: Name of the folder
            parent_folder_id: Parent folder ID (optional)

        Returns:
            Dict with created folder data
        """
        try:
            service = GDriveHelpers._get_service(access_token, refresh_token)

            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }

            if parent_folder_id:
                file_metadata["parents"] = [parent_folder_id]

            folder = (
                service.files()
                .create(body=file_metadata, fields="id, name, mimeType")
                .execute()
            )

            return {"success": True, "folder": folder}

        except HttpError as error:
            logger.error(f"Drive API error creating folder: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def find_folder(
        access_token: str, refresh_token: str, folder_name: str
    ) -> Dict[str, Any]:
        """
        Find a folder by name in Google Drive.

        Args:
            access_token: User's Google Drive access token
            folder_name: Name of the folder to find

        Returns:
            Dict with folder data or None if not found
        """
        try:
            service = GDriveHelpers._get_service(access_token, refresh_token)

            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                service.files()
                .list(q=query, fields="files(id, name)", pageSize=1)
                .execute()
            )

            files = results.get("files", [])

            if files:
                return {"success": True, "folder": files[0]}
            else:
                return {"success": True, "folder": None}

        except HttpError as error:
            logger.error(f"Drive API error finding folder: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def delete_file(access_token: str, file_id: str) -> Dict[str, Any]:
        """
        Delete a file from Google Drive.

        Args:
            access_token: User's Google Drive access token
            file_id: ID of the file to delete

        Returns:
            Dict with success status
        """
        try:
            service = GDriveHelpers._get_service(access_token)

            service.files().delete(fileId=file_id).execute()

            return {"success": True, "file_id": file_id}

        except HttpError as error:
            logger.error(f"Drive API error deleting file: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def download_file(
        access_token: str, refresh_token: str, file_id: str
    ) -> Dict[str, Any]:
        """
        Download a file from Google Drive.

        Args:
            access_token: User's Google Drive access token
            file_id: ID of the file to download

        Returns:
            Dict with file content
        """
        try:
            service = GDriveHelpers._get_service(access_token, refresh_token)

            request = service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()

            downloader = MediaIoBaseDownload(file_content, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            return {"success": True, "content": file_content.getvalue()}

        except HttpError as error:
            logger.error(f"Drive API error downloading file: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_recent_changes(
        access_token: str, days: int = 7, max_results: int = 20
    ) -> Dict[str, Any]:
        """
        Get recently modified files in Google Drive.

        Args:
            access_token: User's Google Drive access token
            days: Number of days to look back (default: 7)
            max_results: Maximum number of files to return

        Returns:
            Dict with recently modified files
        """
        try:
            from datetime import datetime, timedelta

            # Calculate date threshold
            date_threshold = datetime.utcnow() - timedelta(days=days)
            date_str = date_threshold.isoformat() + "Z"

            # Query for recently modified files
            query = f"modifiedTime > '{date_str}' and trashed=false"

            result = await GDriveHelpers.list_files(
                access_token=access_token,
                query=query,
                page_size=max_results,
                order_by="modifiedTime desc",
            )

            if result.get("success"):
                files = result.get("files", [])
                return {
                    "success": True,
                    "recent_changes": files,
                    "count": len(files),
                    "days_back": days,
                }

            return result

        except Exception as error:
            logger.error(f"Error getting recent changes: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_shared_with_me(
        access_token: str, max_results: int = 20
    ) -> Dict[str, Any]:
        """
        Get files shared with the user.

        Args:
            access_token: User's Google Drive access token
            max_results: Maximum number of files to return

        Returns:
            Dict with shared files
        """
        try:
            query = "sharedWithMe=true and trashed=false"

            result = await GDriveHelpers.list_files(
                access_token=access_token,
                query=query,
                page_size=max_results,
                order_by="sharedWithMeTime desc",
            )

            if result.get("success"):
                files = result.get("files", [])
                return {"success": True, "shared_files": files, "count": len(files)}

            return result

        except Exception as error:
            logger.error(f"Error getting shared files: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def search_files_by_type(
        access_token: str, file_type: str, max_results: int = 20
    ) -> Dict[str, Any]:
        """
        Search files by type (documents, spreadsheets, presentations, etc.).

        Args:
            access_token: User's Google Drive access token
            file_type: Type of file ('document', 'spreadsheet', 'presentation', 'pdf', 'image')
            max_results: Maximum number of files to return

        Returns:
            Dict with files of specified type
        """
        try:
            # Map file types to MIME types
            mime_type_map = {
                "document": "application/vnd.google-apps.document",
                "spreadsheet": "application/vnd.google-apps.spreadsheet",
                "presentation": "application/vnd.google-apps.presentation",
                "pdf": "application/pdf",
                "image": "image/",
                "folder": "application/vnd.google-apps.folder",
            }

            mime_type = mime_type_map.get(file_type.lower())
            if not mime_type:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_type}",
                }

            # Build query
            if file_type.lower() == "image":
                query = f"mimeType contains '{mime_type}' and trashed=false"
            else:
                query = f"mimeType='{mime_type}' and trashed=false"

            result = await GDriveHelpers.list_files(
                access_token=access_token,
                query=query,
                page_size=max_results,
                order_by="modifiedTime desc",
            )

            if result.get("success"):
                files = result.get("files", [])
                return {
                    "success": True,
                    "files": files,
                    "file_type": file_type,
                    "count": len(files),
                }

            return result

        except Exception as error:
            logger.error(f"Error searching files by type: {error}")
            return {"success": False, "error": str(error)}


# Function registry for Gemini
GDRIVE_FUNCTIONS = {
    "list_files": {
        "name": "list_files",
        "description": "List Google Drive files with optional filters",
        "parameters": {
            "query": "Search query (e.g., \"name contains 'report'\", optional)",
            "page_size": "Maximum number of files to return (default: 10)",
            "order_by": "Sort order (default: 'modifiedTime desc')",
        },
    },
    "upload_file": {
        "name": "upload_file",
        "description": "Upload a file to Google Drive",
        "parameters": {
            "file_name": "Name of the file",
            "file_content": "File content as bytes",
            "mime_type": "MIME type of the file",
            "folder_id": "Parent folder ID (optional)",
        },
    },
    "create_folder": {
        "name": "create_folder",
        "description": "Create a folder in Google Drive",
        "parameters": {
            "folder_name": "Name of the folder",
            "parent_folder_id": "Parent folder ID (optional)",
        },
    },
    "delete_file": {
        "name": "delete_file",
        "description": "Delete a file from Google Drive",
        "parameters": {"file_id": "ID of the file to delete"},
    },
    "download_file": {
        "name": "download_file",
        "description": "Download a file from Google Drive",
        "parameters": {"file_id": "ID of the file to download"},
    },
    "find_folder": {
        "name": "find_folder",
        "description": "Find a folder by name in Google Drive",
        "parameters": {"folder_name": "Name of the folder to find"},
    },
    "get_recent_changes": {
        "name": "get_recent_changes",
        "description": "Get recently modified files in Google Drive",
        "parameters": {
            "days": "Number of days to look back (default: 7)",
            "max_results": "Maximum number of files to return (default: 20)",
        },
    },
    "get_shared_with_me": {
        "name": "get_shared_with_me",
        "description": "Get files shared with the user",
        "parameters": {
            "max_results": "Maximum number of files to return (default: 20)"
        },
    },
    "search_files_by_type": {
        "name": "search_files_by_type",
        "description": "Search files by type (document, spreadsheet, presentation, pdf, image, folder)",
        "parameters": {
            "file_type": "Type of file to search for",
            "max_results": "Maximum number of files to return (default: 20)",
        },
    },
}
