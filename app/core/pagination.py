from typing import Any, Dict, List, Optional


def paginate(
    items: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 10,
) -> Dict[str, Any]:
    """
    Paginate a list of items.
    Args:
        items: The list of items to paginate.
        page: The current page number.
        page_size: The number of items per page.
    Returns:
        A dictionary containing paginated results and metadata.
    """
    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = items[start:end]

    return {
        "items": paginated_items,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        },
    }
