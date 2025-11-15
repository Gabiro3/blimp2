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
        access_token: str, per_page: int = 20
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

    @staticmethod
    async def get_recent_push(
        access_token: str, repo: str, branch: str = "main", per_page: int = 1
    ) -> Dict[str, Any]:
        """
        Get the most recent push to a repository

        Args:
            access_token: GitHub OAuth token
            repo: Repository name (owner/repo)
            branch: Branch name (default: main)
            per_page: Number of commits to return (default: 1 for most recent)

        Returns:
            Dict with most recent push/commit information
        """
        try:
            url = f"{GitHubHelpers.BASE_URL}/repos/{repo}/commits"
            params = {
                "sha": branch,
                "per_page": per_page,
                "sort": "updated",
                "direction": "desc",
            }
            headers = GitHubHelpers._get_headers(access_token)

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            commits = response.json()

            if not commits:
                return {
                    "success": True,
                    "repository": repo,
                    "branch": branch,
                    "message": "No commits found",
                    "commit": None,
                }

            most_recent = commits[0]
            commit_info = {
                "sha": most_recent.get("sha"),
                "message": most_recent.get("commit", {}).get("message"),
                "author": most_recent.get("commit", {}).get("author", {}).get("name"),
                "author_email": most_recent.get("commit", {}).get("author", {}).get("email"),
                "date": most_recent.get("commit", {}).get("author", {}).get("date"),
                "url": most_recent.get("html_url"),
                "committer": most_recent.get("commit", {}).get("committer", {}).get("name"),
            }

            return {
                "success": True,
                "repository": repo,
                "branch": branch,
                "commit": commit_info,
                "pushed_at": most_recent.get("commit", {}).get("author", {}).get("date"),
            }

        except Exception as error:
            logger.error(f"GitHub API error getting recent push: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def check_all_prs_merged(
        access_token: str, repo: str, state: str = "all"
    ) -> Dict[str, Any]:
        """
        Check if all pull requests in a repository have been merged

        Args:
            access_token: GitHub OAuth token
            repo: Repository name (owner/repo)
            state: PR state to check (open, closed, all) - default: all

        Returns:
            Dict with merge status information
        """
        try:
            url = f"{GitHubHelpers.BASE_URL}/repos/{repo}/pulls"
            params = {
                "state": state,
                "per_page": 100,  # Get up to 100 PRs
                "sort": "updated",
                "direction": "desc",
            }
            headers = GitHubHelpers._get_headers(access_token)

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            prs = response.json()

            total_prs = len(prs)
            merged_count = 0
            open_count = 0
            closed_not_merged_count = 0
            unmerged_prs = []

            for pr in prs:
                pr_number = pr.get("number")
                pr_title = pr.get("title")
                pr_state = pr.get("state")
                merged = pr.get("merged", False)

                if merged:
                    merged_count += 1
                elif pr_state == "open":
                    open_count += 1
                    unmerged_prs.append(
                        {
                            "number": pr_number,
                            "title": pr_title,
                            "state": pr_state,
                            "url": pr.get("html_url"),
                        }
                    )
                else:
                    closed_not_merged_count += 1
                    unmerged_prs.append(
                        {
                            "number": pr_number,
                            "title": pr_title,
                            "state": pr_state,
                            "merged": False,
                            "url": pr.get("html_url"),
                        }
                    )

            all_merged = open_count == 0 and closed_not_merged_count == 0

            return {
                "success": True,
                "repository": repo,
                "all_merged": all_merged,
                "total_prs": total_prs,
                "merged_count": merged_count,
                "open_count": open_count,
                "closed_not_merged_count": closed_not_merged_count,
                "unmerged_prs": unmerged_prs[:10],  # Limit to first 10 for response size
            }

        except Exception as error:
            logger.error(f"GitHub API error checking PR merge status: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def find_pr_by_title(
        access_token: str, repo: str, title: str, state: str = "all"
    ) -> Dict[str, Any]:
        """
        Find a pull request by title in a repository

        Args:
            access_token: GitHub OAuth token
            repo: Repository name (owner/repo)
            title: PR title to search for (partial match supported)
            state: PR state (open, closed, all) - default: all

        Returns:
            Dict with matching pull request(s)
        """
        try:
            url = f"{GitHubHelpers.BASE_URL}/repos/{repo}/pulls"
            params = {
                "state": state,
                "per_page": 100,
                "sort": "updated",
                "direction": "desc",
            }
            headers = GitHubHelpers._get_headers(access_token)

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            prs = response.json()

            # Search for PRs matching the title (case-insensitive partial match)
            title_lower = title.lower()
            matching_prs = []
            for pr in prs:
                pr_title = pr.get("title", "").lower()
                if title_lower in pr_title or pr_title in title_lower:
                    matching_prs.append(
                        {
                            "number": pr.get("number"),
                            "title": pr.get("title"),
                            "state": pr.get("state"),
                            "merged": pr.get("merged", False),
                            "author": pr.get("user", {}).get("login"),
                            "created_at": pr.get("created_at"),
                            "updated_at": pr.get("updated_at"),
                            "url": pr.get("html_url"),
                            "body": pr.get("body", "")[:500],  # First 500 chars
                        }
                    )

            return {
                "success": True,
                "repository": repo,
                "search_title": title,
                "pull_requests": matching_prs,
                "count": len(matching_prs),
            }

        except Exception as error:
            logger.error(f"GitHub API error finding PR by title: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_pr_comments(
        access_token: str, repo: str, pr_number: Optional[int] = None, pr_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comments for a pull request by PR number or by finding PR by title

        Args:
            access_token: GitHub OAuth token
            repo: Repository name (owner/repo)
            pr_number: Pull request number (if known)
            pr_title: Pull request title to search for (if pr_number not provided)

        Returns:
            Dict with PR comments
        """
        try:
            # If pr_number not provided, find PR by title first
            if not pr_number and pr_title:
                find_result = await GitHubHelpers.find_pr_by_title(
                    access_token, repo, pr_title
                )
                if not find_result.get("success") or not find_result.get("pull_requests"):
                    return {
                        "success": False,
                        "error": f"No pull request found with title: {pr_title}",
                    }
                # Use the first matching PR
                pr_number = find_result["pull_requests"][0]["number"]

            if not pr_number:
                return {
                    "success": False,
                    "error": "Either pr_number or pr_title must be provided",
                }

            # Get PR comments
            url = f"{GitHubHelpers.BASE_URL}/repos/{repo}/pulls/{pr_number}/comments"
            headers = GitHubHelpers._get_headers(access_token)

            response = requests.get(url, params={"per_page": 100}, headers=headers)
            response.raise_for_status()
            comments = response.json()

            # Also get review comments (different endpoint)
            review_url = f"{GitHubHelpers.BASE_URL}/repos/{repo}/pulls/{pr_number}/reviews"
            review_response = requests.get(
                review_url, params={"per_page": 100}, headers=headers
            )
            review_response.raise_for_status()
            reviews = review_response.json()

            # Format comments
            formatted_comments = []
            for comment in comments:
                formatted_comments.append(
                    {
                        "id": comment.get("id"),
                        "user": comment.get("user", {}).get("login"),
                        "body": comment.get("body"),
                        "created_at": comment.get("created_at"),
                        "updated_at": comment.get("updated_at"),
                        "type": "comment",
                        "path": comment.get("path"),  # File path if inline comment
                        "line": comment.get("line"),  # Line number if inline comment
                    }
                )

            # Format review comments
            for review in reviews:
                if review.get("body"):  # Only include reviews with comments
                    formatted_comments.append(
                        {
                            "id": review.get("id"),
                            "user": review.get("user", {}).get("login"),
                            "body": review.get("body"),
                            "created_at": review.get("submitted_at"),
                            "state": review.get("state"),  # APPROVED, CHANGES_REQUESTED, etc.
                            "type": "review",
                        }
                    )

            # Sort by creation date (most recent first)
            formatted_comments.sort(
                key=lambda x: x.get("created_at", ""), reverse=True
            )

            return {
                "success": True,
                "repository": repo,
                "pr_number": pr_number,
                "comments": formatted_comments,
                "total_comments": len(formatted_comments),
                "regular_comments": len([c for c in formatted_comments if c.get("type") == "comment"]),
                "review_comments": len([c for c in formatted_comments if c.get("type") == "review"]),
            }

        except Exception as error:
            logger.error(f"GitHub API error getting PR comments: {error}")
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
    "get_recent_push": {
        "name": "get_recent_push",
        "description": "Get the most recent push/commit to a repository branch",
        "parameters": {
            "repo": "Repository name (owner/repo)",
            "branch": "Branch name (default: main)",
            "per_page": "Number of commits to return (default: 1 for most recent)",
        },
    },
    "check_all_prs_merged": {
        "name": "check_all_prs_merged",
        "description": "Check if all pull requests in a repository have been merged. Returns status of all PRs including open and closed unmerged ones.",
        "parameters": {
            "repo": "Repository name (owner/repo)",
            "state": "PR state to check: open, closed, or all (default: all)",
        },
    },
    "find_pr_by_title": {
        "name": "find_pr_by_title",
        "description": "Find pull request(s) by title in a repository. Supports partial matching.",
        "parameters": {
            "repo": "Repository name (owner/repo)",
            "title": "PR title to search for (partial match supported)",
            "state": "PR state: open, closed, or all (default: all)",
        },
    },
    "get_pr_comments": {
        "name": "get_pr_comments",
        "description": "Get all comments for a pull request, including inline comments and review comments. Can find PR by number or by searching by title.",
        "parameters": {
            "repo": "Repository name (owner/repo)",
            "pr_number": "Pull request number (optional if pr_title provided)",
            "pr_title": "Pull request title to search for (optional if pr_number provided)",
        },
    },
}
