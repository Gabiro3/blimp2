"""
Blimp MCP Server - Main FastAPI Application
Handles workflow processing and execution for AI-powered automation
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import uuid
from datetime import datetime
from dotenv import load_dotenv
import os
import json

from services.gemini_service import GeminiService
from services.supabase_service import SupabaseService
from orchestrator import WorkflowOrchestrator
from team_orchestrator import TeamWorkflowOrchestrator
from app_chat_orchestrator import AppChatOrchestrator
from multi_app_orchestrator import MultiAppOrchestrator
from services.email_service import EmailService

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Blimp MCP Server",
    description="AI-powered workflow automation backend",
    version="1.0.0",
)

# CORS middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [
    origin.strip() for origin in allowed_origins.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
supabase_service = SupabaseService()
gemini_service = GeminiService()
orchestrator = WorkflowOrchestrator(supabase_service)
app_chat_orchestrator = AppChatOrchestrator()
email_service = EmailService()
team_orchestrator = TeamWorkflowOrchestrator(supabase_service, email_service)
multi_app_orchestrator = MultiAppOrchestrator(supabase_service)


class RequiredApp(BaseModel):
    app_name: str
    is_connected: bool


# Request/Response Models
class ProcessWorkflowRequest(BaseModel):
    user_id: str
    prompt: str
    context: Optional[Dict[str, Any]] = None


class ProcessWorkflowResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    workflow_description: str
    required_apps: List[RequiredApp]  # <- change from List[str] to List[RequiredApp]
    is_new_workflow: bool
    message: str


class ExecuteWorkflowRequest(BaseModel):
    user_id: str
    workflow_id: str
    parameters: Optional[Dict[str, Any]] = None


class ExecuteWorkflowResponse(BaseModel):
    execution_id: str
    status: str
    result: Dict[str, Any]
    message: str


class ExecuteCustomWorkflowRequest(BaseModel):
    user_id: str
    workflow_id: str
    workflow_title: str
    workflow_json: str  # JSON string containing steps and n8n_workflow
    parameters: Optional[Dict[str, Any]] = None


class ExecuteCustomWorkflowResponse(BaseModel):
    execution_id: str
    status: str
    result: Dict[str, Any]
    workflow_type: str
    apps_used: List[str]
    message: str


class AppCredentials(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    expiry_date: Optional[int] = None
    scope: Optional[str] = None


class AppMetadata(BaseModel):
    email: Optional[str] = None
    connected_at: str
    scopes: Optional[List[str]] = None


class ConnectAppRequest(BaseModel):
    user_id: str
    app_name: str
    app_type: str
    credentials: AppCredentials
    metadata: AppMetadata


class ConnectAppResponse(BaseModel):
    success: bool
    message: str
    credential_id: Optional[str] = None
    app_name: str
    error: Optional[str] = None


class AppChatPromptRequest(BaseModel):
    user_id: str
    query: str
    inquiry_app: str  # gmail, slack, gcalendar


class AppChatPromptResponse(BaseModel):
    success: bool
    data_fetch_plan: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]]
    reasoning: str
    message: str
    query_type: Optional[str] = "informational"


class AppChatExecuteRequest(BaseModel):
    user_id: str
    query: str
    query_type: str  # informational, action-oriented
    data_fetch_plan: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None


class AppChatExecuteResponse(BaseModel):
    success: bool
    answer: str
    confidence: str
    data_found: bool
    relevant_items: List[Dict[str, Any]]
    resource_urls: List[Dict[str, Any]]
    actions_taken: List[Dict[str, Any]]
    suggested_actions: List[Dict[str, Any]]
    actionable_insights: Optional[str] = None
    message: str


class CreateTeamWorkflowRequest(BaseModel):
    admin_id: str
    workflow_title: str
    workflow_json: str  # JSON string containing steps and configuration
    schedule_type: Optional[str] = None  # 'daily', 'weekly', 'monthly', 'custom'
    schedule_config: Optional[Dict[str, Any]] = None


class CreateTeamWorkflowResponse(BaseModel):
    success: bool
    workflow_id: str
    message: str


class InviteTeamMemberRequest(BaseModel):
    workflow_id: str
    inviter_id: str
    invitee_emails: List[str]


class InviteTeamMemberResponse(BaseModel):
    success: bool
    invitations_sent: int
    failed_invitations: List[str]
    message: str


class AcceptInvitationRequest(BaseModel):
    invitation_id: str
    user_id: str


class AcceptInvitationResponse(BaseModel):
    success: bool
    workflow_id: str
    workflow_title: str
    message: str


class TeamWorkflowResponse(BaseModel):
    success: bool
    workflow: Dict[str, Any]
    message: str


class ExecuteTeamWorkflowRequest(BaseModel):
    workflow_id: str
    user_id: str
    parameters: Optional[Dict[str, Any]] = None


class ExecuteTeamWorkflowResponse(BaseModel):
    success: bool
    execution_id: str
    status: str
    result: Dict[str, Any]
    message: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Blimp MCP Server",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "services": {
            "supabase": supabase_service.client is not None,
            "gemini": gemini_service.is_configured(),
            "orchestrator": True,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/process-workflow", response_model=ProcessWorkflowResponse)
async def process_workflow(request: ProcessWorkflowRequest):
    """
    Process a workflow request using Gemini AI

    Flow:
    1. Fetch workflow templates from Supabase
    2. Send prompt + templates to Gemini
    3. Gemini decides if workflow exists or creates new one
    4. Return required apps for user to connect
    """
    try:
        logger.info(f"Processing workflow for user {request.user_id}: {request.prompt}")

        # Fetch all workflow templates from Supabase
        workflow_templates = await supabase_service.get_all_workflow_templates()
        logger.info(f"Fetched {len(workflow_templates)} workflow templates")

        # Get user's connected apps
        connected_apps = await supabase_service.get_user_connected_apps(request.user_id)
        logger.info(f"User has {len(connected_apps)} connected apps")

        # Process with Gemini
        gemini_result = await gemini_service.process_workflow_request(
            prompt=request.prompt,
            workflow_templates=workflow_templates,
            connected_apps=connected_apps,
            context=request.context,
        )

        if not gemini_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Gemini processing failed: {gemini_result.get('error')}",
            )

        workflow_data = gemini_result["workflow"]
        is_new = gemini_result["is_new_workflow"]
        required_apps_list = workflow_data["required_apps"]
        logger.info(f"Required apps: {required_apps_list}")

        required_apps_with_status = [
            {"app_name": app, "is_connected": app in connected_apps}
            for app in required_apps_list
        ]

        logger.info(f"Required apps with status: {required_apps_with_status}")

        # If new workflow, save it to database
        if is_new:
            workflow_id = str(uuid.uuid4())
            await supabase_service.save_user_workflow(
                user_id=request.user_id,
                workflow_id=workflow_id,
                name=workflow_data["name"],
                description=workflow_data["description"],
                prompt=request.prompt,
                required_apps=required_apps_with_status,
                category=workflow_data.get("category", "custom"),
            )
            logger.info(f"Saved new workflow: {workflow_id}")
        else:
            workflow_id = workflow_data["id"]
            logger.info(f"Using existing workflow: {workflow_id}")

        return ProcessWorkflowResponse(
            workflow_id=workflow_id,
            workflow_name=workflow_data["name"],
            workflow_description=workflow_data["description"],
            required_apps=required_apps_with_status,
            is_new_workflow=is_new,
            message="Workflow processed successfully. Please connect the required apps to execute.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/execute-workflow", response_model=ExecuteWorkflowResponse)
async def execute_workflow(request: ExecuteWorkflowRequest):
    """
    Execute a workflow by calling its utility functions

    Flow:
    1. Get workflow details from database
    2. Verify user has connected required apps
    3. Get user credentials for required apps
    4. Execute workflow using orchestrator
    5. Return results to user
    """
    try:
        logger.info(
            f"Executing workflow {request.workflow_id} for user {request.user_id}"
        )

        # Get workflow details
        workflow = await supabase_service.get_workflow(
            workflow_id=request.workflow_id, user_id=request.user_id
        )

        if not workflow:
            raise HTTPException(
                status_code=404, detail=f"Workflow {request.workflow_id} not found"
            )

        # Verify user has connected required apps
        connected_apps = await supabase_service.get_user_connected_apps(request.user_id)
        required_apps = workflow.get("required_apps", [])

        missing_apps = [
            app for app in required_apps if app not in [a for a in connected_apps]
        ]
        if missing_apps:
            raise HTTPException(
                status_code=404,
                detail=f"Missing required app connections: {', '.join(missing_apps)}",
            )

        # Get user credentials for workflow
        credentials = await supabase_service.get_user_workflow_credentials(
            user_id=request.user_id, workflow_id=request.workflow_id
        )

        if not credentials:
            raise HTTPException(
                status_code=400,
                detail="Unable to retrieve app credentials. Please reconnect your apps.",
            )

        # Generate execution ID
        execution_id = str(uuid.uuid4())

        # Save execution record
        await supabase_service.save_workflow_execution(
            user_id=request.user_id,
            workflow_id=request.workflow_id,
            execution_id=execution_id,
            status="running",
            parameters=request.parameters,
        )

        # 5. Choose orchestrator based on number of required apps
        if len(required_apps) >= 3:
            logger.info(
                f"Using multi_app_orchestrator for multi-app workflow ({len(required_apps)} apps)"
            )
            result = await multi_app_orchestrator.execute_multi_app_workflow(
                workflow=workflow,
                credentials=credentials,
                parameters=request.parameters or {},
                user_id=request.user_id,
            )
        else:
            logger.info(
                f"Using standard orchestrator for workflow ({len(required_apps)} apps)"
            )
            result = await orchestrator.execute_workflow(
                workflow=workflow,
                credentials=credentials,
                parameters=request.parameters or {},
            )

        # Update execution status
        status = "completed" if result.get("success") else "failed"
        await supabase_service.update_workflow_status(
            execution_id=execution_id, status=status, result=result
        )

        logger.info(f"Workflow execution {execution_id} {status}")

        return ExecuteWorkflowResponse(
            execution_id=execution_id,
            status=status,
            result=result,
            message=(
                f"Workflow executed successfully"
                if result.get("success")
                else f"Workflow execution failed: {result.get('error')}"
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/execute-custom-workflow", response_model=ExecuteCustomWorkflowResponse)
async def execute_custom_workflow(request: ExecuteCustomWorkflowRequest):
    """
    Execute a custom workflow immediately without processing through Gemini

    Flow:
    1. Parse workflow_json to extract steps and app types
    2. Determine workflow type based on app combinations
    3. Verify user has connected required apps
    4. Get user credentials for required apps
    5. Execute workflow using orchestrator
    6. Return results to user
    """
    try:
        logger.info(
            f"Executing custom workflow '{request.workflow_title}' for user {request.user_id}"
        )

        # Parse workflow_json
        try:
            workflow_data = json.loads(request.workflow_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid workflow_json format: {str(e)}"
            )

        # Extract steps from workflow data
        steps = workflow_data.get("steps", [])
        if not steps:
            raise HTTPException(
                status_code=400, detail="No steps found in workflow_json"
            )

        # Extract app types (excluding Trigger)
        app_types = []
        for step in steps:
            app_type = step.get("app_type", "")
            if app_type and app_type.lower() != "trigger":
                app_types.append(app_type)

        if len(app_types) < 2:
            raise HTTPException(
                status_code=400,
                detail="Workflow must have at least 2 apps (excluding Trigger)",
            )

        logger.info(f"Detected apps in workflow: {app_types}")

        # Determine workflow type based on app combination
        workflow_type = None
        app_types_lower = [app.lower() for app in app_types]

        # Map app combinations to workflow types
        if "gmail" in app_types_lower and "google calendar" in app_types_lower:
            workflow_type = "gmail_to_calendar"
        elif "gmail" in app_types_lower and "google drive" in app_types_lower:
            workflow_type = "gmail_to_gdrive"
        elif "notion" in app_types_lower and "slack" in app_types_lower:
            workflow_type = "notion_to_slack"
        elif "notion" in app_types_lower and "gmail" in app_types_lower:
            workflow_type = "notion_to_gmail"
        elif "notion" in app_types_lower and "discord" in app_types_lower:
            workflow_type = "notion_to_discord"
        elif "google calendar" in app_types_lower and "slack" in app_types_lower:
            workflow_type = "gcalendar_to_slack"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported app combination: {', '.join(app_types)}",
            )

        logger.info(f"Determined workflow type: {workflow_type}")

        # Verify user has connected required apps
        connected_apps = await supabase_service.get_user_connected_apps(request.user_id)
        connected_apps_lower = [app.lower() for app in connected_apps]

        missing_apps = [
            app for app in app_types if app.lower() not in connected_apps_lower
        ]
        if missing_apps:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required app connections: {', '.join(missing_apps)}",
            )

        # Get user credentials for the required apps
        # Get user credentials for workflow
        credentials = await supabase_service.get_user_workflow_credentials(
            user_id=request.user_id, workflow_id=request.workflow_id
        )

        # Generate execution ID
        execution_id = str(uuid.uuid4())

        # Create workflow object for orchestrator
        workflow = {
            "id": execution_id,
            "name": request.workflow_title,
            "description": f"Custom workflow: {request.workflow_title}",
            "type": workflow_type,
            "required_apps": app_types,
            "steps": steps,
        }

        if len(app_types) >= 3:
            logger.info(
                f"Using multi_app_orchestrator for multi-app custom workflow ({len(app_types)} apps)"
            )
            result = await multi_app_orchestrator.execute_multi_app_workflow(
                workflow=workflow,
                credentials=credentials,
                parameters=request.parameters or {},
                user_id=request.user_id,
            )
        else:
            logger.info(
                f"Using standard orchestrator for custom workflow ({len(app_types)} apps)"
            )
            result = await orchestrator.execute_workflow(
                workflow=workflow,
                credentials=credentials,
                parameters=request.parameters or {},
            )

        status = "completed" if result.get("success") else "failed"

        logger.info(f"Custom workflow execution {execution_id} {status}")

        return ExecuteCustomWorkflowResponse(
            execution_id=execution_id,
            status=status,
            result=result,
            workflow_type=workflow_type,
            apps_used=app_types,
            message=(
                f"Custom workflow executed successfully"
                if result.get("success")
                else f"Custom workflow execution failed: {result.get('error')}"
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing custom workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows")
async def list_workflows(user_id: str):
    """List all available workflow templates"""
    try:
        templates = await supabase_service.get_all_workflow_templates()
        return {"success": True, "workflows": templates, "count": len(templates)}
    except Exception as e:
        logger.error(f"Error listing workflows: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mcp/connect-app", response_model=ConnectAppResponse)
async def connect_app(request: ConnectAppRequest):
    """
    Receive OAuth tokens from UI and store user's app credentials

    Flow:
    1. Receive app credentials from UI
    2. Validate credentials
    3. Store in Supabase with encryption
    4. Create/update n8n credentials for this user
    5. Return credential ID
    """
    try:
        logger.info(f"Connecting app {request.app_name} for user: {request.user_id}")

        # Step 1: Validate credentials
        if not request.credentials.access_token:
            raise HTTPException(status_code=404, detail="Access token is required")

        # Step 2: Store credentials in Supabase
        logger.info(f"Storing credentials for {request.app_name}")
        credential_id = await supabase_service.store_user_credentials(
            user_id=request.user_id,
            app_name=request.app_name,
            app_type=request.app_type,
            credentials=request.credentials.dict(),
            metadata=request.metadata.dict(),
        )

        if not credential_id:
            raise HTTPException(status_code=500, detail="Failed to store credentials")

        # Step 3: Create/update n8n credentials for this user
        logger.info(f"Creating n8n credentials for user {request.user_id}")
        n8n_credential_id = await supabase_service.store_user_credentials(
            user_id=request.user_id,
            app_name=request.app_name,  # You can change this as needed
            app_type=request.app_type,
            credentials=request.credentials.dict(),
            metadata={},  # Adjust this based on what metadata needs to be stored
        )

        if not n8n_credential_id:
            logger.warning(
                f"Failed to create n8n credential, but Supabase storage succeeded"
            )

        logger.info(f"App connected successfully: {request.app_name}")

        return ConnectAppResponse(
            success=True,
            message="App connected successfully",
            credential_id=credential_id,
            app_name=request.app_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting app: {str(e)}")
        return ConnectAppResponse(
            success=False,
            message="Failed to connect app",
            credential_id=None,
            app_name=request.app_name,
            error=str(e),
        )


@app.get("/api/connected-apps")
async def get_connected_apps(user_id: str):
    """Get user's connected apps"""
    try:
        apps = await supabase_service.get_user_connected_apps(user_id)
        return {"success": True, "connected_apps": apps, "count": len(apps)}
    except Exception as e:
        logger.error(f"Error getting connected apps: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/app-chat/prompt", response_model=AppChatPromptResponse)
