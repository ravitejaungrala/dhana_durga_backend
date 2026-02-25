from fastapi import APIRouter, Depends
from services.ai_service import process_user_input
from models import AIChatRequest
from routes.users import get_current_user
from datetime import datetime, timedelta
from database import (
    tasks_collection, work_collection, 
    meeting_collection, routine_collection,
    personal_collection, credentials_collection,
    preferences_collection, focus_sessions_collection,
    automations_collection
)
from services.email_service import send_email
from services.whatsapp_service import send_whatsapp_message
from services.greyhr_service import perform_greyhr_action
from routes.credentials import fernet
import urllib.parse

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/chat")
async def chat(request: AIChatRequest, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    past_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    future_date = (datetime.now() + timedelta(days=365 * 2)).strftime("%Y-%m-%d")
    
    all_context_tasks = []
    collections = [tasks_collection, work_collection, meeting_collection, routine_collection, personal_collection]
    
    for coll in collections:
        cursor = coll.find({
            "user_id": user_id,
            "date": {"$gte": past_date, "$lte": future_date}
        })
        async for task in cursor:
            task["id"] = str(task["_id"])
            del task["_id"]
            all_context_tasks.append(task)
            
    # Fetch and decrypt credentials for context
    all_context_credentials = []
    cursor_creds = credentials_collection.find({"user_id": user_id})
    async for cred in cursor_creds:
        cred["id"] = str(cred["_id"])
        del cred["_id"]
        # Decrypt password for AI context
        if "password" in cred and cred["password"]:
            try:
                cred["password"] = fernet.decrypt(cred["password"].encode()).decode()
            except Exception:
                pass
        all_context_credentials.append(cred)
            
    # Fetch preferences for context
    preferences = await preferences_collection.find_one({"user_id": user_id})
    learned_context = preferences.get("learned_context") if preferences else None

    # Fetch focus history for context
    focus_history = []
    cursor_focus = focus_sessions_collection.find({"user_id": user_id}).sort("start_time", -1).limit(10)
    async for sess in cursor_focus:
        sess["id"] = str(sess["_id"])
        del sess["_id"]
        sess["start_time"] = sess["start_time"].isoformat() if isinstance(sess["start_time"], datetime) else sess["start_time"]
        focus_history.append(sess)

    result = await process_user_input(
        request.text, 
        all_context_tasks, 
        all_context_credentials, 
        request.image,
        preferences=preferences,
        learned_context=learned_context,
        focus_history=focus_history
    )
    
    # Process dispatch_schedule if present in actions
    if "actions" in result:
        for action in result["actions"]:
            if action.get("type") == "dispatch_schedule":
                summary = action.get("summary", "Your today's schedule is ready.")
                
                # 1. Send Email
                print(f"DEBUG: Attempting to send schedule email to {current_user['email']}")
                email_success = send_email(current_user["email"], "Today's Schedule Summary - Dhana Durga", summary)
                print(f"DEBUG: Email success status: {email_success}")
                
                # 2. Send Automated WhatsApp (Background)
                print(f"DEBUG: Attempting to send automated WhatsApp message")
                whatsapp_number = "whatsapp:+917013666788" # Direct target as requested
                wa_success = send_whatsapp_message(whatsapp_number, summary)
                print(f"DEBUG: WhatsApp success status: {wa_success}")
                
                # 3. Add a direct WhatsApp link for the frontend to open
                encoded_msg = urllib.parse.quote(summary)
                action["whatsapp_link"] = f"https://wa.me/917013666788?text={encoded_msg}"
                print(f"DEBUG: Generated manual WhatsApp link: {action['whatsapp_link']}")
                
            elif action.get("type") == "dispatch_credentials":
                summary = action.get("summary", "Here are the requested credentials.")
                
                # 1. Send Email
                print(f"DEBUG: Attempting to send credentials email to {current_user['email']}")
                email_success = send_email(current_user["email"], "Your Requested Credentials - Dhana Durga", summary)
                print(f"DEBUG: Credentials Email success status: {email_success}")
                
                # 2. Send Automated WhatsApp (Background)
                print(f"DEBUG: Attempting to send automated credentials WhatsApp message")
                whatsapp_number = "whatsapp:+917013666788" 
                wa_success = send_whatsapp_message(whatsapp_number, summary)
                print(f"DEBUG: Credentials WhatsApp success status: {wa_success}")
                
                # 3. Add a direct WhatsApp link for the frontend
                encoded_msg = urllib.parse.quote(summary)
                action["whatsapp_link"] = f"https://wa.me/917013666788?text={encoded_msg}"
                print(f"DEBUG: Generated credentials manual WhatsApp link: {action['whatsapp_link']}")
                
            elif action.get("type") == "browser_automation":
                grey_hr_action = action.get("action")
                # Expected: greyhr_signin or greyhr_signout
                if grey_hr_action in ["greyhr_signin", "greyhr_signout"]:
                    task_action = "signin" if grey_hr_action == "greyhr_signin" else "signout"
                    print(f"DEBUG: Attempting to perform GreyHR {task_action} automation")
                    status_result = await perform_greyhr_action(user_id, task_action)
                    # We can append this status directly to the model's textual reply
                    result["reply"] += f"\n\n[System Auto-Execution: {status_result['message']}]"
            
            elif action.get("type") == "manage_automation":
                auto_action = action.get("action")
                auto_data = action.get("data", {})
                service = auto_data.get("service")
                
                if auto_action == "schedule":
                    # Save or update automation schedule
                    await automations_collection.update_one(
                        {"user_id": user_id, "service": service},
                        {"$set": {
                            "time": auto_data.get("time"),
                            "days": auto_data.get("days", []),
                            "is_active": True
                        }},
                        upsert=True
                    )
                    result["reply"] += f"\n\n[System: Successfully scheduled {service} automation."
                
                elif auto_action == "skip":
                    # Add skip date
                    skip_date = auto_data.get("skip_date")
                    if skip_date:
                        await automations_collection.update_one(
                            {"user_id": user_id, "service": service},
                            {"$addToSet": {"skip_dates": skip_date}}
                        )
                        result["reply"] += f"\n\n[System: Will skip {service} automation on {skip_date}.]"
                
                elif auto_action == "cancel":
                    # Remove automation
                    await automations_collection.delete_one({"user_id": user_id, "service": service})
                    result["reply"] += f"\n\n[System: Cancelled {service} automation.]"
                
    return result
