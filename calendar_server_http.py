#!/usr/bin/env python3
"""
HTTP version of the Google Calendar MCP server for n8n integration
"""
import os
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import uvicorn

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = os.path.join(SCRIPT_DIR, 'token.json')
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, 'credentials.json')

# FastAPI app
app = FastAPI(title="Google Calendar MCP Server", version="1.0.0")

# Pydantic models for requests
class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

def get_calendar_service():
    """Get authenticated Google Calendar service"""
    creds = None

    # Check for production environment variables first
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if refresh_token and client_id and client_secret:
        # Production mode: use environment variables
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )
    else:
        # Development mode: use local files
        # Load existing token
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError("credentials.json not found. Please add Google OAuth credentials.")

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            # Use port=0 to automatically find an available port
            creds = flow.run_local_server(port=0)

            # Save credentials
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

# API Routes
@app.get("/debug")
async def debug_env():
    """Debug endpoint to check environment variables"""
    return {
        "has_refresh_token": bool(os.environ.get('GOOGLE_REFRESH_TOKEN')),
        "has_client_id": bool(os.environ.get('GOOGLE_CLIENT_ID')),
        "has_client_secret": bool(os.environ.get('GOOGLE_CLIENT_SECRET')),
        "client_id_preview": os.environ.get('GOOGLE_CLIENT_ID', 'NOT_SET')[:20] + "...",
        "refresh_token_preview": os.environ.get('GOOGLE_REFRESH_TOKEN', 'NOT_SET')[:20] + "...",
    }

@app.get("/tools")
async def list_tools():
    """List available tools"""
    return {
        "tools": [
            {
                "name": "list_events",
                "description": "List upcoming calendar events",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {
                            "type": "integer",
                            "description": "Number of days ahead to look for events",
                            "default": 7
                        }
                    }
                }
            },
            {
                "name": "create_event",
                "description": "Create a calendar event",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Event title/summary"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Start time in format: 2024-12-25T10:00:00 or 2024-12-25T10:00:00-07:00"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Event duration in minutes",
                            "default": 60
                        }
                    },
                    "required": ["summary", "start_time"]
                }
            }
        ]
    }

@app.post("/tools/call")
async def call_tool(request: ToolCallRequest):
    """Handle tool calls"""
    try:
        if request.name == "list_events":
            days_ahead = request.arguments.get("days_ahead", 7)
            result = await list_events(days_ahead)
            return {"content": [{"type": "text", "text": result}]}
        elif request.name == "create_event":
            summary = request.arguments["summary"]
            start_time = request.arguments["start_time"]
            duration_minutes = request.arguments.get("duration_minutes", 60)
            result = await create_event(summary, start_time, duration_minutes)
            return {"content": [{"type": "text", "text": result}]}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {request.name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def list_events(days_ahead: int = 7) -> str:
    """List upcoming calendar events"""
    service = get_calendar_service()

    now = datetime.utcnow().isoformat() + 'Z'
    later = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        timeMax=later,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        return 'No upcoming events found.'

    result = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        result.append(f"{start}: {event['summary']}")

    return '\n'.join(result)

async def create_event(summary: str, start_time: str, duration_minutes: int = 60) -> str:
    """Create a calendar event. start_time format: 2024-12-25T10:00:00 or 2024-12-25T10:00:00-07:00"""
    service = get_calendar_service()

    # Parse the start time, preserving timezone if provided
    start_dt = datetime.fromisoformat(start_time)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    # Determine timezone - use Pacific if no timezone specified
    if start_dt.tzinfo is None:
        # No timezone specified, assume Pacific time
        event = {
            'summary': summary,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/Los_Angeles'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/Los_Angeles'},
        }
    else:
        # Timezone was specified in the input, use it
        event = {
            'summary': summary,
            'start': {'dateTime': start_dt.isoformat()},
            'end': {'dateTime': end_dt.isoformat()},
        }

    created = service.events().insert(calendarId='primary', body=event).execute()
    return f"Event created: {created.get('htmlLink')}"

def main():
    """Run the HTTP server"""
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    main()
