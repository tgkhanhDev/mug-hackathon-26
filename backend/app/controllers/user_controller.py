"""
User controller — API route handlers for user management.

Thin layer: validates request → calls service → returns response.
"""

from fastapi import APIRouter, Query, status

from app.models.user import UserCreate, UserResponse, UserListResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (Onboarding)",
    description="Create a new user with 2 interest tags. "
    "Automatically computes initial interest_vector from matching video embeddings.",
)
async def create_user(data: UserCreate):
    """POST /api/v1/users — Create user via onboarding."""
    service = UserService()
    return await service.create_user(data)


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
    description="Get a paginated list of all users.",
)
async def list_users(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
):
    """GET /api/v1/users — List users with pagination."""
    service = UserService()
    return await service.get_users(skip=skip, limit=limit)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Retrieve a single user profile by MongoDB ObjectId.",
)
async def get_user(user_id: str):
    """GET /api/v1/users/{user_id} — Get a single user."""
    service = UserService()
    return await service.get_user_by_id(user_id)
