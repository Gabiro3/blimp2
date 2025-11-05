"""
Trello helper functions using Trello API.
Provides CRUD operations for boards, lists, cards, etc.
"""

from typing import Dict, List, Any, Optional
import requests
import logging

logger = logging.getLogger(__name__)


class TrelloHelpers:
    """Helper class for Trello operations."""

    BASE_URL = "https://api.trello.com/1"

    @staticmethod
    async def list_boards(
        access_token: str, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List user's Trello boards

        Args:
            access_token: Trello OAuth token (or API key)
            api_key: Trello API key (optional if using OAuth)

        Returns:
            Dict with boards list
        """
        try:
            url = f"{TrelloHelpers.BASE_URL}/members/me/boards"
            params = {
                "key": api_key or access_token,
                "token": access_token,
                "fields": "id,name,url,desc,dateLastActivity",
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            boards = response.json()

            return {"success": True, "boards": boards, "count": len(boards)}

        except Exception as error:
            logger.error(f"Trello API error listing boards: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_board_lists(
        access_token: str, board_id: str, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get lists in a Trello board

        Args:
            access_token: Trello OAuth token
            board_id: ID of the board
            api_key: Trello API key (optional)

        Returns:
            Dict with lists
        """
        try:
            url = f"{TrelloHelpers.BASE_URL}/boards/{board_id}/lists"
            params = {
                "key": api_key or access_token,
                "token": access_token,
                "fields": "id,name,pos,closed",
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            lists = response.json()

            return {"success": True, "lists": lists, "board_id": board_id}

        except Exception as error:
            logger.error(f"Trello API error getting board lists: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def get_list_cards(
        access_token: str, list_id: str, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get cards in a Trello list

        Args:
            access_token: Trello OAuth token
            list_id: ID of the list
            api_key: Trello API key (optional)

        Returns:
            Dict with cards
        """
        try:
            url = f"{TrelloHelpers.BASE_URL}/lists/{list_id}/cards"
            params = {
                "key": api_key or access_token,
                "token": access_token,
                "fields": "id,name,desc,url,labels,due,closed,idMembers",
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            cards = response.json()

            return {"success": True, "cards": cards, "list_id": list_id}

        except Exception as error:
            logger.error(f"Trello API error getting list cards: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def create_card(
        access_token: str,
        list_id: str,
        name: str,
        description: str = "",
        due: Optional[str] = None,
        labels: Optional[List[str]] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a card in a Trello list

        Args:
            access_token: Trello OAuth token
            list_id: ID of the list
            name: Card name
            description: Card description
            due: Due date (ISO format)
            labels: List of label IDs
            api_key: Trello API key (optional)

        Returns:
            Dict with created card data
        """
        try:
            url = f"{TrelloHelpers.BASE_URL}/cards"
            params = {
                "key": api_key or access_token,
                "token": access_token,
                "idList": list_id,
                "name": name,
                "desc": description,
            }

            if due:
                params["due"] = due
            if labels:
                params["idLabels"] = ",".join(labels)

            response = requests.post(url, params=params)
            response.raise_for_status()
            card = response.json()

            return {"success": True, "card": card}

        except Exception as error:
            logger.error(f"Trello API error creating card: {error}")
            return {"success": False, "error": str(error)}

    @staticmethod
    async def search_cards(
        access_token: str,
        query: str,
        board_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for cards

        Args:
            access_token: Trello OAuth token
            query: Search query
            board_id: Optional board ID to limit search
            api_key: Trello API key (optional)

        Returns:
            Dict with matching cards
        """
        try:
            url = f"{TrelloHelpers.BASE_URL}/search"
            params = {
                "key": api_key or access_token,
                "token": access_token,
                "query": query,
                "modelTypes": "cards",
                "card_fields": "id,name,desc,url,labels,due",
            }

            if board_id:
                params["idBoards"] = board_id

            response = requests.get(url, params=params)
            response.raise_for_status()
            result = response.json()
            cards = result.get("cards", [])

            return {"success": True, "cards": cards, "query": query}

        except Exception as error:
            logger.error(f"Trello API error searching cards: {error}")
            return {"success": False, "error": str(error)}


# Function registry for Gemini
TRELLO_FUNCTIONS = {
    "list_boards": {
        "name": "list_boards",
        "description": "List user's Trello boards",
        "parameters": {},
    },
    "get_board_lists": {
        "name": "get_board_lists",
        "description": "Get lists in a Trello board",
        "parameters": {"board_id": "ID of the board"},
    },
    "get_list_cards": {
        "name": "get_list_cards",
        "description": "Get cards in a Trello list",
        "parameters": {"list_id": "ID of the list"},
    },
    "create_card": {
        "name": "create_card",
        "description": "Create a card in a Trello list",
        "parameters": {
            "list_id": "ID of the list",
            "name": "Card name",
            "description": "Card description (optional)",
            "due": "Due date in ISO format (optional)",
            "labels": "List of label IDs (optional)",
        },
    },
    "search_cards": {
        "name": "search_cards",
        "description": "Search for cards in Trello",
        "parameters": {
            "query": "Search query",
            "board_id": "Optional board ID to limit search",
        },
    },
}
