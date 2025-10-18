"""
Supabase Service - Database operations
Handles all interactions with Supabase database
"""

import os
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from datetime import datetime

logger = logging.getLogger(__name__)


class SupabaseService:
    """Service for interacting with Supabase database"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
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
            
            response = self.client.table("user_connected_apps").select("app_name").eq("user_id", user_id).eq("is_active", True).execute()
            
            if response.data:
                connected_apps = [row["app_name"] for row in response.data]
                logger.info(f"Found {len(connected_apps)} connected apps for user {user_id}")
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
            
            response = self.client.table("workflow_templates").select("id, name, description, required_apps, category").eq("is_active", True).execute()
            
            if response.data:
                logger.info(f"Retrieved {len(response.data)} workflow templates")
                return response.data
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching workflow templates: {str(e)}")
            return []
    
    async def get_workflow(self, workflow_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific workflow by ID"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            # Try workflow_templates first
            response = self.client.table("workflow_templates").select("*").eq("id", workflow_id).eq("is_active", True).single().execute()
            
            if response.data:
                return response.data
            
            # Try user_workflows
            response = self.client.table("user_workflows").select("*").eq("id", workflow_id).eq("user_id", user_id).eq("is_active", True).single().execute()
            
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
        webhook_url: Optional[str] = None
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
                "updated_at": datetime.utcnow().isoformat()
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
        parameters: Optional[Dict[str, Any]] = None
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
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = self.client.table("workflow_executions").insert(data).execute()
            
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"Error saving workflow execution: {str(e)}")
            return False
    
    async def update_workflow_status(
        self,
        execution_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update workflow execution status"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False
            
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if result:
                update_data["result"] = result
            
            response = self.client.table("workflow_executions").update(update_data).eq("execution_id", execution_id).execute()
            
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"Error updating workflow status: {str(e)}")
            return False
    
    async def get_user_workflow_credentials(
        self,
        user_id: str,
        workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get user's credentials for workflow apps"""
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            response = self.client.table("user_credentials").select("app_type, credentials, metadata").eq("user_id", user_id).eq("is_active", True).execute()
            
            if not response.data:
                return None
            
            credentials_map = {}
            for row in response.data:
                credentials_map[row["app_type"]] = {
                    "credentials": row["credentials"],
                    "metadata": row["metadata"]
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
        metadata: Dict[str, Any]
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
            existing = self.client.table("user_credentials").select("id").eq("user_id", user_id).eq("app_type", app_type).execute()
            
            data = {
                "user_id": user_id,
                "app_name": app_name,
                "app_type": app_type,
                "credentials": credentials,  # Store encrypted in production
                "metadata": metadata,
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if existing.data:
                # Update existing credential
                credential_id = existing.data[0]["id"]
                response = self.client.table("user_credentials").update(data).eq("id", credential_id).execute()
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
