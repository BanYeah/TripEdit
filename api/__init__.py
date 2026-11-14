from fastapi import APIRouter

from . import items, place

router = APIRouter()
router.include_router(place.router)
router.include_router(items.router)
