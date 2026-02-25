from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from typing import List, Optional
from datetime import datetime, timedelta
from database import (
    tasks_collection, work_collection, 
    meeting_collection, routine_collection,
    personal_collection, plans_collection
)
from models import TaskCreate, TaskResponse, TaskUpdate
from routes.users import get_current_user
from routes.google_auth import get_google_calendar_service

router = APIRouter(prefix="/tasks", tags=["tasks"])

def get_collection_for_category(category: str):
    """Router for segmented collections - Case Insensitive"""
    if not category:
        return tasks_collection

    cat_lower = category.lower()
    mapping = {
        "work": work_collection,
        "meeting": meeting_collection,
        "routine": routine_collection,
        "task": tasks_collection,
        "personal": personal_collection,
        "personal space": personal_collection,
        "plan": plans_collection
    }
    return mapping.get(cat_lower, tasks_collection)

@router.post("/", response_model=TaskResponse)
async def create_task(task: TaskCreate, current_user: dict = Depends(get_current_user)):
    try:
        task_dict = task.dict()
        task_dict["user_id"] = str(current_user["_id"])
        
        # --- Google Calendar Sync ---
        user_id = str(current_user["_id"])
        service = await get_google_calendar_service(user_id)
        
        if service and task.date and task.start_time:
            # We only sync tasks that have at least a date and start_time
            # Construct ISO datetimes
            start_dt_str = f"{task.date}T{task.start_time}:00"
            
            end_date = task.end_date or task.date
            end_time = task.end_time or "23:59:00" # default to end of day if no end time
            
            # If no end time at all, maybe we just add 1 hour
            if not task.end_time:
                # Basic assumption 1 hour
                try:
                    dt = datetime.strptime(start_dt_str, "%Y-%m-%dT%H:%M:%S")
                    dt_end = dt + timedelta(hours=1)
                    end_dt_str = dt_end.strftime("%Y-%m-%dT%H:%M:%S")
                except:
                    end_dt_str = f"{end_date}T{end_time}"
            else:
                end_dt_str = f"{end_date}T{end_time}:00"

            event_body = {
                'summary': task.title,
                'description': task.description or task.notes or '',
                'start': {
                    'dateTime': start_dt_str,
                    'timeZone': 'Asia/Kolkata', # Defaulting to India timezone or fetch from user setting
                },
                'end': {
                    'dateTime': end_dt_str,
                    'timeZone': 'Asia/Kolkata',
                },
            }
            
            try:
                created_event = service.events().insert(calendarId='primary', body=event_body).execute()
                task_dict["google_event_id"] = created_event.get('id')
            except Exception as e:
                print(f"Failed to sync task to Google Calendar: {str(e)}")
        # --- End Google Calendar Sync ---

        # Determine target collection
        coll = get_collection_for_category(task.category)
        
        result = await coll.insert_one(task_dict)
        task_dict["id"] = str(result.inserted_id)
        return task_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    category: Optional[str] = None,
    date: Optional[str] = None, 
    status: Optional[str] = None, 
    period: Optional[str] = None, # 'today', 'weekly'
    current_user: dict = Depends(get_current_user)
):
    user_query = {"user_id": str(current_user["_id"])}
    
    # Filter by date/period
    date_query = {}
    if period == "today":
        date_query["date"] = datetime.now().strftime("%Y-%m-%d")
    elif period == "weekly":
        today = datetime.now()
        next_week = today + timedelta(days=7)
        date_query["date"] = {
            "$gte": today.strftime("%Y-%m-%d"),
            "$lte": next_week.strftime("%Y-%m-%d")
        }
    elif date:
        date_query["date"] = date
        
    status_query = {"status": status} if status else {}
    
    final_query = {**user_query, **date_query, **status_query}

    # If a specific category is requested, just search that collection
    if category:
        coll = get_collection_for_category(category)
        cursor = coll.find(final_query)
        tasks = []
        async for task in cursor:
            task["id"] = str(task["_id"])
            tasks.append(task)
        return tasks
    
    # Otherwise, aggregate from all (for "All Activities" view)
    all_tasks = []
    collections = [tasks_collection, work_collection, meeting_collection, routine_collection, personal_collection, plans_collection]
    for coll in collections:
        cursor = coll.find(final_query)
        async for task in cursor:
            task["id"] = str(task["_id"])
            all_tasks.append(task)
    
    return all_tasks

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, task_update: TaskUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in task_update.dict().items() if v is not None}
    user_id = str(current_user["_id"])
    
    # Store old task to get google_event_id if it exists
    old_task = None

    # Try the most likely one (category in update) or check all.
    target_coll = None
    collections = [tasks_collection, work_collection, meeting_collection, routine_collection, personal_collection, plans_collection]
    
    if task_update.category:
        target_coll = get_collection_for_category(task_update.category)
        old_task = await target_coll.find_one({"_id": ObjectId(task_id), "user_id": user_id})
        if old_task:
            await target_coll.update_one({"_id": ObjectId(task_id)}, {"$set": update_data})
            updated_task = await target_coll.find_one({"_id": ObjectId(task_id)})
            
    if not old_task:
        for coll in collections:
            old_task = await coll.find_one({"_id": ObjectId(task_id), "user_id": user_id})
            if old_task:
                await coll.update_one({"_id": ObjectId(task_id)}, {"$set": update_data})
                updated_task = await coll.find_one({"_id": ObjectId(task_id)})
                break
                
    if not old_task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # --- Google Calendar Sync ---
    google_event_id = old_task.get("google_event_id")
    if google_event_id:
        service = await get_google_calendar_service(user_id)
        if service:
            # Reconstruct the fields that might have changed
            event_patch = {}
            if "title" in update_data:
                event_patch["summary"] = update_data["title"]
            if "description" in update_data or "notes" in update_data:
                event_patch["description"] = update_data.get("description", old_task.get("description")) or update_data.get("notes", old_task.get("notes"))
                
            # If dates change, we need start and end dicts completely
            date_changed = any(k in update_data for k in ["date", "end_date", "start_time", "end_time"])
            if date_changed:
                new_date = update_data.get("date", old_task.get("date"))
                new_start_time = update_data.get("start_time", old_task.get("start_time"))
                new_end_date = update_data.get("end_date", old_task.get("end_date")) or new_date
                new_end_time = update_data.get("end_time", old_task.get("end_time"))
                
                if new_date and new_start_time:
                    start_dt_str = f"{new_date}T{new_start_time}:00"
                    
                    if not new_end_time:
                        try:
                            dt = datetime.strptime(start_dt_str, "%Y-%m-%dT%H:%M:%S")
                            dt_end = dt + timedelta(hours=1)
                            end_dt_str = dt_end.strftime("%Y-%m-%dT%H:%M:%S")
                        except:
                            end_dt_str = f"{new_end_date}T23:59:00"
                    else:
                        end_dt_str = f"{new_end_date}T{new_end_time}:00"
                        
                    event_patch["start"] = {'dateTime': start_dt_str, 'timeZone': 'Asia/Kolkata'}
                    event_patch["end"] = {'dateTime': end_dt_str, 'timeZone': 'Asia/Kolkata'}

            if event_patch:
                try:
                    service.events().patch(calendarId='primary', eventId=google_event_id, body=event_patch).execute()
                except Exception as e:
                    print(f"Failed to patch Google Calendar event {google_event_id}: {str(e)}")
    # --- End Google Calendar Sync ---

    updated_task["id"] = str(updated_task["_id"])
    return updated_task

@router.delete("/{task_id}")
async def delete_task(task_id: str, current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    collections = [tasks_collection, work_collection, meeting_collection, routine_collection, personal_collection, plans_collection]
    
    task_to_delete = None
    target_coll = None
    
    for coll in collections:
        task_to_delete = await coll.find_one({"_id": ObjectId(task_id), "user_id": user_id})
        if task_to_delete:
            target_coll = coll
            break
            
    if not task_to_delete:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # Delete from DB
    await target_coll.delete_one({"_id": ObjectId(task_id)})
    
    # --- Google Calendar Sync ---
    google_event_id = task_to_delete.get("google_event_id")
    if google_event_id:
        service = await get_google_calendar_service(user_id)
        if service:
            try:
                service.events().delete(calendarId='primary', eventId=google_event_id).execute()
            except Exception as e:
                print(f"Failed to delete Google Calendar event {google_event_id}: {str(e)}")
    # --- End Google Calendar Sync ---

    return {"message": "Task deleted"}

