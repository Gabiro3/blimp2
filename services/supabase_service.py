"""
Supabase Service - Database operations
Handles all interactions with Supabase database
"""

import os
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)


class SupabaseService:
    """Service for interacting with Supabase database"""

    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.timeout = httpx.Timeout(30.0)

        if not self.url or not self.key:
            logger.warning("Supabase credentials not found in environment variables")
            self.client = None
        else:
            self.client: Client = create_client(self.url, self.key)
            logger.info("Supabase service initialized")

    async def get_user_connected_apps(self, user_id: str) -> List[str]:
        """Get list of apps that user has connected"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return []

            response = (
                self.client.table("user_credentials")
                .select("app_name")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .execute()
            )

            if response.data:
                connected_apps = [row["app_name"] for row in response.data]
                logger.info(f"Connected apps for user {user_id}: {connected_apps}")
                logger.info(
                    f"Found {len(connected_apps)} connected apps for user {user_id}"
                )
                return connected_apps

            return []

        except Exception as e:
            logger.error(f"Error fetching connected apps: {str(e)}")
            return []

    async def get_all_workflow_templates(self) -> List[Dict[str, Any]]:
        """Get all active workflow templates from the database"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return []

            response = (
                self.client.table("workflow_templates")
                .select("id, name, description, required_apps, category")
                .eq("is_active", True)
                .execute()
            )

            if response.data:
                logger.info(f"Retrieved {len(response.data)} workflow templates")
                return response.data

            return []

        except Exception as e:
            logger.error(f"Error fetching workflow templates: {str(e)}")
            return []

    async def get_workflow(
        self, workflow_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific workflow by ID"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None

            # Try workflow_templates first
            response = (
                self.client.table("workflow_templates")
                .select("*")
                .eq("id", workflow_id)
                .eq("is_active", True)
                .single()
                .execute()
            )

            if response.data:
                return response.data

            # Try user_workflows
            response = (
                self.client.table("user_workflows")
                .select("*")
                .eq("id", workflow_id)
                .eq("user_id", user_id)
                .eq("is_active", True)
                .single()
                .execute()
            )

            if response.data:
                return response.data

            return None

        except Exception as e:
            logger.error(f"Error fetching workflow: {str(e)}")
            return None

    async def save_user_workflow(
        self,
        user_id: str,
        workflow_id: str,
        name: str,
        description: str,
        prompt: str,
        required_apps: List[str],
        category: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> bool:
        """Save a user-specific workflow"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False

            data = {
                "id": workflow_id,
                "user_id": user_id,
                "name": name,
                "description": description,
                "prompt": prompt,
                "required_apps": required_apps,
                "category": category or "custom",
                "webhook_url": webhook_url,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            response = self.client.table("user_workflows").insert(data).execute()

            return bool(response.data)

        except Exception as e:
            logger.error(f"Error saving user workflow: {str(e)}")
            return False

    async def save_workflow_execution(
        self,
        user_id: str,
        workflow_id: str,
        execution_id: str,
        status: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Save workflow execution record"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False

            data = {
                "user_id": user_id,
                "workflow_id": workflow_id,
                "execution_id": execution_id,
                "status": status,
                "parameters": parameters or {},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            response = self.client.table("workflow_executions").insert(data).execute()

            return bool(response.data)

        except Exception as e:
            logger.error(f"Error saving workflow execution: {str(e)}")
            return False

    async def update_workflow_status(
        self, execution_id: str, status: str, result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update workflow execution status"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False

            update_data = {
                "status": status,
                "completed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            if result:
                update_data["result"] = result

            response = (
                self.client.table("workflow_executions")
                .update(update_data)
                .eq("execution_id", execution_id)
                .execute()
            )

            return bool(response.data)

        except Exception as e:
            logger.error(f"Error updating workflow status: {str(e)}")
            return False

    async def get_user_workflow_credentials(
        self, user_id: str, workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get user's credentials for workflow apps"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None

            response = (
                self.client.table("user_credentials")
                .select("app_type, credentials, metadata")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .execute()
            )

            if not response.data:
                return None

            credentials_map = {}
            for row in response.data:
                credentials_map[row["app_type"]] = {
                    "credentials": row["credentials"],
                    "metadata": row["metadata"],
                }

            return credentials_map

        except Exception as e:
            logger.error(f"Error fetching user workflow credentials: {str(e)}")
            return None

    async def store_user_credentials(
        self,
        user_id: str,
        app_name: str,
        app_type: str,
        credentials: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Optional[str]:
        """
        Store user's OAuth credentials for an app

        Args:
            user_id: User's unique identifier
            app_name: Name of the app (e.g., "Gmail")
            app_type: Type of the app (e.g., "gmail")
            credentials: OAuth credentials (access_token, refresh_token, etc.)
            metadata: Additional metadata (email, scopes, etc.)

        Returns:
            Credential ID if successful, None otherwise
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None

            # Check if credential already exists
            existing = (
                self.client.table("user_credentials")
                .select("id")
                .eq("user_id", user_id)
                .eq("app_type", app_type)
                .execute()
            )

            data = {
                "user_id": user_id,
                "app_name": app_name,
                "app_type": app_type,
                "credentials": credentials,  # Store encrypted in production
                "metadata": metadata,
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if existing.data:
                # Update existing credential
                credential_id = existing.data[0]["id"]
                response = (
                    self.client.table("user_credentials")
                    .update(data)
                    .eq("id", credential_id)
                    .execute()
                )
                logger.info(f"Updated credentials for {app_name}: {credential_id}")
            else:
                # Insert new credential
                data["created_at"] = datetime.utcnow().isoformat()
                response = self.client.table("user_credentials").insert(data).execute()
                credential_id = response.data[0]["id"] if response.data else None
                logger.info(f"Stored new credentials for {app_name}: {credential_id}")

            # Also update user_connected_apps table for quick lookup
            await self._update_connected_apps(user_id, app_name, app_type)

            return credential_id

        except Exception as e:
            logger.error(f"Error storing user credentials: {str(e)}")
            return None

    async def _update_connected_apps(
        self, user_id: str, app_name: str, app_type: str
    ) -> bool:
        """Update the user_connected_apps table for quick lookup"""
        try:
            if not self.client:
                return False

            existing = (
                self.client.table("user_connected_apps")
                .select("id")
                .eq("user_id", user_id)
                .eq("app_type", app_type)
                .execute()
            )

            data = {
                "user_id": user_id,
                "app_name": app_name,
                "app_type": app_type,
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if existing.data:
                self.client.table("user_connected_apps").update(data).eq(
                    "id", existing.data[0]["id"]
                ).execute()
            else:
                data["created_at"] = datetime.utcnow().isoformat()
                self.client.table("user_connected_apps").insert(data).execute()

            return True

        except Exception as e:
            logger.error(f"Error updating connected apps: {str(e)}")
            return False

    async def update_user_credentials(
        self, user_id: str, app_name: str, credentials: Dict[str, Any]
    ) -> bool:
        """
        Update user's credentials for a specific app

        Args:
            user_id: User's unique identifier
            app_name: Name of the app
            credentials: Updated credentials dictionary

        Returns:
            bool: Success status
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False

            update_data = {
                "credentials": credentials,
                "updated_at": datetime.utcnow().isoformat(),
            }

            response = (
                self.client.table("user_credentials")
                .update(update_data)
                .eq("user_id", user_id)
                .eq("app_type", app_name)
                .execute()
            )

            if response.data:
                logger.info(f"Successfully updated credentials for {app_name}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating user credentials: {str(e)}")
            return False

    async def _refresh_access_token(
        self, user_id: str, app_name: str, credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Refresh expired access token using refresh token

        Args:
            user_id: User's unique identifier
            app_name: Name of the app
            credentials: Current credentials with refresh_token

        Returns:
            Dict with success status and new credentials
        """
        try:
            refresh_token = credentials.get("refresh_token")

            if not refresh_token:
                logger.error(f"No refresh token found for {app_name}")
                return {
                    "success": False,
                    "error": "No refresh token available. Please reconnect your account.",
                }

            token_endpoint = None
            client_id = None
            client_secret = None

            app_type = app_name.lower()
            logger.info(f"Refreshing token for app type: {app_type}")

            if app_type in [
                "gmail",
                "calendar",
                "google_drive",
                "google_docs",
                "google_calendar",
                "google_sheets",
            ]:
                token_endpoint = "https://oauth2.googleapis.com/token"
                client_id = credentials.get("client_id") or os.getenv(
                    "GOOGLE_CLIENT_ID"
                )
                client_secret = credentials.get("client_secret") or os.getenv(
                    "GOOGLE_CLIENT_SECRET"
                )

            elif app_type == "slack":
                token_endpoint = "https://slack.com/api/oauth.v2.access"
                client_id = credentials.get("client_id") or os.getenv("SLACK_CLIENT_ID")
                client_secret = credentials.get("client_secret") or os.getenv(
                    "SLACK_CLIENT_SECRET"
                )

            elif app_type == "notion":
                token_endpoint = "https://api.notion.com/v1/oauth/token"
                client_id = credentials.get("client_id") or os.getenv(
                    "NOTION_CLIENT_ID"
                )
                client_secret = credentials.get("client_secret") or os.getenv(
                    "NOTION_CLIENT_SECRET"
                )

            else:
                return {
                    "success": False,
                    "error": f"Token refresh not supported for {app_name}",
                }

            if not token_endpoint or not client_id or not client_secret:
                logger.error(f"Missing OAuth configuration for {app_name}")
                return {
                    "success": False,
                    "error": "OAuth configuration missing. Please reconnect your account.",
                }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                }

                response = await client.post(token_endpoint, data=data)
                response.raise_for_status()

                token_data = response.json()

                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in", 3600)

                if not new_access_token:
                    return {
                        "success": False,
                        "error": "Failed to obtain new access token",
                    }

                expires_at = (
                    datetime.utcnow() + timedelta(seconds=expires_in)
                ).isoformat()

                new_credentials = {
                    **credentials,
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expiry_date": expires_at,
                    "expires_in": expires_in,
                }

                await self.update_user_credentials(
                    user_id=user_id, app_name=app_name, credentials=new_credentials
                )

                logger.info(
                    f"Successfully refreshed token for {app_name}, expires at {expires_at}"
                )

                return {"success": True, "credentials": new_credentials}

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error refreshing token: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": f"Failed to refresh token: {e.response.status_code}",
            }
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return {"success": False, "error": f"Token refresh error: {str(e)}"}

    async def get_and_refresh_credentials(
        self, user_id: str, app_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get user credentials and refresh if expired.
        Handles both ISO string and timestamp formats for expiry_date.

        Args:
            user_id: User's unique identifier
            app_name: Name of the app (e.g., "gmail", "calendar", "gdrive")

        Returns:
            Dict with valid credentials or None if not found/refresh failed
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None

            response = (
                self.client.table("user_credentials")
                .select("credentials, metadata")
                .eq("user_id", user_id)
                .eq("app_type", app_name)
                .eq("is_active", True)
                .single()
                .execute()
            )

            if not response.data:
                logger.warning(f"No credentials found for {app_name}")
                return None

            credentials = response.data.get("credentials", {})

            expiry_raw = credentials.get("expiry_date")
            refresh_token = credentials.get("refresh_token")

            if not refresh_token:
                logger.warning(
                    f"No refresh token available for {app_name}. Returning existing credentials."
                )
                return credentials

            try:
                if isinstance(expiry_raw, str):
                    # ISO format string
                    expiry_dt = datetime.fromisoformat(
                        expiry_raw.replace("Z", "+00:00")
                    )
                elif isinstance(expiry_raw, (int, float)):
                    # Timestamp in milliseconds
                    expiry_dt = datetime.fromtimestamp(int(expiry_raw) / 1000)
                else:
                    logger.warning(
                        f"Unknown expiry_date format for {app_name}. Returning existing credentials."
                    )
                    return credentials
            except Exception as e:
                logger.warning(
                    f"Error parsing expiry date for {app_name}: {str(e)}. Returning existing credentials."
                )
                return credentials

            now = datetime.utcnow()

            if expiry_dt <= now + timedelta(minutes=5):
                logger.info(
                    f"{app_name.capitalize()} token expired or expiring soon. Refreshing..."
                )

                app_type = app_name.lower()
                token_endpoint = None
                client_id = None
                client_secret = None

                if app_type in [
                    "gmail",
                    "calendar",
                    "google drive",
                    "google docs",
                    "google_docs",
                    "google sheets",
                    "google_drive",
                    "google_calendar",
                    "google calendar",
                    "google_sheets",
                ]:
                    token_endpoint = "https://oauth2.googleapis.com/token"
                    client_id = credentials.get("client_id") or os.getenv(
                        "GOOGLE_CLIENT_ID"
                    )
                    client_secret = credentials.get("client_secret") or os.getenv(
                        "GOOGLE_CLIENT_SECRET"
                    )
                elif app_type == "slack":
                    token_endpoint = "https://slack.com/api/oauth.v2.access"
                    client_id = credentials.get("client_id") or os.getenv(
                        "SLACK_CLIENT_ID"
                    )
                    client_secret = credentials.get("client_secret") or os.getenv(
                        "SLACK_CLIENT_SECRET"
                    )
                elif app_type == "notion":
                    token_endpoint = "https://api.notion.com/v1/oauth/token"
                    client_id = credentials.get("client_id") or os.getenv(
                        "NOTION_CLIENT_ID"
                    )
                    client_secret = credentials.get("client_secret") or os.getenv(
                        "NOTION_CLIENT_SECRET"
                    )
                else:
                    logger.warning(
                        f"Token refresh not supported for {app_name}. Returning existing credentials."
                    )
                    return credentials

                if not token_endpoint or not client_id or not client_secret:
                    logger.error(f"Missing OAuth configuration for {app_name}")
                    return None

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    payload = {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    }

                    response = await client.post(token_endpoint, data=payload)

                    if response.status_code != 200:
                        logger.error(
                            f"Failed to refresh token for {app_name}: {response.text}"
                        )
                        return None

                    token_data = response.json()
                    new_access_token = token_data.get("access_token")
                    new_refresh_token = token_data.get("refresh_token", refresh_token)
                    expires_in = token_data.get("expires_in", 3600)

                    if not new_access_token:
                        logger.error(
                            f"No access token in refresh response for {app_name}"
                        )
                        return None

                    new_expiry = now + timedelta(seconds=expires_in)

                    updated_credentials = {
                        **credentials,
                        "access_token": new_access_token,
                        "refresh_token": new_refresh_token,
                        "expiry_date": new_expiry.isoformat(),
                        "expires_in": expires_in,
                    }

                    await self.update_user_credentials(
                        user_id, app_name, updated_credentials
                    )

                    logger.info(
                        f"{app_name.capitalize()} token refreshed successfully. New expiry: {new_expiry.isoformat()}"
                    )
                    return updated_credentials

            logger.info(f"{app_name.capitalize()} token is still valid.")
            return credentials

        except Exception as e:
            logger.error(
                f"Error in get_and_refresh_credentials for {app_name}: {str(e)}"
            )
            return None

    async def create_team_workflow(
        self,
        admin_id: str,
        workflow_title: str,
        workflow_json: Dict[str, Any],
        schedule_type: Optional[str] = None,
        schedule_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create a new team workflow"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None

            data = {
                "admin_id": admin_id,
                "workflow_title": workflow_title,
                "workflow_json": workflow_json,
                "members_json": [],
                "schedule_type": schedule_type,
                "schedule_config": schedule_config,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            response = self.client.table("custom_team_workflows").insert(data).execute()

            if response.data:
                workflow_id = response.data[0]["id"]
                logger.info(f"Created team workflow: {workflow_id}")
                return workflow_id

            return None

        except Exception as e:
            logger.error(f"Error creating team workflow: {str(e)}")
            return None

    async def get_team_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get team workflow by ID"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None

            response = (
                self.client.table("custom_team_workflows")
                .select("*")
                .eq("id", workflow_id)
                .eq("is_active", True)
                .single()
                .execute()
            )

            if response.data:
                return response.data

            return None

        except Exception as e:
            logger.error(f"Error fetching team workflow: {str(e)}")
            return None

    async def get_user_team_workflows(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all team workflows where user is admin or member"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return []

            # Get workflows where user is admin
            admin_response = (
                self.client.table("custom_team_workflows")
                .select("*")
                .eq("admin_id", user_id)
                .eq("is_active", True)
                .execute()
            )

            workflows = admin_response.data if admin_response.data else []

            # Get workflows where user is a member
            all_workflows = (
                self.client.table("custom_team_workflows")
                .select("*")
                .eq("is_active", True)
                .execute()
            )

            if all_workflows.data:
                for workflow in all_workflows.data:
                    members = workflow.get("members_json", [])
                    if any(member.get("user_id") == user_id for member in members):
                        if workflow not in workflows:
                            workflows.append(workflow)

            return workflows

        except Exception as e:
            logger.error(f"Error fetching user team workflows: {str(e)}")
            return []

    async def add_team_member(self, workflow_id: str, user_id: str) -> bool:
        """Add a member to a team workflow, including full_name from profiles"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False

            # Fetch workflow
            workflow = await self.get_team_workflow(workflow_id)
            if not workflow:
                return False

            members = workflow.get("members_json", [])

            # Check if user is already a member
            if any(member.get("user_id") == user_id for member in members):
                logger.info(
                    f"User {user_id} is already a member of workflow {workflow_id}"
                )
                return True

            # Fetch user's full name from profiles
            profile_response = (
                self.client.table("profiles")
                .select("full_name")
                .eq("id", user_id)
                .single()
                .execute()
            )

            full_name = (
                profile_response.data.get("full_name")
                if profile_response and profile_response.data
                else "Unknown User"
            )

            # Add new member with full_name
            members.append(
                {
                    "user_id": user_id,
                    "full_name": full_name,
                    "joined_at": datetime.utcnow().isoformat(),
                }
            )

            # Update workflow
            response = (
                self.client.table("custom_team_workflows")
                .update(
                    {
                        "members_json": members,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                )
                .eq("id", workflow_id)
                .execute()
            )

            return bool(response.data)

        except Exception as e:
            logger.error(f"Error adding team member: {str(e)}")
            return False

    async def create_workflow_invitation(
        self, workflow_id: str, inviter_id: str, invitee_email: str
    ) -> Optional[str]:
        """Create a workflow invitation"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None

            data = {
                "workflow_id": workflow_id,
                "inviter_id": inviter_id,
                "invitee_email": invitee_email,
                "status": "pending",
                "invited_at": datetime.utcnow().isoformat(),
            }

            response = (
                self.client.table("team_workflow_invitations").insert(data).execute()
            )

            if response.data:
                invitation_id = response.data[0]["id"]
                logger.info(f"Created invitation: {invitation_id}")
                return invitation_id

            return None

        except Exception as e:
            logger.error(f"Error creating invitation: {str(e)}")
            return None

    async def update_invitation_status(
        self, invitation_id: str, status: str, invitee_id: Optional[str] = None
    ) -> bool:
        """Update invitation status"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False

            update_data = {
                "status": status,
                "responded_at": datetime.utcnow().isoformat(),
            }

            if invitee_id:
                update_data["invitee_id"] = invitee_id

            response = (
                self.client.table("team_workflow_invitations")
                .update(update_data)
                .eq("id", invitation_id)
                .execute()
            )

            return bool(response.data)

        except Exception as e:
            logger.error(f"Error updating invitation status: {str(e)}")
            return False

    async def get_workflow_invitation(
        self, invitation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get invitation by ID"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None

            response = (
                self.client.table("team_workflow_invitations")
                .select("*")
                .eq("id", invitation_id)
                .single()
                .execute()
            )

            if response.data:
                return response.data

            return None

        except Exception as e:
            logger.error(f"Error fetching invitation: {str(e)}")
            return None
