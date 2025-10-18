"""
Workflow Orchestrator
Central coordinator for executing workflows and calling utility functions
"""

import logging
from typing import Dict, Any, List
import importlib

from services.supabase_service import SupabaseService
from utils.gmail_calendar_utils import GmailCalendarUtils
from utils.gmail_gdrive_utils import GmailGDriveUtils

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """Orchestrates workflow execution by coordinating utility function calls"""
    
    def __init__(self, supabase_service: SupabaseService):
        self.supabase = supabase_service
        
        # Register utility modules
        self.utils_registry = {
            "gmail_calendar": GmailCalendarUtils,
            "gmail_gdrive": GmailGDriveUtils,
            # Add more utility modules as they're created
        }
        
        logger.info(f"Orchestrator initialized with {len(self.utils_registry)} utility modules")
    
    async def execute_workflow(
        self,
        workflow: Dict[str, Any],
        credentials: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a workflow by calling appropriate utility functions
        
        Args:
            workflow: Workflow definition with name, description, required_apps
            credentials: User's app credentials
            parameters: Execution parameters
            
        Returns:
            Dict with execution results
        """
        try:
            workflow_name = workflow.get("name", "").lower()
            required_apps = workflow.get("required_apps", [])
            
            logger.info(f"Executing workflow: {workflow_name}")
            logger.info(f"Required apps: {required_apps}")
            
            # Determine which utility module to use based on required apps
            util_key = self._determine_util_module(required_apps)
            
            if not util_key:
                return {
                    "success": False,
                    "error": f"No utility module found for apps: {required_apps}"
                }
            
            util_class = self.utils_registry.get(util_key)
            if not util_class:
                return {
                    "success": False,
                    "error": f"Utility module '{util_key}' not registered"
                }
            
            # Initialize utility class with credentials
            util_instance = util_class(credentials)
            
            # Execute based on workflow type
            result = await self._execute_workflow_logic(
                util_instance=util_instance,
                workflow=workflow,
                parameters=parameters
            )
            
            logger.info(f"Workflow execution completed: {result.get('success')}")
            return result
            
        except Exception as e:
            logger.error(f"Error executing workflow: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _determine_util_module(self, required_apps: List[str]) -> str:
        """
        Determine which utility module to use based on required apps
        
        Args:
            required_apps: List of required app names
            
        Returns:
            Utility module key
        """
        # Normalize app names
        apps = [app.lower() for app in required_apps]
        apps_set = set(apps)
        
        # Check for known combinations
        if {"gmail", "gcalendar"}.issubset(apps_set):
            return "gmail_calendar"
        elif {"gmail", "gdrive"}.issubset(apps_set):
            return "gmail_gdrive"
        
        # Add more combinations as needed
        
        return None
    
    async def _execute_workflow_logic(
        self,
        util_instance: Any,
        workflow: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the actual workflow logic using the utility instance
        
        Args:
            util_instance: Initialized utility class instance
            workflow: Workflow definition
            parameters: Execution parameters
            
        Returns:
            Execution results
        """
        workflow_name = workflow.get("name", "").lower()
        
        # Route to appropriate workflow execution method
        if "gmail" in workflow_name and "calendar" in workflow_name:
            return await util_instance.emails_to_calendar_events(
                max_emails=parameters.get("max_emails", 10),
                query=parameters.get("query", "is:unread")
            )
        
        elif "gmail" in workflow_name and "drive" in workflow_name:
            return await util_instance.save_attachments_to_drive(
                max_emails=parameters.get("max_emails", 10),
                folder_name=parameters.get("folder_name", "Email Attachments")
            )
        
        # Add more workflow routing logic as needed
        
        return {
            "success": False,
            "error": f"No execution logic defined for workflow: {workflow_name}"
        }
