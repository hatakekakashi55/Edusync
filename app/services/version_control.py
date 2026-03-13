"""
EduSync Backend - Version Control Service
Auto-extracted from main.py
"""
import logging
import os
import json
import asyncio
import uuid
import hashlib
import subprocess
import tempfile
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pathlib import Path

from app.database import *
from app.config import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, AIModelWrapper

logger = logging.getLogger("edusync")

class VersionControlService:
    @staticmethod
    async def create_repository(user_id: str, name: str, description: str, is_public: bool = True):
        """Create a new code repository"""
        try:
            repo_id = str(uuid.uuid4())
            
            repository = {
                "id": repo_id,
                "name": name,
                "description": description,
                "owner_id": user_id,
                "is_public": is_public,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "collaborators": [user_id],
                "branches": ["main"],
                "default_branch": "main",
                "star_count": 0,
                "fork_count": 0,
                "last_commit": None,
                "language_stats": {},
                "settings": {
                    "allow_pull_requests": True,
                    "allow_issues": True,
                    "require_code_review": False
                }
            }
            
            await code_repositories_collection.insert_one(repository)
            return repository
            
        except Exception as e:
            logger.error(f"Create repository error: {e}")
            raise HTTPException(status_code=500, detail="Failed to create repository")
    
    @staticmethod
    async def create_commit(repository_id: str, user_id: str, message: str, files: List[Dict], branch: str = "main"):
        """Create a new commit in repository"""
        try:
            # Get repository
            repo = await code_repositories_collection.find_one({"id": repository_id})
            if not repo:
                raise HTTPException(status_code=404, detail="Repository not found")
            
            # Check if user has access
            if user_id not in repo.get("collaborators", []):
                raise HTTPException(status_code=403, detail="Access denied")
            
            commit_id = str(uuid.uuid4())
            
            commit = {
                "id": commit_id,
                "repository_id": repository_id,
                "author_id": user_id,
                "message": message,
                "files": files,
                "branch": branch,
                "timestamp": datetime.now(timezone.utc),
                "hash": hashlib.sha256(f"{repository_id}{user_id}{message}{datetime.now()}".encode()).hexdigest()[:12],
                "parent_commit": repo.get("last_commit"),
                "stats": {
                    "files_changed": len(files),
                    "additions": sum(f.get("additions", 0) for f in files),
                    "deletions": sum(f.get("deletions", 0) for f in files)
                }
            }
            
            await code_commits_collection.insert_one(commit)
            
            # Update repository
            await code_repositories_collection.update_one(
                {"id": repository_id},
                {
                    "$set": {
                        "last_commit": commit_id,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "recent_commits": {
                            "$each": [commit_id],
                            "$slice": -50  # Keep only last 50 commits
                        }
                    }
                }
            )
            
            # Update language statistics
            await VersionControlService.update_language_stats(repository_id)
            
            # Send notifications to collaborators
            for collaborator_id in repo.get("collaborators", []):
                if collaborator_id != user_id:
                    await NotificationService.create_notification(
                        user_id=collaborator_id,
                        title="New Commit",
                        message=f"New commit in {repo['name']}: {message}",
                        notification_type="repository",
                        action_url=f"/repos/{repository_id}/commit/{commit_id}"
                    )
            
            return commit
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Create commit error: {e}")
            raise HTTPException(status_code=500, detail="Failed to create commit")
    
    @staticmethod
    async def get_repository_files(repository_id: str, branch: str = "main"):
        """Get all files in repository at specific branch"""
        try:
            # Get all commits for the branch
            commits = await code_commits_collection.find({
                "repository_id": repository_id,
                "branch": branch
            }).sort("timestamp", 1).to_list(1000)  # Limit to 1000 commits
            
            # Build file tree from commits
            files = {}
            for commit in commits:
                for file in commit.get("files", []):
                    file_path = file.get("path")
                    if file_path:
                        files[file_path] = file.get("content", "")
            
            return files
            
        except Exception as e:
            logger.error(f"Get repository files error: {e}")
            return {}
    
    @staticmethod
    async def update_language_stats(repository_id: str):
        """Update language statistics for repository"""
        try:
            files = await VersionControlService.get_repository_files(repository_id)
            
            # Count files by extension
            extensions = {}
            for file_path, content in files.items():
                ext = Path(file_path).suffix.lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1
            
            # Map extensions to languages
            lang_map = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.java': 'Java',
                '.cpp': 'C++',
                '.c': 'C',
                '.go': 'Go',
                '.rs': 'Rust',
                '.html': 'HTML',
                '.css': 'CSS',
                '.md': 'Markdown',
                '.json': 'JSON'
            }
            
            language_stats = {}
            for ext, count in extensions.items():
                lang = lang_map.get(ext, ext.upper()[1:])
                language_stats[lang] = count
            
            await code_repositories_collection.update_one(
                {"id": repository_id},
                {"$set": {"language_stats": language_stats}}
            )
            
        except Exception as e:
            logger.error(f"Update language stats error: {e}")
    
    @staticmethod
    async def create_pull_request(repository_id: str, user_id: str, title: str, description: str, source_branch: str, target_branch: str = "main"):
        """Create a pull request"""
        try:
            pr_id = str(uuid.uuid4())
            
            pr = {
                "id": pr_id,
                "repository_id": repository_id,
                "title": title,
                "description": description,
                "author_id": user_id,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "status": "open",  # open, closed, merged
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "comments": [],
                "reviewers": [],
                "assignees": [],
                "labels": ["feature"],
                "mergeable": True,
                "conflicts": []
            }
            
            # Save to version_control collection
            await version_control_collection.insert_one(pr)
            
            # Notify repository owner
            repo = await code_repositories_collection.find_one({"id": repository_id})
            if repo:
                await NotificationService.create_notification(
                    user_id=repo["owner_id"],
                    title="New Pull Request",
                    message=f"New PR for {repo['name']}: {title}",
                    notification_type="pull_request",
                    action_url=f"/repos/{repository_id}/pull/{pr_id}"
                )
            
            return pr
            
        except Exception as e:
            logger.error(f"Create pull request error: {e}")
            raise HTTPException(status_code=500, detail="Failed to create pull request")

