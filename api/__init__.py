from fastapi import APIRouter

from . import itinerary, place, travel_time

router = APIRouter()
router.include_router(place.router)
router.include_router(itinerary.router)
router.include_router(travel_time.router)
