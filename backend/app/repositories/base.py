"""
Base repository — generic async CRUD operations for MongoDB collections.

All specific repositories extend this class.
"""

from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection


class BaseRepository:
    """Generic async CRUD operations for a MongoDB collection."""

    def __init__(self, collection: AsyncIOMotorCollection):
        self._collection = collection

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return self._collection

    # ── Create ─────────────────────────────────────────────────

    async def insert_one(self, document: Dict[str, Any]) -> str:
        """Insert a single document. Returns the inserted _id as string."""
        result = await self._collection.insert_one(document)
        return str(result.inserted_id)

    async def insert_many(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Insert multiple documents. Returns list of inserted _ids as strings."""
        result = await self._collection.insert_many(documents)
        return [str(id_) for id_ in result.inserted_ids]

    # ── Read ───────────────────────────────────────────────────

    async def find_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """Find a single document by its ObjectId."""
        if not ObjectId.is_valid(id):
            return None
        doc = await self._collection.find_one({"_id": ObjectId(id)})
        return self._serialize(doc) if doc else None

    async def find_one(self, filter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single document matching the filter."""
        doc = await self._collection.find_one(filter)
        return self._serialize(doc) if doc else None

    async def find_many(
        self,
        filter: Dict[str, Any] = None,
        skip: int = 0,
        limit: int = 20,
        sort: List[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """Find multiple documents with pagination and optional sorting."""
        filter = filter or {}
        cursor = self._collection.find(filter).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        docs = await cursor.to_list(length=limit)
        return [self._serialize(doc) for doc in docs]

    # ── Update ─────────────────────────────────────────────────

    async def update_one(
        self, id: str, update: Dict[str, Any]
    ) -> bool:
        """Update a single document by ObjectId. Returns True if modified."""
        if not ObjectId.is_valid(id):
            return False
        result = await self._collection.update_one(
            {"_id": ObjectId(id)}, {"$set": update}
        )
        return result.modified_count > 0

    async def update_many(
        self, filter: Dict[str, Any], update: Dict[str, Any]
    ) -> int:
        """Update multiple documents. Returns count of modified documents."""
        result = await self._collection.update_many(filter, {"$set": update})
        return result.modified_count

    # ── Delete ─────────────────────────────────────────────────

    async def delete_one(self, id: str) -> bool:
        """Delete a single document by ObjectId. Returns True if deleted."""
        if not ObjectId.is_valid(id):
            return False
        result = await self._collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count > 0

    # ── Count ──────────────────────────────────────────────────

    async def count(self, filter: Dict[str, Any] = None) -> int:
        """Count documents matching the filter."""
        filter = filter or {}
        return await self._collection.count_documents(filter)

    # ── Aggregation ────────────────────────────────────────────

    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run an aggregation pipeline."""
        cursor = self._collection.aggregate(pipeline)
        docs = await cursor.to_list(length=None)
        return [self._serialize(doc) for doc in docs]

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MongoDB _id (ObjectId) to string 'id' field."""
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        return doc
