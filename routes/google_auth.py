import os
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import urllib.parse
from database import google_credentials_collection
from routes.users import get_current_user

router = APIRouter(prefix="/auth/google", tags=["google_auth"])

# Using the absolute path provided for the client secret JSON
CLIENT_SECRETS_FILE = r"c:\Users\jaswa\Neuzenai\Daily-task\backend\credentails\client_secret_696167554632-vjbni25vlrsf3segjtu4v4270aoh4quu.apps.googleusercontent.com.json"

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]

def get_redirect_uri(request: Request):
    # Depending on where the frontend is hosted, we dynamically match it
    origin = request.headers.get("origin") or request.headers.get("referer", "http://localhost:5173").rstrip("/")
    if "localhost" in origin:
        return "http://localhost:5173/auth/google/callback"
    elif "daily-task-frontend-mu.vercel.app" in origin:
        return "https://daily-task-frontend-mu.vercel.app/auth/google/callback"
    else:
        return f"{origin}/auth/google/callback"

@router.get("/login")
async def google_login(request: Request, current_user: dict = Depends(get_current_user)):
    """Generate the OAuth2 redirect URL for Google Calendar."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(status_code=500, detail="Google client secrets file not found on server.")

    redirect_uri = get_redirect_uri(request)

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    # We pass the user id closely bound to the state, so we know who logged in upon callback.
    # We format state as user_id to easily sync
    state = str(current_user["_id"])
    
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state
    )

    return {"auth_url": auth_url}

@router.post("/callback")
async def google_callback(request: Request, code: str, state: str):
    """Callback to receive the authorization code and save credentials for the specific user."""
    redirect_uri = get_redirect_uri(request)
    
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        user_id = state # from earlier login step
        
        creds_dict = {
            "user_id": user_id,
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }
        
        # Save or update in database
        await google_credentials_collection.update_one(
            {"user_id": user_id},
            {"$set": creds_dict},
            upsert=True
        )
        
        return {"message": "Google Calendar connected successfully!"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {str(e)}")

@router.get("/status")
async def google_auth_status(current_user: dict = Depends(get_current_user)):
    """Check if the user has connected their Google Calendar."""
    user_id = str(current_user["_id"])
    creds = await google_credentials_collection.find_one({"user_id": user_id})
    return {"connected": creds is not None}

@router.post("/disconnect")
async def google_auth_disconnect(current_user: dict = Depends(get_current_user)):
    """Disconnect the user's Google Calendar."""
    user_id = str(current_user["_id"])
    result = await google_credentials_collection.delete_one({"user_id": user_id})
    if result.deleted_count > 0:
        return {"message": "Google Calendar disconnected successfully"}
    return {"message": "Google Calendar was not connected"}

# --- Helpher Function for Other Routes (e.g., tasks.py) ---
async def get_google_calendar_service(user_id: str):
    """
    Retrieves the user's stored Google credentials and builds the Calendar API service.
    Returns None if the user hasn't authenticated.
    """
    creds_data = await google_credentials_collection.find_one({"user_id": user_id})
    if not creds_data:
        return None
        
    creds = Credentials(
        token=creds_data.get("access_token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=creds_data.get("scopes")
    )
    
    # Simple check for simple expiry mechanism; note that googleapiclient handles automatic refreshing
    # internally if refresh_token is present when calling APIs
    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Failed to build Google Calendar service for user {user_id}: {str(e)}")
        return None
