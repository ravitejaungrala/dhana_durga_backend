from fastapi import APIRouter, Depends, HTTPException
from models import UserPreferenceUpdate, UserPreferenceResponse
from database import preferences_collection
from routes.users import get_current_user

router = APIRouter()

@router.get("/", response_model=UserPreferenceResponse)
async def get_preferences(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    pref = await preferences_collection.find_one({"user_id": user_id})
    if not pref:
        # Return default if none exists
        return {
            "user_id": user_id,
            "default_focus_duration": 25,
            "theme": "dark",
            "agent_praise_mode": True,
            "learned_context": None
        }
    return pref

@router.put("/", response_model=UserPreferenceResponse)
async def update_preferences(pref_update: UserPreferenceUpdate, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    update_data = {k: v for k, v in pref_update.dict().items() if v is not None}
    
    await preferences_collection.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )
    
    pref = await preferences_collection.find_one({"user_id": user_id})
    return pref
