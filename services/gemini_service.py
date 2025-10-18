"""
Gemini AI Service
Handles interaction with Google's Gemini API for workflow processing
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai

from function_registry import FUNCTION_REGISTRY, get_functions_for_apps

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Gemini API"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            logger.info("Gemini service initialized successfully")
        else:
            logger.warning("GEMINI_API_KEY not found in environment variables")
            self.model = None
    
    def is_configured(self) -> bool:
        """Check if Gemini is properly configured"""
        return self.model is not None
    
    async def process_workflow_request(
        self,
        prompt: str,
        workflow_templates: List[Dict[str, Any]],
        connected_apps: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a workflow request using Gemini
        
        Args:
            prompt: User's workflow request
            workflow_templates: List of available workflow templates
            connected_apps: List of apps user has connected
            context: Additional context
            
        Returns:
            Dict with workflow data and whether it's new
        """
        try:
            if not self.model:
                return {
                    "success": False,
                    "error": "Gemini service not configured"
                }
            
            # Build system prompt
            system_prompt = self._build_workflow_analysis_prompt(
                workflow_templates=workflow_templates,
                connected_apps=connected_apps
            )
            
            # Build user message
            user_message = f"""
User Request: {prompt}

Additional Context: {json.dumps(context) if context else "None"}

Please analyze this request and determine:
1. Does it match an existing workflow template?
2. If yes, which one? If no, create a new workflow definition.
3. What apps are required?
4. Provide a clear workflow name and description.

Respond in JSON format with:
{{
    "is_new_workflow": boolean,
    "workflow": {{
        "id": "template_id or null if new",
        "name": "workflow name",
        "description": "workflow description",
        "required_apps": ["app1", "app2"],
        "category": "category name"
    }},
    "reasoning": "explanation of your decision"
}}
"""
            
            # Call Gemini
            response = self.model.generate_content(
                [system_prompt, user_message],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    response_mime_type="application/json"
                )
            )
            
            # Parse response
            result = json.loads(response.text)
            logger.info(f"Gemini analysis: {result.get('reasoning')}")
            
            return {
                "success": True,
                "workflow": result["workflow"],
                "is_new_workflow": result["is_new_workflow"],
                "reasoning": result.get("reasoning")
            }
            
        except Exception as e:
            logger.error(f"Error processing workflow with Gemini: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_workflow_analysis_prompt(
        self,
        workflow_templates: List[Dict[str, Any]],
        connected_apps: List[str]
    ) -> str:
        """Build system prompt for workflow analysis"""
        
        templates_str = json.dumps(workflow_templates, indent=2)
        connected_apps_str = ", ".join(connected_apps) if connected_apps else "None"
        
        return f"""You are an AI workflow automation expert for Blimp, a platform that helps users automate tasks across different apps.

Your role is to analyze user requests and determine if they match existing workflow templates or if a new workflow needs to be created.

Available Workflow Templates:
{templates_str}

User's Connected Apps:
{connected_apps_str}

Available App Functions:
{json.dumps(FUNCTION_REGISTRY, indent=2)}

Guidelines:
1. Match user requests to existing templates when possible (look for semantic similarity)
2. For new workflows, create clear, descriptive names and descriptions
3. Identify all required apps for the workflow
4. Consider the user's connected apps when making recommendations
5. Be specific about what the workflow will do
6. Use lowercase app names (gmail, gcalendar, notion, slack, discord, gdrive)

Common Workflow Patterns:
- Email to Calendar: Get emails and create calendar events
- Email to Drive: Save email attachments to Google Drive
- Calendar to Slack: Send calendar reminders to Slack
- Notion to Email: Email summaries of Notion pages
- Multi-app sync: Keep data synchronized across multiple apps
"""
    
    async def determine_workflow_functions(
        self,
        workflow: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use Gemini to determine which utility functions to call for a workflow
        
        Args:
            workflow: Workflow definition
            parameters: Execution parameters
            
        Returns:
            Dict with function calls to make
        """
        try:
            if not self.model:
                return {
                    "success": False,
                    "error": "Gemini service not configured"
                }
            
            # Get available functions for required apps
            required_apps = workflow.get("required_apps", [])
            available_functions = get_functions_for_apps(required_apps)
            
            prompt = f"""
Workflow: {workflow.get('name')}
Description: {workflow.get('description')}
Required Apps: {', '.join(required_apps)}
Parameters: {json.dumps(parameters)}

Available Functions:
{json.dumps(available_functions, indent=2)}

Determine the sequence of function calls needed to execute this workflow.
Consider the workflow description and parameters to decide which functions to call and in what order.

Respond in JSON format with:
{{
    "function_calls": [
        {{
            "app": "app_name",
            "function": "function_name",
            "parameters": {{}},
            "description": "what this call does"
        }}
    ],
    "reasoning": "explanation of the execution plan"
}}
"""
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            
            result = json.loads(response.text)
            logger.info(f"Gemini execution plan: {result.get('reasoning')}")
            
            return {
                "success": True,
                "function_calls": result["function_calls"],
                "reasoning": result.get("reasoning")
            }
            
        except Exception as e:
            logger.error(f"Error determining workflow functions: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
