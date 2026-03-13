"""
EduSync Backend - Base Models
Common base models used across the application.
"""
from pydantic import BaseModel, ConfigDict
from bson import ObjectId
from datetime import datetime


class MongoDBModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    )
