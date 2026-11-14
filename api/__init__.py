from fastapi import APIRouter

from . import itinerary, place

router = APIRouter()
router.include_router(place.router)
router.include_router(itinerary.router)
