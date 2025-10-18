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

from services.gemini_service import GeminiService
from services.supabase_service import SupabaseService
from orchestrator import WorkflowOrchestrator

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
supabase_service = SupabaseService()
gemini_service = GeminiService()
orchestrator = WorkflowOrchestrator(supabase_service)


# Request/Response Models
class ProcessWorkflowRequest(BaseModel):
    user_id: str
    prompt: str
    context: Optional[Dict[str, Any]] = None


class ProcessWorkflowResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    workflow_description: str
    required_apps: List[str]
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
        
        # If new workflow, save it to database
        if is_new:
            workflow_id = str(uuid.uuid4())
            await supabase_service.save_user_workflow(
                user_id=request.user_id,
                workflow_id=workflow_id,
                name=workflow_data["name"],
                description=workflow_data["description"],
                prompt=request.prompt,
                required_apps=workflow_data["required_apps"],
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
            required_apps=workflow_data["required_apps"],
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
        
        missing_apps = [app for app in required_apps if app.lower() not in [a.lower() for a in connected_apps]]
        if missing_apps:
            raise HTTPException(
                status_code=400,
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
