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

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Blimp MCP Server",
    description="AI-powered workflow automation backend",
    version="1.0.0"
)

# CORS middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]
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


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Blimp MCP Server",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "services": {
            "supabase": supabase_service.client is not None,
            "gemini": gemini_service.is_configured(),
            "orchestrator": True
        },
        "timestamp": datetime.utcnow().isoformat()
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
            context=request.context
        )
        
        if not gemini_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Gemini processing failed: {gemini_result.get('error')}"
            )
        
        workflow_data = gemini_result["workflow"]
        is_new = gemini_result["is_new_workflow"]
        required_apps_list = workflow_data["required_apps"]
        logger.info(f"Required apps: {required_apps_list}")
        
        required_apps_with_status = [
    {
        "app_name": app,
        "is_connected": app in connected_apps
    }
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
                category=workflow_data.get("category", "custom")
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
            message="Workflow processed successfully. Please connect the required apps to execute."
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
        logger.info(f"Executing workflow {request.workflow_id} for user {request.user_id}")
        
        # Get workflow details
        workflow = await supabase_service.get_workflow(
            workflow_id=request.workflow_id,
            user_id=request.user_id
        )
        
        if not workflow:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {request.workflow_id} not found"
            )
        
        # Verify user has connected required apps
        connected_apps = await supabase_service.get_user_connected_apps(request.user_id)
        required_apps = workflow.get("required_apps", [])
        
        missing_apps = [app for app in required_apps if app not in [a for a in connected_apps]]
        if missing_apps:
            raise HTTPException(
                status_code=404,
                detail=f"Missing required app connections: {', '.join(missing_apps)}"
            )
        
        # Get user credentials for workflow
        credentials = await supabase_service.get_user_workflow_credentials(
            user_id=request.user_id,
            workflow_id=request.workflow_id
        )
        
        if not credentials:
            raise HTTPException(
                status_code=400,
                detail="Unable to retrieve app credentials. Please reconnect your apps."
            )
        
        # Generate execution ID
        execution_id = str(uuid.uuid4())
        
        # Save execution record
        await supabase_service.save_workflow_execution(
            user_id=request.user_id,
            workflow_id=request.workflow_id,
            execution_id=execution_id,
            status="running",
            parameters=request.parameters
        )
        
        # Execute workflow using orchestrator
        result = await orchestrator.execute_workflow(
            workflow=workflow,
            credentials=credentials,
            parameters=request.parameters or {}
        )
        
        # Update execution status
        status = "completed" if result.get("success") else "failed"
        await supabase_service.update_workflow_status(
            execution_id=execution_id,
            status=status,
            result=result
        )
        
        logger.info(f"Workflow execution {execution_id} {status}")
        
        return ExecuteWorkflowResponse(
            execution_id=execution_id,
            status=status,
            result=result,
            message=f"Workflow executed successfully" if result.get("success") else f"Workflow execution failed: {result.get('error')}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing workflow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/api/execute-custom-workflow", response_model=ExecuteCustomWorkflowResponse)
async def execute_custom_workflow(request: ExecuteCustomWorkflowRequest):
    logger.info("Request made %s", request)
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
        logger.info(f"Executing custom workflow '{request.workflow_title}' for user {request.user_id}")
        
        # Parse workflow_json
        try:
            workflow_data = json.loads(request.workflow_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid workflow_json format: {str(e)}"
            )
        
        # Extract steps from workflow data
        steps = workflow_data.get("steps", [])
        if not steps:
            raise HTTPException(
                status_code=400,
                detail="No steps found in workflow_json"
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
                detail="Workflow must have at least 2 apps (excluding Trigger)"
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
                detail=f"Unsupported app combination: {', '.join(app_types)}"
            )
        
        logger.info(f"Determined workflow type: {workflow_type}")
        
        # Verify user has connected required apps
        connected_apps = await supabase_service.get_user_connected_apps(request.user_id)
        connected_apps_lower = [app.lower() for app in connected_apps]
        
        missing_apps = [app for app in app_types if app.lower() not in connected_apps_lower]
        if missing_apps:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required app connections: {', '.join(missing_apps)}"
            )
        
        # Get user credentials for the required apps
        # Get user credentials for workflow
        credentials = await supabase_service.get_user_workflow_credentials(
            user_id=request.user_id,
            workflow_id=request.workflow_id)
        
        # Generate execution ID
        execution_id = str(uuid.uuid4())
        
        # Create workflow object for orchestrator
        workflow = {
            "id": execution_id,
            "name": request.workflow_title,
            "description": f"Custom workflow: {request.workflow_title}",
            "type": workflow_type,
            "required_apps": app_types,
            "steps": steps
        }
        
        # Execute workflow using orchestrator
        result = await orchestrator.execute_workflow(
            workflow=workflow,
            credentials=credentials,
            parameters=request.parameters or {}
        )
        
        status = "completed" if result.get("success") else "failed"
        
        logger.info(f"Custom workflow execution {execution_id} {status}")
        
        return ExecuteCustomWorkflowResponse(
            execution_id=execution_id,
            status=status,
            result=result,
            workflow_type=workflow_type,
            apps_used=app_types,
            message=f"Custom workflow executed successfully" if result.get("success") else f"Custom workflow execution failed: {result.get('error')}"
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
        return {
            "success": True,
            "workflows": templates,
            "count": len(templates)
        }
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
            raise HTTPException(
                status_code=404,
                detail="Access token is required"
            )
        
        # Step 2: Store credentials in Supabase
        logger.info(f"Storing credentials for {request.app_name}")
        credential_id = await supabase_service.store_user_credentials(
            user_id=request.user_id,
            app_name=request.app_name,
            app_type=request.app_type,
            credentials=request.credentials.dict(),
            metadata=request.metadata.dict()
        )
        
        if not credential_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to store credentials"
            )
        
        # Step 3: Create/update n8n credentials for this user
        logger.info(f"Creating n8n credentials for user {request.user_id}")
        n8n_credential_id = await supabase_service.store_user_credentials(
            user_id=request.user_id,
            app_name=request.app_name,  # You can change this as needed
            app_type=request.app_type,
            credentials=request.credentials.dict(),
            metadata={}  # Adjust this based on what metadata needs to be stored
        )
        
        if not n8n_credential_id:
            logger.warning(f"Failed to create n8n credential, but Supabase storage succeeded")
        
        logger.info(f"App connected successfully: {request.app_name}")
        
        return ConnectAppResponse(
            success=True,
            message="App connected successfully",
            credential_id=credential_id,
            app_name=request.app_name
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
            error=str(e)
        )


@app.get("/api/connected-apps")
async def get_connected_apps(user_id: str):
    """Get user's connected apps"""
    try:
        apps = await supabase_service.get_user_connected_apps(user_id)
        return {
            "success": True,
            "connected_apps": apps,
            "count": len(apps)
        }
    except Exception as e:
        logger.error(f"Error getting connected apps: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
