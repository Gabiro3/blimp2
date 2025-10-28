"""
Security Data Filter
Filters sensitive information from data before passing to AI models
"""

import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class SecurityFilter:
    """Filter sensitive information from data"""

    # Patterns for sensitive data
    SENSITIVE_PATTERNS = {
        "password": [
            r'password["\s:=]+[^\s,}\]]+',
            r'pwd["\s:=]+[^\s,}\]]+',
            r'pass["\s:=]+[^\s,}\]]+',
        ],
        "api_key": [
            r'api[_-]?key["\s:=]+[^\s,}\]]+',
            r'apikey["\s:=]+[^\s,}\]]+',
            r'access[_-]?token["\s:=]+[^\s,}\]]+',
        ],
        "secret": [
            r'secret["\s:=]+[^\s,}\]]+',
            r'client[_-]?secret["\s:=]+[^\s,}\]]+',
        ],
        "credit_card": [
            r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
            r"\b\d{13,19}\b",
        ],
        "ssn": [
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"\b\d{9}\b",
        ],
        "private_key": [
            r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
            r"-----BEGIN\s+ENCRYPTED\s+PRIVATE\s+KEY-----",
        ],
    }

    @staticmethod
    def filter_text(text: str) -> str:
        """
        Filter sensitive information from text

        Args:
            text: Text to filter

        Returns:
            Filtered text with sensitive info redacted
        """
        if not text:
            return text

        filtered_text = text

        for category, patterns in SecurityFilter.SENSITIVE_PATTERNS.items():
            for pattern in patterns:
                filtered_text = re.sub(
                    pattern,
                    f"[REDACTED_{category.upper()}]",
                    filtered_text,
                    flags=re.IGNORECASE,
                )

        return filtered_text

    @staticmethod
    def filter_email(email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive information from email data

        Args:
            email_data: Email data dictionary

        Returns:
            Filtered email data
        """
        filtered = email_data.copy()

        # Filter subject
        if "subject" in filtered:
            filtered["subject"] = SecurityFilter.filter_text(filtered["subject"])

        # Filter body/snippet
        if "body" in filtered:
            filtered["body"] = SecurityFilter.filter_text(filtered["body"])
        if "snippet" in filtered:
            filtered["snippet"] = SecurityFilter.filter_text(filtered["snippet"])

        # Filter headers
        if "headers" in filtered:
            for header in filtered["headers"]:
                if "value" in header:
                    header["value"] = SecurityFilter.filter_text(header["value"])

        return filtered

    @staticmethod
    def filter_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive information from message data (Slack, Discord, etc.)

        Args:
            message_data: Message data dictionary

        Returns:
            Filtered message data
        """
        filtered = message_data.copy()

        # Filter text content
        if "text" in filtered:
            filtered["text"] = SecurityFilter.filter_text(filtered["text"])
        if "content" in filtered:
            filtered["content"] = SecurityFilter.filter_text(filtered["content"])

        # Filter attachments
        if "attachments" in filtered:
            for attachment in filtered["attachments"]:
                if "text" in attachment:
                    attachment["text"] = SecurityFilter.filter_text(attachment["text"])
                if "title" in attachment:
                    attachment["title"] = SecurityFilter.filter_text(
                        attachment["title"]
                    )

        return filtered

    @staticmethod
    def filter_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive information from calendar event data

        Args:
            event_data: Event data dictionary

        Returns:
            Filtered event data
        """
        filtered = event_data.copy()

        # Filter summary
        if "summary" in filtered:
            filtered["summary"] = SecurityFilter.filter_text(filtered["summary"])

        # Filter description
        if "description" in filtered:
            filtered["description"] = SecurityFilter.filter_text(
                filtered["description"]
            )

        # Filter location
        if "location" in filtered:
            filtered["location"] = SecurityFilter.filter_text(filtered["location"])

        return filtered

    @staticmethod
    def filter_data_list(
        data_list: List[Dict[str, Any]], data_type: str
    ) -> List[Dict[str, Any]]:
        """
        Filter a list of data items based on type

        Args:
            data_list: List of data items
            data_type: Type of data (email, message, event)

        Returns:
            Filtered data list
        """
        filter_func = {
            "email": SecurityFilter.filter_email,
            "message": SecurityFilter.filter_message,
            "event": SecurityFilter.filter_event,
        }.get(data_type, lambda x: x)

        return [filter_func(item) for item in data_list]
