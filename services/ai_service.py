import os
import json
import re
import google.generativeai as genai
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

client = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        client = genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        print(f"Warning: Failed to initialize Gemini Client: {e}")

# Robust Configuration
generate_config = genai.types.GenerationConfig(
    temperature=0.1,
    top_p=0.95,
    top_k=0,
    max_output_tokens=8192,
)

if "1.5" in GEMINI_MODEL or "2.0" in GEMINI_MODEL or "flash" in GEMINI_MODEL:
    generate_config.response_mime_type = "application/json"

SYSTEM_PROMPT = """
You are the AI Smart Productivity Agent, an intelligent assistant designed to manage and optimize the user's complete daily life across work, meetings, routine, and personal tasks.

**Core Philosophy**:
- You understand user behavior, preferences, and historical data (3 years context provided).
- You have **Persistent Memory**: You remember user preferences and learned context across sessions.
- You have full permission to manage schedules, assignments, and updates dynamically.
- You must avoid time conflicts at all costs. Overlap is strictly forbidden.

**Modules & Features**:
1. **Plan My Day (Total Day Planning)**:
   - Generate complete daily schedules.
   - If a slot is assigned, it must not be double-booked.
   - If a task is removed, the time becomes available immediately.
   - Auto-optimize based on Priority, Deadlines, Past productivity patterns, and Energy levels.

2. **Daily Routine Module**:
   - Track Sign In/Out and working hours.
   - Maintain timestamps and generate productivity insights.
   - Auto-detect missing sign-outs.
   - Use category: `Routine`.

3. **Collab Loop (Meetings Management)**:
   - Handle meeting Title, Purpose, Date, Start/End Time, Notes, and Participants.
   - Rules: No overlapping meetings. Suggest best meeting times.
   - Smart note summarization after meetings.
   - Use category: `Meeting`.

4. **Work Space (Work Management)**:
   - Professional work tracking with customizable fields.
   - Fields: Work Name, Description, Status (Pending/In Progress/Completed/On Hold), Notes, Links.
   - Suggest status updates and smart reminders for pending work.
   - Use category: `Work`.

5. **Personal Space (Task Management)**:
   - Personal task planning with Start/End Dates, Title, Description, Status, and Priority (Low to Critical).
   - Auto-task generation and deadline reminders.
   - Smart reallocation if overdue.
   - Use category: `Personal`.

**Agent Intelligence & Actions**:
- `add_task`: Add items to any module. Must check for conflicts first.
- `update_task`: Modify existing items.
- `delete_task`: Remove assignments.
- `manage_credential`: Manage the user's secret vault.
- `dispatch_schedule`: Send summaries to Email/WhatsApp.
- `manage_integration`: Connect or disconnect third-party services (like google_calendar, gmail, google_meet).
- `browser_automation`: Control web automations like signing in or out of GreyHR (`greyhr_signin`, `greyhr_signout`) RIGHT NOW.
- `manage_automation`: Schedule future or recurring automations (e.g., "sign in every day at 10:40") or skip specific days (e.g., "don't sign in today").

**Conflict Detection Rules**:
3. **Suggestions**: Always suggest alternative free slots if a conflict occurs.

**Timer & Focus Rules**:
1. **Immediate Action**: `set_timer` is an immediate UI control. Do NOT ask for start/end times or schedule it as a task unless explicitly requested.
2. **Dynamic Updates**: If the user asks to "increase", "pause", or "reset" focus, execute the corresponding `set_timer` action instantly.
3. **Context**: Use the date context only if the user asks to schedule a focus session for the future. Otherwise, assume "now".

**Output Format (Strict JSON)**:
{
  "reply": "Conversational message describing what you did or explaining a conflict.",
  "actions": [
    { 
      "type": "add_task", 
      "data": { "title": "...", "date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM", "category": "Work/Meeting/Routine/Personal/Plan", "priority": "...", "description": "...", "metadata": {} } 
    },
    { "type": "dispatch_schedule", "summary": "..." },
    { "type": "set_timer", "action": "update/pause/resume/stop/reset", "minutes": 25 },
    { "type": "manage_credential", "action": "add/update/delete", "data": { ... } },
    { "type": "manage_integration", "action": "connect/disconnect", "service": "google_calendar" },
    { "type": "browser_automation", "action": "greyhr_signin/greyhr_signout" },
    { "type": "manage_automation", "action": "schedule/skip/cancel", "data": { "service": "greyhr_signin/greyhr_signout", "time": "10:40", "days": ["Monday", "Tuesday"], "skip_date": "YYYY-MM-DD" } }
  ]
}
"""

