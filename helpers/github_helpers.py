"""
GitHub helper functions using GitHub API v3.
Provides operations for repositories, issues, pull requests, etc.
"""

from typing import Dict, List, Any, Optional
import requests
import logging

logger = logging.getLogger(__name__)


class GitHubHelpers:
    """Helper class for GitHub operations."""

    BASE_URL = "https://api.github.com"

    @staticmethod
    def _get_headers(token: str) -> Dict[str, str]:
        """Get headers with auth credentials"""
        return {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}",
            "User-Agent": "Blimp-GitHub-Integration",
        }

    @staticmethod
    async def list_repositories(
        access_token: str, per_page: int = 10
    ) -> Dict[str, Any]:
        """
        List user's repositories

        Args:
            access_token: GitHub OAuth token
            per_page: Number of results per page

        Returns:
            Dict with repositories list
        """
        try:
            url = f"{GitHubHelpers.BASE_URL}/user/repos"
            params = {"per_page": per_page, "sort": "updated", "direction": "desc"}
            headers = GitHubHelpers._get_headers(access_token)

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            repos = response.json()

            return {"success": True, "repositories": repos, "count": len(repos)}

        except Exception as error:
            logger.error(f"GitHub API error listing repositories: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def list_issues(
        access_token: str, repo: str, state: str = "all", per_page: int = 10
    ) -> Dict[str, Any]:
        """
        List issues in a repository

        Args:
            access_token: GitHub OAuth token
            repo: Repository name (owner/repo)
            state: Issue state (open, closed, all)
            per_page: Number of results per page

        Returns:
            Dict with issues list
        """
        try:
            url = f"{GitHubHelpers.BASE_URL}/repos/{repo}/issues"
            params = {
                "state": state,
                "per_page": per_page,
                "sort": "updated",
                "direction": "desc",
            }
            headers = GitHubHelpers._get_headers(access_token)

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            issues = response.json()

            return {
                "success": True,
                "issues": issues,
                "repository": repo,
                "count": len(issues),
            }

        except Exception as error:
            logger.error(f"GitHub API error listing issues: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def list_pull_requests(
        access_token: str, repo: str, state: str = "all", per_page: int = 10
    ) -> Dict[str, Any]:
        """
        List pull requests in a repository

        Args:
            access_token: GitHub OAuth token
            repo: Repository name (owner/repo)
            state: PR state (open, closed, all)
            per_page: Number of results per page

        Returns:
            Dict with pull requests list
        """
        try:
            url = f"{GitHubHelpers.BASE_URL}/repos/{repo}/pulls"
            params = {
                "state": state,
                "per_page": per_page,
                "sort": "updated",
                "direction": "desc",
            }
            headers = GitHubHelpers._get_headers(access_token)

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            prs = response.json()

            return {
                "success": True,
                "pull_requests": prs,
                "repository": repo,
                "count": len(prs),
            }

        except Exception as error:
            logger.error(f"GitHub API error listing pull requests: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def create_issue(
        access_token: str,
        repo: str,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create an issue in a repository

        Args:
            access_token: GitHub OAuth token
            repo: Repository name (owner/repo)
            title: Issue title
            body: Issue description
            labels: List of label names

        Returns:
            Dict with created issue data
        """
        try:
            url = f"{GitHubHelpers.BASE_URL}/repos/{repo}/issues"
            headers = GitHubHelpers._get_headers(access_token)

            payload = {"title": title, "body": body}

            if labels:
                payload["labels"] = labels

            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            issue = response.json()

            return {"success": True, "issue": issue}

        except Exception as error:
            logger.error(f"GitHub API error creating issue: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def search_issues(
        access_token: str, query: str, per_page: int = 10
    ) -> Dict[str, Any]:
        """
        Search for issues across repositories

        Args:
            access_token: GitHub OAuth token
            query: Search query
            per_page: Number of results per page

        Returns:
            Dict with matching issues
        """
        try:
            url = f"{GitHubHelpers.BASE_URL}/search/issues"
            params = {"q": query, "per_page": per_page, "sort": "updated"}
            headers = GitHubHelpers._get_headers(access_token)

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()

            return {
                "success": True,
                "issues": result.get("items", []),
                "query": query,
                "count": result.get("total_count", 0),
            }

        except Exception as error:
            logger.error(f"GitHub API error searching issues: {error}")
            return {"success": False, "error": str(error)}


# Function registry for Gemini
GITHUB_FUNCTIONS = {
    "list_repositories": {
        "name": "list_repositories",
        "description": "List user's repositories sorted by recent updates",
        "parameters": {"per_page": "Number of results per page (default: 10)"},
    },
    "list_issues": {
        "name": "list_issues",
        "description": "List issues in a repository",
        "parameters": {
            "repo": "Repository name (owner/repo)",
            "state": "Issue state: open, closed, or all (default: all)",
            "per_page": "Number of results per page (default: 10)",
        },
    },
    "list_pull_requests": {
        "name": "list_pull_requests",
        "description": "List pull requests in a repository",
        "parameters": {
            "repo": "Repository name (owner/repo)",
            "state": "PR state: open, closed, or all (default: all)",
            "per_page": "Number of results per page (default: 10)",
        },
    },
    "create_issue": {
        "name": "create_issue",
        "description": "Create a new issue in a repository",
        "parameters": {
            "repo": "Repository name (owner/repo)",
            "title": "Issue title",
            "body": "Issue description (optional)",
            "labels": "List of label names (optional)",
        },
    },
    "search_issues": {
        "name": "search_issues",
        "description": "Search for issues across repositories",
        "parameters": {
            "query": "Search query",
            "per_page": "Number of results per page (default: 10)",
        },
    },
}
