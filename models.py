from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    id: str
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD (Start Date)
    end_date: Optional[str] = None  # YYYY-MM-DD
    start_time: Optional[str] = None  # HH:MM
    end_time: Optional[str] = None  # HH:MM
    priority: str = "Medium"
    category: str = "Task"  # Task, Work, Meeting
    status: str = "Pending"
    reminder_time: Optional[int] = 10  # minutes before start
    ai_generated: bool = False
    notes: Optional[str] = None
    path: Optional[str] = None
    remarks: Optional[str] = None
    metadata: Optional[dict] = {}  # Dynamic columns/fields
    google_event_id: Optional[str] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    reminder_time: Optional[int] = None
    notes: Optional[str] = None
    path: Optional[str] = None
    remarks: Optional[str] = None
    metadata: Optional[dict] = None
    google_event_id: Optional[str] = None

class TaskResponse(TaskBase):
    id: str
    user_id: str

class NoteBase(BaseModel):
    content: str
    date: str

class NoteCreate(NoteBase):
    pass

class NoteResponse(NoteBase):
    id: str
    user_id: str

class AIChatRequest(BaseModel):
    text: str
    image: Optional[str] = None  # Base64 encoded image

class AIChatResponse(BaseModel):
    reply: str
    suggested_tasks: List[TaskBase] = []

class HabitBase(BaseModel):
    title: str
    frequency: str  # Daily, Weekly
    status: dict = {}  # { "YYYY-MM-DD": true/false }

class HabitCreate(HabitBase):
    pass

class HabitResponse(HabitBase):
    id: str
    user_id: str

class CredentialBase(BaseModel):
    service_name: str
    identifier_type: str = "username" # username, email, etc.
    identifier_value: str
    password: Optional[str] = None
    metadata: dict = {}

class CredentialCreate(CredentialBase):
    pass

class CredentialResponse(CredentialBase):
    id: str
    user_id: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class UpdatePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class GoogleCredentials(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: List[str]


class FocusSessionBase(BaseModel):
    title: Optional[str] = "Focus Session"
    duration_minutes: int
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str = "Completed" # Completed, Interrupted

class FocusSessionCreate(FocusSessionBase):
    pass

class FocusSessionResponse(FocusSessionBase):
    id: str
    user_id: str

class UserPreferenceBase(BaseModel):
    default_focus_duration: int = 25
    theme: str = "dark"
    agent_praise_mode: bool = True
    learned_context: Optional[str] = None # For agent knowledge

class UserPreferenceUpdate(BaseModel):
    default_focus_duration: Optional[int] = None
    theme: Optional[str] = None
    agent_praise_mode: Optional[bool] = None
    learned_context: Optional[str] = None

class UserPreferenceResponse(UserPreferenceBase):
    user_id: str
