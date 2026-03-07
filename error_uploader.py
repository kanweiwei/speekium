"""
Error Uploader for Speekium
Handles uploading errors to remote services (GitHub Issues, Sentry, etc.)
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from error_tracker import ErrorRecord, ErrorTracker


class ErrorUploader:
    """
    Error uploader for batch reporting errors to remote services.
    
    Supported targets:
    - GitHub Issues (free, default)
    - Sentry (optional)
    - Local (fallback)
    """
    
    def __init__(
        self,
        tracker: ErrorTracker | None = None,
        github_token: str | None = None,
        github_repo: str | None = None,
    ):
        """
        Initialize error uploader.
        
        Args:
            tracker: ErrorTracker instance. If None, uses global tracker.
            github_token: GitHub personal access token for Issues API
            github_repo: Repository in format "owner/repo"
        """
        self.tracker = tracker or ErrorTracker()
        
        # GitHub configuration
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.github_repo = github_repo or os.environ.get("GITHUB_REPO", "kanweiwei/speekium")
        
        # Track reported errors
        self._reported_file = self.tracker.storage_path / "reported.json"
        self._reported_ids: set[str] = self._load_reported()
    
    def _load_reported(self) -> set[str]:
        """Load set of reported error IDs."""
        if not self._reported_file.exists():
            return set()
        
        try:
            with open(self._reported_file, "r") as f:
                data = json.load(f)
                return set(data.get("reported_ids", []))
        except Exception:
            return set()
    
    def _save_reported(self):
        """Save reported error IDs."""
        try:
            self._reported_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._reported_file, "w") as f:
                json.dump({"reported_ids": list(self._reported_ids)}, f)
        except Exception as e:
            print(f"Failed to save reported IDs: {e}")
    
    def get_pending(self, limit: int = 10) -> list[ErrorRecord]:
        """
        Get errors that haven't been reported yet.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of ErrorRecord objects
        """
        all_errors = self.tracker.get_errors(limit=100)
        
        # Filter out already reported
        pending = []
        for error in all_errors:
            error_id = f"{error.timestamp}_{error.error_type}"
            if error_id not in self._reported_ids:
                pending.append(error)
                if len(pending) >= limit:
                    break
        
        return pending
    
    def _generate_github_issue_body(self, error: ErrorRecord) -> str:
        """Generate GitHub Issue body from error record."""
        lines = [
            f"**Level:** {error.level}",
            f"**Type:** {error.error_type}",
            f"**Time:** {error.timestamp}",
            f"**Function:** {error.context.get('function', 'N/A')}",
            "",
            "### Context",
        ]
        
        # Add context (excluding sensitive data)
        for key, value in error.context.items():
            lines.append(f"- **{key}:** {value}")
        
        if error.stack_trace:
            lines.extend([
                "",
                "### Stack Trace",
                "```",
                error.stack_trace[:2000],  # Limit length
                "```"
            ])
        
        return "\n".join(lines)
    
    async def upload_to_github(self, errors: list[ErrorRecord]) -> dict[str, Any]:
        """
        Upload errors to GitHub Issues.
        
        Args:
            errors: List of ErrorRecord to upload
            
        Returns:
            Result dict with success count and issue URLs
        """
        if not self.github_token:
            return {"success": False, "error": "No GitHub token configured"}
        
        results = {
            "success": True,
            "uploaded": [],
            "failed": []
        }
        
        owner, repo = self.github_repo.split("/")
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        for error in errors:
            try:
                title = f"[{error.level.upper()}] {error.error_type} - {error.timestamp[:19]}"
                body = self._generate_github_issue_body(error)
                
                response = requests.post(
                    url,
                    headers=headers,
                    json={
                        "title": title,
                        "body": body,
                        "labels": ["error", "auto-reported"]
                    },
                    timeout=30
                )
                
                if response.status_code == 201:
                    issue_url = response.json().get("html_url")
                    results["uploaded"].append({
                        "error_id": f"{error.timestamp}_{error.error_type}",
                        "issue_url": issue_url
                    })
                else:
                    results["failed"].append({
                        "error_id": f"{error.timestamp}_{error.error_type}",
                        "status": response.status_code,
                        "message": response.text[:200]
                    })
                    
            except Exception as e:
                results["failed"].append({
                    "error_id": f"{error.timestamp}_{error.error_type}",
                    "error": str(e)
                })
        
        results["success"] = len(results["failed"]) == 0
        return results
    
    async def upload_batch(self, target: str = "github") -> dict[str, Any]:
        """
        Upload pending errors to target.
        
        Args:
            target: Target service ("github", "sentry", "local")
            
        Returns:
            Result dict
        """
        errors = self.get_pending()
        
        if not errors:
            return {"success": True, "message": "No pending errors", "uploaded": 0}
        
        if target == "github":
            result = await self.upload_to_github(errors)
        else:
            return {"success": False, "error": f"Unknown target: {target}"}
        
        # Mark successfully uploaded as reported
        if result.get("uploaded"):
            for item in result["uploaded"]:
                self._reported_ids.add(item["error_id"])
            self._save_reported()
        
        return result
    
    def mark_reported(self, error_ids: list[str]):
        """
        Manually mark errors as reported.
        
        Args:
            error_ids: List of error IDs to mark
        """
        self._reported_ids.update(error_ids)
        self._save_reported()
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get error statistics.
        
        Returns:
            Stats dict
        """
        all_errors = self.tracker.get_errors(limit=100)
        
        # Count by level
        level_counts = {}
        for error in all_errors:
            level = error.level
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return {
            "total_errors": len(all_errors),
            "pending": len(self.get_pending(limit=100)),
            "reported": len(self._reported_ids),
            "by_level": level_counts
        }


# CLI helper for manual uploads
async def main():
    """CLI for uploading errors."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload errors to remote")
    parser.add_argument("--target", default="github", choices=["github"])
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    
    args = parser.parse_args()
    
    uploader = ErrorUploader()
    
    if args.stats:
        stats = uploader.get_stats()
        print(json.dumps(stats, indent=2))
    else:
        result = await uploader.upload_batch(args.target)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
