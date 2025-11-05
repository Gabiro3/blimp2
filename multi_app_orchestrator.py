"""
Multi-App Workflow Orchestrator
Handles complex workflows with 3+ apps using Gemini for intelligent function orchestration
"""

import logging
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai
import os

from services.supabase_service import SupabaseService
from function_registry import get_functions_for_apps

logger = logging.getLogger(__name__)


class MultiAppOrchestrator:
    """Orchestrates multi-app workflows (3+ apps) with Gemini-guided function calls"""

    def __init__(self, supabase_service: SupabaseService):
        self.supabase = supabase_service
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash-exp")
        else:
            self.model = None

    async def execute_multi_app_workflow(
        self,
        workflow: Dict[str, Any],
        credentials: Dict[str, Any],
        parameters: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a multi-app workflow with Gemini orchestration

        Args:
            workflow: Workflow definition with steps and required_apps
            credentials: User's app credentials
            parameters: Execution parameters
            user_id: User ID for credential refresh

        Returns:
            Dict with execution results
        """
        try:
            required_apps = workflow.get("required_apps", [])

            if len(required_apps) < 3:
                return {
                    "success": False,
                    "error": "Multi-app orchestrator requires 3+ apps",
                }

            logger.info(f"Executing multi-app workflow with apps: {required_apps}")

            # Refresh credentials if needed
            if user_id:
                logger.info("Refreshing credentials before execution...")
                refreshed_credentials = {}
                for app_name in required_apps:
                    fresh_creds = await self.supabase.get_and_refresh_credentials(
                        user_id=user_id, app_name=app_name
                    )
                    if fresh_creds:
                        cred_key = app_name.lower().replace(" ", "_")
                        refreshed_credentials[cred_key] = {"credentials": fresh_creds}
                    else:
                        logger.warning(f"Could not refresh credentials for {app_name}")

                if refreshed_credentials:
                    credentials = refreshed_credentials

            # Get all available functions for the required apps
            available_functions = get_functions_for_apps(required_apps)

            # Use Gemini to determine execution plan
            execution_plan = await self._generate_execution_plan(
                workflow=workflow,
                available_functions=available_functions,
                parameters=parameters,
            )

            if not execution_plan.get("success"):
                return execution_plan

            # Execute the planned function calls
            result = await self._execute_function_calls(
                function_calls=execution_plan["function_calls"],
                credentials=credentials,
                parameters=parameters,
            )

            return result

        except Exception as e:
            logger.error(f"Error executing multi-app workflow: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _generate_execution_plan(
        self,
        workflow: Dict[str, Any],
        available_functions: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use Gemini to generate an execution plan for the workflow

        Args:
            workflow: Workflow definition
            available_functions: Available functions for each app
            parameters: Execution parameters

        Returns:
            Dict with execution plan
        """
        try:
            if not self.model:
                return {"success": False, "error": "Gemini service not configured"}

            system_prompt = self._build_orchestration_prompt(available_functions)

            user_message = f"""
Workflow: {workflow.get('name')}
Description: {workflow.get('description')}
Required Apps: {', '.join(workflow.get('required_apps', []))}
Workflow Steps: {json.dumps(workflow.get('steps', []), indent=2)}
Parameters: {json.dumps(parameters, indent=2)}

Generate a detailed execution plan that:
1. Identifies which functions to call in which order
2. Defines the parameters for each function call
3. Handles data flow between functions (output from one becomes input to next)
4. Includes conditional logic if needed
5. Ensures proper error handling

Respond in JSON format with:
{{
    "function_calls": [
        {{
            "step": 1,
            "app": "app_name",
            "function": "function_name",
            "description": "what this step does",
            "parameters": {{}},
            "depends_on": [0] (or null if first step),
            "uses_output_from": "variable_name" (or null)
        }}
    ],
    "variable_mapping": {{}},
    "reasoning": "explanation of execution plan"
}}
"""

            response = self.model.generate_content(
                [system_prompt, user_message],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3, response_mime_type="application/json"
                ),
            )

            plan = json.loads(response.text)
            logger.info(f"Generated execution plan: {plan.get('reasoning')}")

            return {
                "success": True,
                "function_calls": plan["function_calls"],
                "variable_mapping": plan.get("variable_mapping", {}),
                "reasoning": plan.get("reasoning"),
            }

        except Exception as e:
            logger.error(f"Error generating execution plan: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _execute_function_calls(
        self,
        function_calls: List[Dict[str, Any]],
        credentials: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the planned function calls in sequence

        Args:
            function_calls: List of function calls to execute
            credentials: User credentials
            parameters: Execution parameters

        Returns:
            Dict with execution results
        """
        try:
            execution_results = {}
            outputs = {}  # Store outputs from each step

            for step in sorted(function_calls, key=lambda x: x.get("step", 0)):
                step_num = step.get("step", 0)
                app_name = step.get("app", "").lower()
                function_name = step.get("function", "")

                logger.info(f"Executing step {step_num}: {app_name}.{function_name}")

                try:
                    # Get function parameters, substituting any references to previous outputs
                    func_params = self._substitute_parameters(
                        step.get("parameters", {}), outputs
                    )

                    # Get credentials for this app
                    app_creds = credentials.get(app_name, {}).get("credentials", {})

                    # Dynamically call the function (implementation depends on your helper setup)
                    result = await self._call_helper_function(
                        app_name=app_name,
                        function_name=function_name,
                        parameters=func_params,
                        credentials=app_creds,
                    )

                    execution_results[f"step_{step_num}"] = result

                    # Store output for next steps
                    if result.get("success"):
                        outputs[f"step_{step_num}_output"] = result.get(
                            "result", result
                        )

                except Exception as e:
                    logger.error(f"Error executing step {step_num}: {str(e)}")
                    execution_results[f"step_{step_num}"] = {
                        "success": False,
                        "error": str(e),
                    }

            # Check if all steps succeeded
            all_successful = all(
                result.get("success", False) for result in execution_results.values()
            )

            return {
                "success": all_successful,
                "execution_results": execution_results,
                "outputs": outputs,
                "message": (
                    "Multi-app workflow completed successfully"
                    if all_successful
                    else "Some steps failed"
                ),
            }

        except Exception as e:
            logger.error(f"Error executing function calls: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _substitute_parameters(
        self, parameters: Dict[str, Any], outputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Substitute parameter references with actual output values

        Args:
            parameters: Parameters with potential references
            outputs: Previous step outputs

        Returns:
            Parameters with substitutions made
        """
        substituted = {}

        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("${"):
                # This is a reference to a previous output
                ref_key = value.strip("${}")
                substituted[key] = outputs.get(ref_key, value)
            else:
                substituted[key] = value

        return substituted

    async def _call_helper_function(
        self,
        app_name: str,
        function_name: str,
        parameters: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call the appropriate helper function dynamically

        Args:
            app_name: Name of the app (gmail, slack, etc.)
            function_name: Name of the function to call
            parameters: Function parameters
            credentials: App credentials

        Returns:
            Function result
        """
        try:
            # Import the appropriate helper module
            if app_name == "gmail":
                from helpers.gmail_helpers import GmailHelpers

                helper_class = GmailHelpers
            elif app_name == "slack":
                from helpers.slack_helpers import SlackHelpers

                helper_class = SlackHelpers
            elif app_name == "google_calendar":
                from helpers.gcalendar_helpers import GCalendarHelpers

                helper_class = GCalendarHelpers
            elif app_name == "notion":
                from helpers.notion_helpers import NotionHelpers

                helper_class = NotionHelpers
            elif app_name == "google_drive":
                from helpers.gdrive_helpers import GDriveHelpers

                helper_class = GDriveHelpers
            elif app_name == "google_docs":
                from helpers.google_docs_helpers import GoogleDocsHelpers

                helper_class = GoogleDocsHelpers
            elif app_name == "trello":
                from helpers.trello_helpers import TrelloHelpers

                helper_class = TrelloHelpers
            elif app_name == "github":
                from helpers.github_helpers import GitHubHelpers

                helper_class = GitHubHelpers
            elif app_name == "discord":
                from helpers.discord_helpers import DiscordHelpers

                helper_class = DiscordHelpers
            else:
                return {"success": False, "error": f"Unknown app: {app_name}"}

            # Get the function from the helper class
            if not hasattr(helper_class, function_name):
                return {
                    "success": False,
                    "error": f"Function {function_name} not found in {app_name}",
                }

            helper_function = getattr(helper_class, function_name)

            # Add credentials to parameters
            parameters["credentials"] = credentials

            # Call the function
            result = await helper_function(**parameters)

            return {"success": result.get("success", True), "result": result}

        except Exception as e:
            logger.error(f"Error calling helper function: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _build_orchestration_prompt(self, available_functions: Dict[str, Any]) -> str:
        """Build system prompt for multi-app orchestration"""

        return f"""You are an expert multi-app workflow orchestrator for Blimp. Your role is to determine the optimal sequence and parameters for executing complex workflows across multiple apps.

Available Functions by App:
{json.dumps(available_functions, indent=2)}

Guidelines for Orchestration:
1. Analyze the workflow description and requirements
2. Plan the execution order based on data dependencies
3. Specify exact parameters for each function call
4. Handle data flow between steps (e.g., output from Gmail becomes input to Slack)
5. Support conditional logic where needed
6. Ensure error handling and validation
7. Optimize for minimal API calls and efficient data transfer
8. Use proper data types and formats for each function

Common Multi-App Patterns:
- Gmail → Notion → Slack: Extract emails, save to Notion, notify in Slack
- Trello → Slack → Google Docs: Get Trello cards, post to Slack, document in Docs
- GitHub → Discord → Google Docs: Monitor repos, alert on Discord, archive in Docs
- Google Docs → Gmail → Slack: Generate docs, email recipients, post summary to Slack

Output Format Requirements:
- Each function call must have clear step number and app name
- Parameters must be specific and complete
- Handle array outputs by specifying which item(s) to use
- Include error handling strategies
"""