def clean_json_response(text):
    """Helper to extract JSON if the model includes markdown backticks or extra text."""
    try:
        # Try to find JSON block
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(text)
    except:
        return None

async def process_user_input(text: str, context_tasks: list = None, context_credentials: list = None, image_b64: str = None, preferences: dict = None, learned_context: str = None, focus_history: list = None):
    if not client:
        return {"reply": "AI Service is offline: GEMINI_API_KEY is missing from the environment variables.", "actions": []}

    try:
        if context_tasks is None:
            context_tasks = []
        if context_credentials is None:
            context_credentials = []
            
        # Get current date and tomorrow for context
        now = datetime.now()
        today_date = now.strftime("%Y-%m-%d")
        tomorrow_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Sort and format all tasks dynamically
        from collections import defaultdict
        grouped_tasks = defaultdict(list)
        for t in context_tasks:
            date_str = t.get("date", "Unknown")
            grouped_tasks[date_str].append(t)
            
        schedule_context = "\n\nUser's Schedule Context (Past 1 Year to Future 2 Years):\n"
        if not grouped_tasks:
            schedule_context += "The user has no upcoming tasks scheduled.\n"
        else:
            # Always ensure today and tomorrow are printed even if empty, for clarity.
            if today_date not in grouped_tasks:
                schedule_context += f"\n--- Date: TODAY ({today_date}) ---\nNo tasks scheduled for today.\n"
            if tomorrow_date not in grouped_tasks:
                schedule_context += f"\n--- Date: TOMORROW ({tomorrow_date}) ---\nNo tasks scheduled for tomorrow.\n"

            for d in sorted(grouped_tasks.keys()):
                label = "TODAY" if d == today_date else "TOMORROW" if d == tomorrow_date else d
                schedule_context += f"\n--- Date: {label} ({d}) ---\n"
                for task in sorted(grouped_tasks[d], key=lambda x: x.get("start_time", "23:59")):
                    schedule_context += f"- {task.get('start_time', '')} to {task.get('end_time', '')}: {task.get('title', '')} ({task.get('category', '')})\n"

        
        credentials_context = "\n\nCREDENTIAL VAULT CONTEXT:\n"
        if context_credentials:
            for cred in context_credentials:
                credentials_context += f"- Service: {cred.get('service_name', 'Unknown')}, Type: {cred.get('identifier_type', '')}, ID: {cred.get('identifier_value', '')}, Password: {cred.get('password', '')}\n"
        else:
            credentials_context += "The user's credential vault is empty.\n"
        
        preferences_context = "\n\nUSER PREFERENCES (Persistent):\n"
        if preferences:
            preferences_context += f"- Default Focus Duration: {preferences.get('default_focus_duration', 25)} min\n"
            preferences_context += f"- Praise Mode: {'On' if preferences.get('agent_praise_mode') else 'Off'}\n"
        
        knowledge_context = "\n\nAGENT LEARNED KNOWLEDGE (Persistent Memory):\n"
        knowledge_context += learned_context if learned_context else "No specific learned context yet. Learn from the session history below."
        
        focus_context = "\n\nRECENT FOCUS HISTORY (Persistence):\n"
        if focus_history:
            for sess in focus_history:
                focus_context += f"- {sess.get('start_time', 'Unknown')}: {sess.get('duration_minutes')} min focus ({sess.get('status')})\n"
        else:
            focus_context += "No recent focus sessions recorded.\n"
        
        full_prompt = f"{SYSTEM_PROMPT}\n\nIMPORTANT: Today's date is {today_date}.{schedule_context}{credentials_context}{preferences_context}{knowledge_context}{focus_context}\n\nUser Input: {text}"
        
        # Prepare contents (multimodal)
        contents = [full_prompt]
        if image_b64:
            # Handle base64 image (remove prefix if present)
            if "," in image_b64:
                image_b64 = image_b64.split(",")[1]
            
            import base64
            contents.append({
                "mime_type": "image/jpeg",
                "data": base64.b64decode(image_b64)
            })

        response = client.generate_content(
            contents=contents,
            generation_config=generate_config
        )
        
        if not response.text:
            return {"reply": "I'm sorry, I couldn't generate a response.", "tasks": []}

        data = clean_json_response(response.text)
        if data:
            return data
            
        return {"reply": "Sorry, I had trouble formatting the response correctly.", "tasks": []}
        
    except Exception as e:
        print(f"AI Error: {e}")
        return {"reply": f"AI Error: {str(e)}", "tasks": []}
