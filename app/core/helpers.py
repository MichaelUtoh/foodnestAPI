from bson import ObjectId
from typing import Any


def transform_mongo_data(data: Any) -> Any:
    """
    Recursively transforms MongoDB data, converting ObjectId to string and renaming _id to id.
    """
    if isinstance(data, list):
        return [transform_mongo_data(item) for item in data]
    if isinstance(data, dict):
        transformed = {key: transform_mongo_data(value) for key, value in data.items()}
        if "_id" in transformed:
            transformed["id"] = str(transformed.pop("_id"))  # Rename _id to id
        return transformed
    if isinstance(data, ObjectId):
        return str(data)
    return data
