"""
Google Drive helper functions using Google API Python Client.
Provides CRUD operations for Google Drive files and folders.

IMPORTANT: This module uses the 'drive.file' OAuth scope (https://www.googleapis.com/auth/drive.file)
instead of the restricted 'drive' scope. This means the app can only access:
1. Files created by the app
2. Files explicitly opened/selected by the user via Google Picker

This is a non-restricted scope that doesn't require security assessment.
"""

from typing import Dict, List, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io
import logging

logger = logging.getLogger(__name__)


class GDriveHelpers:
    """
    Helper class for Google Drive operations using drive.file scope.

    Scope: https://www.googleapis.com/auth/drive.file
    - Can create new files
    - Can only access files created by this app or explicitly selected by user
    - No verification required (non-restricted scope)
    """

    @staticmethod
    def _get_service(access_token: str):
        """Create Drive API service with access token."""
        credentials = Credentials(token=access_token)
        return build("drive", "v3", credentials=credentials)

    @staticmethod
    async def list_files(
        access_token: str,
        query: Optional[str] = None,
        page_size: int = 10,
        order_by: str = "modifiedTime desc",
    ) -> Dict[str, Any]:
        """
        List Google Drive files accessible to this app.

        With drive.file scope, this only returns:
        - Files created by this app
        - Files the user has explicitly granted access to via Picker

        Args:
            access_token: User's Google Drive access token
            query: Search query (e.g., "name contains 'report'")
            page_size: Maximum number of files to return
            order_by: Sort order

        Returns:
            Dict with files list
        """
        try:
            service = GDriveHelpers._get_service(access_token)

            params = {
                "pageSize": page_size,
                "orderBy": order_by,
                "fields": "files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink)",
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
        file_name: str,
        file_content: bytes,
        mime_type: str,
        folder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Drive.

        Files created via this method are automatically accessible with drive.file scope.

        Args:
            access_token: User's Google Drive access token
            file_name: Name of the file
            file_content: File content as bytes
            mime_type: MIME type of the file
            folder_id: Parent folder ID (optional, must be accessible to app)

        Returns:
            Dict with uploaded file data
        """
        try:
            service = GDriveHelpers._get_service(access_token)

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
        access_token: str, folder_name: str, parent_folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a folder in Google Drive.

        Folders created via this method are automatically accessible with drive.file scope.

        Args:
            access_token: User's Google Drive access token
            folder_name: Name of the folder
            parent_folder_id: Parent folder ID (optional, must be accessible to app)

        Returns:
            Dict with created folder data
        """
        try:
            service = GDriveHelpers._get_service(access_token)

            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }

            if parent_folder_id:
                file_metadata["parents"] = [parent_folder_id]

            folder = (
                service.files()
                .create(body=file_metadata, fields="id, name, mimeType, webViewLink")
                .execute()
            )

            return {"success": True, "folder": folder}

        except HttpError as error:
            logger.error(f"Drive API error creating folder: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def find_folder(access_token: str, folder_name: str) -> Dict[str, Any]:
        """
        Find a folder by name in Google Drive.

        With drive.file scope, this only finds folders created by this app
        or explicitly granted access to.

        Args:
            access_token: User's Google Drive access token
            folder_name: Name of the folder to find

        Returns:
            Dict with folder data or None if not found
        """
        try:
            service = GDriveHelpers._get_service(access_token)

            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                service.files()
                .list(q=query, fields="files(id, name, webViewLink)", pageSize=1)
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

        Can only delete files created by this app or explicitly granted access to.

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
    async def download_file(access_token: str, file_id: str) -> Dict[str, Any]:
        """
        Download a file from Google Drive.

        Can only download files created by this app or explicitly granted access to.

        Args:
            access_token: User's Google Drive access token
            file_id: ID of the file to download

        Returns:
            Dict with file content
        """
        try:
            service = GDriveHelpers._get_service(access_token)

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
    async def share_file(
        access_token: str, file_id: str, email: str, role: str = "reader"
    ) -> Dict[str, Any]:
        """
        Share a file with another user.

        Can only share files created by this app or explicitly granted access to.

        Args:
            access_token: User's Google Drive access token
            file_id: ID of the file to share
            email: Email address to share with
            role: Permission role (reader, commenter, writer)

        Returns:
            Dict with sharing status
        """
        try:
            service = GDriveHelpers._get_service(access_token)

            permission = (
                service.permissions()
                .create(
                    fileId=file_id,
                    body={"type": "user", "role": role, "emailAddress": email},
                    fields="id",
                )
                .execute()
            )

            return {
                "success": True,
                "permission_id": permission.get("id"),
                "message": f"File shared with {email} as {role}",
            }

        except HttpError as error:
            logger.error(f"Drive API error sharing file: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_recent_changes(
        access_token: str, days: int = 7, max_results: int = 20
    ) -> Dict[str, Any]:
        """
        Get recently modified files accessible to this app.

        With drive.file scope, only returns files created by app
        or explicitly granted access to.

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
        Get files shared with the user that are accessible to this app.

        NOTE: With drive.file scope, this will only return files that:
        - Were created by this app, OR
        - Were explicitly selected by user via Google Picker

        Use Google Picker on frontend to let users grant access to specific files.

        Args:
            access_token: User's Google Drive access token
            max_results: Maximum number of files to return

        Returns:
            Dict with shared files accessible to app
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
        Search files by type that are accessible to this app.

        With drive.file scope, only searches files created by app
        or explicitly granted access to.

        Args:
            access_token: User's Google Drive access token
            file_type: Type of file ('document', 'spreadsheet', 'presentation', 'pdf', 'image', 'folder')
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

    @staticmethod
    async def get_file_metadata(access_token: str, file_id: str) -> Dict[str, Any]:
        """
        Get metadata for a specific file.

        Can only access files created by this app or explicitly granted access to.

        Args:
            access_token: User's Google Drive access token
            file_id: ID of the file

        Returns:
            Dict with file metadata
        """
        try:
            service = GDriveHelpers._get_service(access_token)

            file = (
                service.files()
                .get(
                    fileId=file_id,
                    fields="id, name, mimeType, size, createdTime, modifiedTime, webViewLink, owners, shared",
                )
                .execute()
            )

            return {"success": True, "file": file}

        except HttpError as error:
            logger.error(f"Drive API error getting file metadata: {error}")
            return {"success": False, "error": str(error)}


# Function registry for Gemini
GDRIVE_FUNCTIONS = {
    "list_files": {
        "name": "list_files",
        "description": "List Google Drive files accessible to this app (files created by app or selected by user)",
        "parameters": {
            "query": "Search query (e.g., \"name contains 'report'\", optional)",
            "page_size": "Maximum number of files to return (default: 10)",
            "order_by": "Sort order (default: 'modifiedTime desc')",
        },
    },
    "upload_file": {
        "name": "upload_file",
        "description": "Upload a file to Google Drive (will be accessible to app)",
        "parameters": {
            "file_name": "Name of the file",
            "file_content": "File content as bytes",
            "mime_type": "MIME type of the file",
            "folder_id": "Parent folder ID (optional, must be accessible to app)",
        },
    },
    "create_folder": {
        "name": "create_folder",
        "description": "Create a folder in Google Drive (will be accessible to app)",
        "parameters": {
            "folder_name": "Name of the folder",
            "parent_folder_id": "Parent folder ID (optional, must be accessible to app)",
        },
    },
    "delete_file": {
        "name": "delete_file",
        "description": "Delete a file from Google Drive (only files accessible to app)",
        "parameters": {"file_id": "ID of the file to delete"},
    },
    "download_file": {
        "name": "download_file",
        "description": "Download a file from Google Drive (only files accessible to app)",
        "parameters": {"file_id": "ID of the file to download"},
    },
    "find_folder": {
        "name": "find_folder",
        "description": "Find a folder by name (only folders accessible to app)",
        "parameters": {"folder_name": "Name of the folder to find"},
    },
    "share_file": {
        "name": "share_file",
        "description": "Share a file with another user via email (only files accessible to app)",
        "parameters": {
            "file_id": "ID of the file to share",
            "email": "Email address to share with",
            "role": "Permission role (reader, commenter, writer)",
        },
    },
    "get_recent_changes": {
        "name": "get_recent_changes",
        "description": "Get recently modified files accessible to this app",
        "parameters": {
            "days": "Number of days to look back (default: 7)",
            "max_results": "Maximum number of files to return (default: 20)",
        },
    },
    "get_shared_with_me": {
        "name": "get_shared_with_me",
        "description": "Get files shared with user that are accessible to this app",
        "parameters": {
            "max_results": "Maximum number of files to return (default: 20)"
        },
    },
    "search_files_by_type": {
        "name": "search_files_by_type",
        "description": "Search files by type (document, spreadsheet, presentation, pdf, image, folder) accessible to app",
        "parameters": {
            "file_type": "Type of file to search for",
            "max_results": "Maximum number of files to return (default: 20)",
        },
    },
    "get_file_metadata": {
        "name": "get_file_metadata",
        "description": "Get detailed metadata for a specific file (only files accessible to app)",
        "parameters": {"file_id": "ID of the file"},
    },
}
