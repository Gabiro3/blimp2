# Blimp MCP Server - Setup & Usage Guide

uvicorn main:app --host 0.0.0.0 --port 8000

## Overview

Blimp MCP Server is a backend API for AI-powered workflow automation. It enables users to automate tasks across multiple apps like Gmail, Google Calendar, Notion, Slack, and Discord.

## Architecture

\`\`\`
┌─────────────┐
│ Client │
│ (Frontend) │
└──────┬──────┘
│
│ HTTP Requests
│
┌──────▼──────────────────────────────────────┐
│ FastAPI Server (main.py) │
│ ┌────────────────────────────────────┐ │
│ │ /api/process-workflow │ │
│ │ /api/execute-workflow │ │
│ │ /api/workflows │ │
│ │ /api/connected-apps │ │
│ └────────────────────────────────────┘ │
└──────┬──────────────┬──────────────┬────────┘
│ │ │
│ │ │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼────────┐
│ Gemini │ │ Supabase │ │ Orchestrator│
│ Service │ │ Service │ │ │
└─────────────┘ └────────────┘ └──────┬──────┘
│
│
┌──────────────▼──────────────┐
│ Utility Functions │
│ ┌──────────────────────┐ │
│ │ gmail_calendar_utils │ │
│ │ gmail_gdrive_utils │ │
│ │ ...more utils... │ │
│ └──────────────────────┘ │
└─────────────────────────────┘
\`\`\`

## Prerequisites

- Python 3.11+
- Docker (optional, for containerized deployment)
- Supabase account and project
- Google Gemini API key
- OAuth credentials for apps (Gmail, Google Calendar, etc.)

## Installation

### 1. Clone the Repository

\`\`\`bash
git clone <your-repo-url>
cd blimp-mcp-server
\`\`\`

### 2. Create Virtual Environment

\`\`\`bash
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate
\`\`\`

### 3. Install Dependencies

\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 4. Configure Environment Variables

Copy the example environment file:

\`\`\`bash
cp .env.example .env
\`\`\`

Edit `.env` and add your credentials:

\`\`\`env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
GEMINI_API_KEY=your_gemini_api_key
\`\`\`

### 5. Set Up Supabase Database

Create the following tables in your Supabase project:

#### `workflow_templates` Table

\`\`\`sql
CREATE TABLE workflow_templates (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
name TEXT NOT NULL,
description TEXT,
required_apps TEXT[] NOT NULL,
category TEXT,
webhook_url TEXT,
is_active BOOLEAN DEFAULT true,
created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
\`\`\`

#### `user_workflows` Table

\`\`\`sql
CREATE TABLE user_workflows (
id UUID PRIMARY KEY,
user_id TEXT NOT NULL,
name TEXT NOT NULL,
description TEXT,
prompt TEXT,
required_apps TEXT[] NOT NULL,
category TEXT,
webhook_url TEXT,
is_active BOOLEAN DEFAULT true,
created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
\`\`\`

#### `user_connected_apps` Table

\`\`\`sql
CREATE TABLE user_connected_apps (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
user_id TEXT NOT NULL,
app_name TEXT NOT NULL,
app_type TEXT NOT NULL,
is_active BOOLEAN DEFAULT true,
created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
UNIQUE(user_id, app_type)
);
\`\`\`

#### `user_credentials` Table

\`\`\`sql
CREATE TABLE user_credentials (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
user_id TEXT NOT NULL,
app_name TEXT NOT NULL,
app_type TEXT NOT NULL,
credentials JSONB NOT NULL,
metadata JSONB,
is_active BOOLEAN DEFAULT true,
created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
UNIQUE(user_id, app_type)
);
\`\`\`

#### `workflow_executions` Table

\`\`\`sql
CREATE TABLE workflow_executions (
id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
user_id TEXT NOT NULL,
workflow_id UUID NOT NULL,
execution_id TEXT UNIQUE NOT NULL,
status TEXT NOT NULL,
parameters JSONB,
result JSONB,
created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
\`\`\`

## Running the Server

### Development Mode

\`\`\`bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
\`\`\`

### Production Mode

\`\`\`bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
\`\`\`

### Using Docker

Build the image:

\`\`\`bash
docker build -t blimp-mcp-server .
\`\`\`

Run the container:

\`\`\`bash
docker run -d \
 --name blimp-server \
 -p 8000:8000 \
 --env-file .env \
 blimp-mcp-server
\`\`\`

## API Endpoints

### 1. Process Workflow

**Endpoint:** `POST /api/process-workflow`

**Description:** Analyze a user's workflow request and determine required apps.

**Request Body:**

\`\`\`json
{
"user_id": "user123",
"prompt": "Send my Gmail emails to Google Calendar",
"context": {}
}
\`\`\`

**Response:**

\`\`\`json
{
"workflow_id": "uuid",
"workflow_name": "Gmail to Calendar Sync",
"workflow_description": "Automatically create calendar events from your emails",
"required_apps": ["gmail", "gcalendar"],
"is_new_workflow": false,
"message": "Workflow processed successfully. Please connect the required apps to execute."
}
\`\`\`

### 2. Execute Workflow

**Endpoint:** `POST /api/execute-workflow`

**Description:** Execute a workflow after user has connected required apps.

**Request Body:**

\`\`\`json
{
"user_id": "user123",
"workflow_id": "uuid",
"parameters": {
"max_emails": 10,
"query": "is:unread"
}
}
\`\`\`

**Response:**

\`\`\`json
{
"execution_id": "exec-uuid",
"status": "completed",
"result": {
"success": true,
"events_created": 5,
"message": "Successfully created 5 calendar events from 10 emails"
},
"message": "Workflow executed successfully"
}
\`\`\`

### 3. List Workflows

**Endpoint:** `GET /api/workflows?user_id=user123`

**Description:** Get all available workflow templates.

**Response:**

\`\`\`json
{
"success": true,
"workflows": [
{
"id": "uuid",
"name": "Gmail to Calendar",
"description": "Create calendar events from emails",
"required_apps": ["gmail", "gcalendar"],
"category": "productivity"
}
],
"count": 1
}
\`\`\`

### 4. Get Connected Apps

**Endpoint:** `GET /api/connected-apps?user_id=user123`

**Description:** Get user's connected apps.

**Response:**

\`\`\`json
{
"success": true,
"connected_apps": ["gmail", "gcalendar"],
"count": 2
}
\`\`\`

## Adding New Utility Functions

### Step 1: Create Utility Module

Create a new file in `utils/` directory:

\`\`\`python

# utils/slack_notion_utils.py

import logging
from typing import Dict, Any
from slack_helpers import SlackHelpers
from notion_helpers import NotionHelpers

logger = logging.getLogger(**name**)

class SlackNotionUtils:
"""Utility functions for Slack to Notion automation"""

    def __init__(self, credentials: Dict[str, Any]):
        self.slack_token = credentials.get("slack", {}).get("credentials", {}).get("access_token")
        self.notion_token = credentials.get("notion", {}).get("credentials", {}).get("access_token")

    async def slack_messages_to_notion(self, channel: str, page_id: str) -> Dict[str, Any]:
        """Send Slack messages to Notion page"""
        # Implementation here
        pass

\`\`\`

### Step 2: Register in Orchestrator

Update `orchestrator.py`:

\`\`\`python
from utils.slack_notion_utils import SlackNotionUtils

class WorkflowOrchestrator:
def **init**(self, supabase_service: SupabaseService):
self.utils_registry = {
"gmail_calendar": GmailCalendarUtils,
"gmail_gdrive": GmailGDriveUtils,
"slack_notion": SlackNotionUtils, # Add new utility
}
\`\`\`

### Step 3: Add Routing Logic

Update `_execute_workflow_logic` method in `orchestrator.py`:

\`\`\`python
async def \_execute_workflow_logic(self, util_instance, workflow, parameters):
workflow_name = workflow.get("name", "").lower()

    if "slack" in workflow_name and "notion" in workflow_name:
        return await util_instance.slack_messages_to_notion(
            channel=parameters.get("channel"),
            page_id=parameters.get("page_id")
        )

\`\`\`

## Workflow Execution Flow

1. **Client sends workflow request** → `/api/process-workflow`
2. **Server fetches workflow templates** from Supabase
3. **Gemini analyzes request** and matches/creates workflow
4. **Server returns required apps** to client
5. **User connects apps** via OAuth (handled by frontend)
6. **Client calls** `/api/execute-workflow`
7. **Orchestrator determines utility functions** to call
8. **Utility functions execute** inter-app operations
9. **Results returned** to client

## Troubleshooting

### Issue: "Supabase client not initialized"

**Solution:** Check that `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set in `.env`

### Issue: "Gemini service not configured"

**Solution:** Verify `GEMINI_API_KEY` is set in `.env`

### Issue: "Missing required app connections"

**Solution:** Ensure user has connected all required apps via OAuth before executing workflow

### Issue: "Failed to fetch emails"

**Solution:** Check that Gmail OAuth token is valid and has required scopes

## Security Considerations

1. **Never commit `.env` file** - Keep credentials secure
2. **Use HTTPS in production** - Encrypt data in transit
3. **Encrypt credentials in database** - Use Supabase encryption features
4. **Implement rate limiting** - Prevent API abuse
5. **Validate user permissions** - Ensure users can only access their own data
6. **Rotate API keys regularly** - Update credentials periodically

## Next Steps

1. Add more utility functions for different app combinations
2. Implement webhook support for real-time workflows
3. Add workflow scheduling capabilities
4. Build monitoring and analytics dashboard
5. Implement error retry mechanisms
6. Add comprehensive logging and alerting

## Support

For issues or questions, please open an issue on GitHub or contact the development team.

## License

[Your License Here]
