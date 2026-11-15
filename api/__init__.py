from fastapi import APIRouter

from . import place, travel_time, itinerary

router = APIRouter()
router.include_router(place.router)
router.include_router(travel_time.router)
router.include_router(itinerary.router)
