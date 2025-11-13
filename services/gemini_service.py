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
        self.api_keys = []
        for i in range(
            1, 4
        ):  # Load GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                self.api_keys.append(key)

        # Also check for default GEMINI_API_KEY
        default_key = os.getenv("GEMINI_API_KEY")
        if default_key and default_key not in self.api_keys:
            self.api_keys.insert(0, default_key)

        self.current_key_index = 0

        if self.api_keys:
            self._configure_current_key()
            logger.info(
                f"Gemini service initialized with {len(self.api_keys)} API key(s)"
            )
        else:
            logger.warning("No GEMINI_API_KEY found in environment variables")
            self.model = None

    def _configure_current_key(self):
        """Configure Gemini with the current API key"""
        if self.current_key_index < len(self.api_keys):
            genai.configure(api_key=self.api_keys[self.current_key_index])
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            logger.info(
                f"Using API key index {self.current_key_index + 1}/{len(self.api_keys)}"
            )
        else:
            self.model = None
            logger.error("All API keys exhausted")

    def _rotate_api_key(self) -> bool:
        """Rotate to the next API key. Returns True if rotation successful, False if no more keys"""
        self.current_key_index += 1
        if self.current_key_index < len(self.api_keys):
            self._configure_current_key()
            logger.info(
                f"Rotated to API key {self.current_key_index + 1}/{len(self.api_keys)}"
            )
            return True
        else:
            logger.error("No more API keys available for rotation")
            return False

    def _make_api_call_with_retry(
        self, prompt_parts: List[str], generation_config: Any, max_retries: int = None
    ) -> str:
        """
        Make API call with automatic key rotation on 402 errors

        Args:
            prompt_parts: List of prompt parts to send to Gemini
            generation_config: Generation configuration
            max_retries: Maximum number of retries (defaults to number of API keys)

        Returns:
            Response text from Gemini

        Raises:
            Exception if all API keys are exhausted
        """
        if max_retries is None:
            max_retries = len(self.api_keys)

        attempts = 0
        while attempts < max_retries:
            try:
                if not self.model:
                    raise Exception("Gemini service not configured")

                response = self.model.generate_content(
                    prompt_parts, generation_config=generation_config
                )

                return response.text

            except Exception as e:
                error_str = str(e)

                # Check for 402 resource exhausted error
                if (
                    "429" in error_str
                    or "403" in error_str
                    or "Your API key was reported as leaked"
                    or "Resource exhausted" in error_str
                    or "quota" in error_str.lower()
                ):
                    logger.warning(
                        f"API key {self.current_key_index + 1} resource limit reached: {error_str}"
                    )

                    # Try to rotate to next key
                    if self._rotate_api_key():
                        attempts += 1
                        logger.info(
                            f"Retrying with next API key (attempt {attempts + 1}/{max_retries})"
                        )
                        continue
                    else:
                        raise Exception(
                            "All API keys have reached their resource limits"
                        )
                else:
                    # Not a 402 error, raise immediately
                    raise e

        raise Exception(f"Failed after {max_retries} attempts with different API keys")

    def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        response_format: str = "text",
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Public method to generate content using Gemini with automatic key rotation.
        Other services can call this method to leverage the key rotation feature.

        Args:
            prompt: The user prompt/request
            system_instruction: Optional system instruction to guide the model
            temperature: Controls randomness (0.0-1.0). Lower = more focused
            response_format: "text" or "json" for response format
            max_retries: Maximum retry attempts with different keys (defaults to number of keys)

        Returns:
            Dict with:
                - success: bool
                - content: Generated content (str)
                - error: Error message if failed

        Example:
            result = gemini_service.generate_content(
                prompt="Research about AI",
                system_instruction="You are a research assistant",
                temperature=0.3,
                response_format="text"
            )
            if result["success"]:
                content = result["content"]
        """
        try:
            if not self.model:
                return {
                    "success": False,
                    "error": "Gemini service not configured. Please check API keys.",
                }

            # Build prompt parts
            prompt_parts = []
            if system_instruction:
                prompt_parts.append(system_instruction)
            prompt_parts.append(prompt)

            # Set response format
            mime_type = (
                "application/json" if response_format == "json" else "text/plain"
            )

            # Configure generation settings
            generation_config = genai.types.GenerationConfig(
                temperature=temperature, response_mime_type=mime_type
            )

            # Make API call with automatic key rotation
            response_text = self._make_api_call_with_retry(
                prompt_parts=prompt_parts,
                generation_config=generation_config,
                max_retries=max_retries,
            )

            logger.info(f"Successfully generated content ({len(response_text)} chars)")

            return {"success": True, "content": response_text}

        except Exception as e:
            logger.error(f"Error generating content: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def is_configured(self) -> bool:
        """Check if Gemini is properly configured"""
        return self.model is not None

    async def process_workflow_request(
        self,
        prompt: str,
        workflow_templates: List[Dict[str, Any]],
        connected_apps: List[str],
        context: Optional[Dict[str, Any]] = None,
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
                return {"success": False, "error": "Gemini service not configured"}

            # Build system prompt
            system_prompt = self._build_workflow_analysis_prompt(
                workflow_templates=workflow_templates, connected_apps=connected_apps
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

            response_text = self._make_api_call_with_retry(
                prompt_parts=[system_prompt, user_message],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3, response_mime_type="application/json"
                ),
            )

            # Parse response
            result = json.loads(response_text)
            logger.info(f"Gemini analysis: {result.get('reasoning')}")

            return {
                "success": True,
                "workflow": result["workflow"],
                "is_new_workflow": result["is_new_workflow"],
                "reasoning": result.get("reasoning"),
            }

        except Exception as e:
            logger.error(
                f"Error processing workflow with Gemini: {str(e)}", exc_info=True
            )
            return {"success": False, "error": str(e)}

    def _build_workflow_analysis_prompt(
        self, workflow_templates: List[Dict[str, Any]], connected_apps: List[str]
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
        self, workflow: Dict[str, Any], parameters: Dict[str, Any]
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
                return {"success": False, "error": "Gemini service not configured"}

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

            response_text = self._make_api_call_with_retry(
                prompt_parts=[prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2, response_mime_type="application/json"
                ),
            )

            result = json.loads(response_text)
            logger.info(f"Gemini execution plan: {result.get('reasoning')}")

            return {
                "success": True,
                "function_calls": result["function_calls"],
                "reasoning": result.get("reasoning"),
            }

        except Exception as e:
            logger.error(
                f"Error determining workflow functions: {str(e)}", exc_info=True
            )
            return {"success": False, "error": str(e)}
