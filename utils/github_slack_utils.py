"""
GitHub to Slack integration utilities
"""

import logging
from typing import Dict, Any
from helpers.github_helpers import GitHubHelpers
from helpers.slack_helpers import SlackHelpers

logger = logging.getLogger(__name__)


class GitHubSlackUtils:
    """Utilities for integrating GitHub with Slack"""

    def __init__(self, github_creds: Dict[str, Any], slack_creds: Dict[str, Any]):
        """Initialize with credentials"""
        self.github_creds = github_creds
        self.slack_creds = slack_creds

    async def send_repository_updates_to_slack(
        self, repo: str, channel_id: str
    ) -> Dict[str, Any]:
        """Send GitHub repository updates to Slack"""
        try:
            issues_result = await GitHubHelpers.list_issues(
                access_token=self.github_creds.get("access_token"),
                repo=repo,
                state="all",
                per_page=5,
            )

            prs_result = await GitHubHelpers.list_pull_requests(
                access_token=self.github_creds.get("access_token"),
                repo=repo,
                state="all",
                per_page=5,
            )

            message = f"🚀 *GitHub Repository Update: {repo}*\n\n"

            if issues_result.get("success"):
                issues = issues_result.get("issues", [])[:3]
                message += f"📋 Recent Issues ({len(issues)}):\n"
                for issue in issues:
                    message += f"  • {issue['title']} (#{issue['number']})\n"

            if prs_result.get("success"):
                prs = prs_result.get("pull_requests", [])[:3]
                message += f"\n🔄 Recent PRs ({len(prs)}):\n"
                for pr in prs:
                    message += f"  • {pr['title']} (#{pr['number']})\n"

            slack_helper = SlackHelpers()
            send_result = await slack_helper.send_message(
                access_token=self.slack_creds.get("access_token"),
                channel_id=channel_id,
                text=message,
            )

            if not send_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to send message: {send_result.get('error')}",
                }

            logger.info(f"Sent repo update to Slack")
            return {"success": True, "message": "Repository update sent to Slack"}

        except Exception as e:
            logger.error(
                f"Error in send_repository_updates_to_slack: {str(e)}", exc_info=True
            )
            return {"success": False, "error": str(e)}
