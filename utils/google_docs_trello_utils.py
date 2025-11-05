"""
Google Docs to Trello integration
Creates Trello cards and documents progress in Google Docs
"""

import logging
from typing import Dict, Any
from helpers.google_docs_helpers import GoogleDocsHelpers
from helpers.trello_helpers import TrelloHelpers

logger = logging.getLogger(__name__)


class GoogleDocsTrelloUtils:
    """Utility class for Google Docs to Trello workflows"""

    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials
        self.google_docs_helpers = GoogleDocsHelpers()
        self.trello_helpers = TrelloHelpers()

    async def document_trello_board_progress(
        self, board_id: str, document_id: str, include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Document Trello board progress in a Google Docs document

        Args:
            board_id: Trello board ID
            document_id: Google Docs document ID
            include_details: Whether to include card details

        Returns:
            Dict with operation results
        """
        try:
            logger.info(
                f"Documenting Trello board {board_id} to Google Doc {document_id}"
            )

            # Get board data
            board_result = await self.trello_helpers.get_board(
                board_id=board_id,
                credentials=self.credentials.get("trello", {}).get("credentials", {}),
            )

            if not board_result.get("success"):
                return board_result

            # Get lists and cards
            lists_result = await self.trello_helpers.get_board_lists(
                board_id=board_id,
                credentials=self.credentials.get("trello", {}).get("credentials", {}),
            )

            # Format content
            content = f"\n\n--- Trello Board: {board_result.get('name')} ---\n"

            for list_item in lists_result.get("lists", []):
                content += f"\n## {list_item.get('name')}\n"

                if include_details:
                    for card in list_item.get("cards", []):
                        content += f"- {card.get('name')}\n"

            # Append to document
            append_result = await self.google_docs_helpers.append_to_document(
                document_id=document_id,
                content=content,
                credentials=self.credentials.get("google_docs", {}).get(
                    "credentials", {}
                ),
            )

            return append_result

        except Exception as e:
            logger.error(f"Error documenting Trello progress: {str(e)}")
            return {"success": False, "error": str(e)}