async def app_chat_prompt(request: AppChatPromptRequest):
    """
    Process user query and determine data fetching plan

    Flow:
    1. Verify user has connected the inquiry app
    2. Send query to Gemini to analyze
    3. Gemini determines what data to fetch and what functions to call
    4. Return data fetching plan to client
    """
    try:
        logger.info(f"Processing app chat query for user {request.user_id}: {request}")

        # Process query with orchestrator
        result = await app_chat_orchestrator.process_query(
            user_id=request.user_id,
            query=request.query,
            inquiry_app=request.inquiry_app,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Failed to process query")
            )
        logger.info(f"Result: {result}")

        return AppChatPromptResponse(
            success=True,
            data_fetch_plan=result.get("data_fetch_plan", {}),
            actions=result.get("actions", []),
            reasoning=result.get("reasoning", ""),
            message="Query analyzed successfully. Ready to fetch data.",
            query_type=result.get("query_type", "informational"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing app chat prompt: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/app-chat/execute", response_model=AppChatExecuteResponse)
async def app_chat_execute(request: AppChatExecuteRequest):
    """
    Execute data fetching and generate AI response

    Flow:
    1. Fetch data from the app based on the plan
    2. Filter sensitive information
    3. Pass data to Gemini for response generation
    4. Execute any requested actions (e.g., send reply)
    5. Return AI response with resource URLs
    """
    try:
        logger.info(f"Executing app chat query for user {request.user_id}")
        logger.info(f"Request details: {request}")

        # Execute query with orchestrator
        result = await app_chat_orchestrator.execute_query(
            query_type=request.query_type,
            user_id=request.user_id,
            query=request.query,
            data_fetch_plan=request.data_fetch_plan,
            actions=request.actions,
        )
        logger.info(f"Execution result: {result}")

        if not result.get("success"):
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to execute query")
            )

        actions_message = ""
        if result.get("actions_taken"):
            actions_message = f" {len(result['actions_taken'])} action(s) executed."

        return AppChatExecuteResponse(
            success=True,
            answer=result["answer"],
            confidence=result.get("confidence", "medium"),
            data_found=result.get("data_found", True),
            relevant_items=result.get("relevant_items", []),
            resource_urls=result.get("resource_urls", []),
            actions_taken=result.get("actions_taken", []),
            suggested_actions=result.get("suggested_actions", []),
            actionable_insights=result.get("actionable_insights", "none"),
            message=f"Query executed successfully.{actions_message}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing app chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/team-workflows/create", response_model=CreateTeamWorkflowResponse)
async def create_team_workflow(request: CreateTeamWorkflowRequest):
    """
    Create a new team workflow

    Flow:
    1. Parse workflow JSON
    2. Create team workflow in database
    3. Return workflow ID
    """
    try:
        logger.info(
            f"Creating team workflow '{request.workflow_title}' for admin {request.admin_id}"
        )

        # Parse workflow JSON
        try:
            workflow_data = json.loads(request.workflow_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid workflow_json format: {str(e)}"
            )

        # Create team workflow
        workflow_id = await supabase_service.create_team_workflow(
            admin_id=request.admin_id,
            workflow_title=request.workflow_title,
            workflow_json=workflow_data,
            schedule_type=request.schedule_type,
            schedule_config=request.schedule_config,
        )

        if not workflow_id:
            raise HTTPException(
                status_code=500, detail="Failed to create team workflow"
            )

        logger.info(f"Team workflow created: {workflow_id}")

        return CreateTeamWorkflowResponse(
            success=True,
            workflow_id=workflow_id,
            message=f"Team workflow '{request.workflow_title}' created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating team workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/team-workflows/invite", response_model=InviteTeamMemberResponse)
async def invite_team_members(request: InviteTeamMemberRequest):
    """
    Invite team members to join a workflow

    Flow:
    1. Verify workflow exists and user is admin
    2. Create invitations in database
    3. Send invitation emails via Resend
    4. Return invitation status
    """
    try:
        logger.info(
            f"Inviting {len(request.invitee_emails)} members to workflow {request.workflow_id}"
        )

        # Get workflow details
        workflow = await supabase_service.get_team_workflow(request.workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        logger.info(
            f"Workflow found: {workflow['id'], {workflow['admin_id']}, {request.inviter_id}}"
        )

        # Verify user is admin
        if workflow["admin_id"] != request.inviter_id:
            raise HTTPException(
                status_code=403, detail="Only workflow admin can invite members"
            )
        inviter_data = (
            supabase_service.client.table("profiles")
            .select("full_name")
            .eq("id", request.inviter_id)
            .single()
            .execute()
        )

        if not inviter_data or not inviter_data.data:
            inviter_name = "Team Admin"  # Fallback
        else:
            inviter_name = inviter_data.data["full_name"]

        invitations_sent = 0
        failed_invitations = []

        # Create invitation link base URL
        base_url = os.getenv("FRONTEND_URL", "https://blimp.app")

        for invitee_email in request.invitee_emails:
            try:
                # Create invitation in database
                invitation_id = await supabase_service.create_workflow_invitation(
                    workflow_id=request.workflow_id,
                    inviter_id=request.inviter_id,
                    invitee_email=invitee_email,
                )

                if not invitation_id:
                    failed_invitations.append(invitee_email)
                    continue

                # Send invitation email
                invitation_link = f"{base_url}/team-workflows/join/{invitation_id}"

                email_result = await email_service.send_team_workflow_invitation(
                    invitee_email=invitee_email,
                    inviter_name=inviter_name,
                    workflow_title=workflow["workflow_title"],
                    workflow_description=f"Collaborative workflow with {len(workflow.get('members_json', [])) + 1} members",
                    invitation_link=invitation_link,
                )

                if email_result.get("success"):
                    invitations_sent += 1
                    logger.info(f"Invitation sent to {invitee_email}")
                else:
                    failed_invitations.append(invitee_email)
                    logger.error(
                        f"Failed to send invitation to {invitee_email}: {email_result.get('error')}"
                    )

            except Exception as e:
                logger.error(f"Error inviting {invitee_email}: {str(e)}")
                failed_invitations.append(invitee_email)

        return InviteTeamMemberResponse(
            success=invitations_sent > 0,
            invitations_sent=invitations_sent,
            failed_invitations=failed_invitations,
            message=f"Sent {invitations_sent} invitation(s). {len(failed_invitations)} failed.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inviting team members: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/team-workflows/accept-invitation", response_model=AcceptInvitationResponse
)
async def accept_invitation(request: AcceptInvitationRequest):
    """
    Accept a team workflow invitation

    Flow:
    1. Verify invitation exists and is pending
    2. Add user to workflow members
    3. Update invitation status
    4. Return workflow details
    """
    try:
        logger.info(
            f"User {request.user_id} accepting invitation {request.invitation_id}"
        )

        # Get invitation details
        invitation = await supabase_service.get_workflow_invitation(
            request.invitation_id
        )

        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        if invitation["status"] != "pending":
            raise HTTPException(
                status_code=400, detail=f"Invitation already {invitation['status']}"
            )

        # Add user to workflow
        success = await supabase_service.add_team_member(
            workflow_id=invitation["workflow_id"], user_id=request.user_id
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to add user to workflow"
            )

        # Update invitation status
        await supabase_service.update_invitation_status(
            invitation_id=request.invitation_id,
            status="accepted",
            invitee_id=request.user_id,
        )

        # Get workflow details
        workflow = await supabase_service.get_team_workflow(invitation["workflow_id"])

        logger.info(
            f"User {request.user_id} joined workflow {invitation['workflow_id']}"
        )

        return AcceptInvitationResponse(
            success=True,
            workflow_id=invitation["workflow_id"],
            workflow_title=workflow["workflow_title"] if workflow else "Team Workflow",
            message="Successfully joined team workflow",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting invitation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/team-workflows/{workflow_id}", response_model=TeamWorkflowResponse)
async def get_team_workflow(workflow_id: str, user_id: str):
    """Get team workflow details"""
    try:
        workflow = await supabase_service.get_team_workflow(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Verify user has access (is admin or member)
        is_admin = workflow["admin_id"] == user_id
        is_member = any(
            member.get("user_id") == user_id
            for member in workflow.get("members_json", [])
        )

        if not (is_admin or is_member):
            raise HTTPException(status_code=403, detail="Access denied")

        return TeamWorkflowResponse(
            success=True, workflow=workflow, message="Workflow retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/team-workflows/user/{user_id}")
async def get_user_team_workflows(user_id: str):
    """Get all team workflows for a user"""
    try:
        workflows = await supabase_service.get_user_team_workflows(user_id)

        return {"success": True, "workflows": workflows, "count": len(workflows)}

    except Exception as e:
        logger.error(f"Error getting user team workflows: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/team-workflows/execute", response_model=ExecuteTeamWorkflowResponse)
async def execute_team_workflow(request: ExecuteTeamWorkflowRequest):
    """
    Execute a team workflow

    Flow:
    1. Verify user has access to workflow
    2. Get workflow details and parse steps
    3. Execute workflow using orchestrator
    4. Return execution results
    """
    try:
        logger.info(
            f"Executing team workflow {request.workflow_id} for user {request.user_id}"
        )

        # Get workflow details
        workflow = await supabase_service.get_team_workflow(request.workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Verify user has access
        is_admin = workflow["admin_id"] == request.user_id
        is_member = any(
            member.get("user_id") == request.user_id
            for member in workflow.get("members_json", [])
        )

        if not (is_admin or is_member):
            raise HTTPException(status_code=403, detail="Access denied")

        # Parse workflow JSON
        workflow_data = workflow["workflow_json"]
        steps = workflow_data.get("steps", [])

        if not steps:
            raise HTTPException(status_code=400, detail="No steps found in workflow")

        # Extract app types
        app_types = []
        for step in steps:
            app_type = step.get("app_type", "")
            if app_type and app_type.lower() != "trigger":
                app_types.append(app_type)

        # Determine workflow type
        workflow_type = None
        app_types_lower = [app.lower() for app in app_types]

        if "gmail" in app_types_lower and "google calendar" in app_types_lower:
            workflow_type = "gmail_to_calendar"
        elif "gmail" in app_types_lower and "google drive" in app_types_lower:
            workflow_type = "gmail_to_gdrive"
        elif "notion" in app_types_lower and "slack" in app_types_lower:
            workflow_type = "notion_to_slack"
        elif "notion" in app_types_lower and "gmail" in app_types_lower:
            workflow_type = "notion_to_gmail"
        elif "notion" in app_types_lower and "discord" in app_types_lower:
            workflow_type = "notion_to_discord"
        elif "google calendar" in app_types_lower and "slack" in app_types_lower:
            workflow_type = "gcalendar_to_slack"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported app combination: {', '.join(app_types)}",
            )

        # Get user credentials
        credentials = {}
        for app in app_types:
            app_creds = await supabase_service.get_and_refresh_credentials(
                user_id=request.user_id, app_name=app
            )
            if not app_creds:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing credentials for {app}. Please connect the app.",
                )
            credentials[app.lower().replace(" ", "_")] = app_creds

        # Generate execution ID
        execution_id = str(uuid.uuid4())

        # Create workflow object for orchestrator
        workflow_obj = {
            "id": request.workflow_id,
            "name": workflow["workflow_title"],
            "description": f"Team workflow: {workflow['workflow_title']}",
            "type": workflow_type,
            "required_apps": app_types,
            "steps": steps,
        }
        if len(app_types) >= 3:
            logger.info(
                f"Using multi_app_orchestrator for multi-app team workflow ({len(app_types)} apps)"
            )
            result = await multi_app_orchestrator.execute_multi_app_workflow(
                workflow=workflow_obj,
                credentials=credentials,
                parameters=request.parameters or {},
                user_id=request.user_id,
            )
        else:
            logger.info(
                f"Using team_orchestrator for team workflow ({len(app_types)} apps)"
            )
            result = await team_orchestrator.execute_workflow(
                workflow=workflow_obj,
                credentials=credentials,
                parameters=request.parameters or {},
                user_id=request.user_id,
            )

        status = "completed" if result.get("success") else "failed"

        logger.info(f"Team workflow execution {execution_id} {status}")

        return ExecuteTeamWorkflowResponse(
            success=result.get("success", False),
            execution_id=execution_id,
            status=status,
            result=result,
            message=(
                f"Team workflow executed successfully"
                if result.get("success")
                else f"Team workflow execution failed: {result.get('error')}"
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing team workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
