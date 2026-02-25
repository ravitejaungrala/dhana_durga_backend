from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from models import FocusSessionCreate, FocusSessionResponse
from database import focus_sessions_collection
from routes.users import get_current_user
from bson import ObjectId
import json

router = APIRouter()

@router.post("/", response_model=FocusSessionResponse)
async def create_focus_session(session: FocusSessionCreate, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    session_dict = session.dict()
    session_dict["user_id"] = user_id
    
    result = await focus_sessions_collection.insert_one(session_dict)
    session_dict["id"] = str(result.inserted_id)
    return session_dict

@router.get("/", response_model=List[FocusSessionResponse])
async def get_focus_sessions(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    sessions = []
    async for session in focus_sessions_collection.find({"user_id": user_id}):
        session["id"] = str(session["_id"])
        sessions.append(session)
    return sessions
