import os
import json
import requests
from typing import Any


def _function(name: str, description: str, properties: dict) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }


_ID = {"type": "integer"}
_TIME = {
    "type": "string",
    "description": "Local date and time in YYYY-MM-DDTHH:MM:SS format, without timezone; optional fractional seconds.",
}
_RANGE = {"start_time": _TIME, "end_time": _TIME}

# Nullable fields are required in strict mode. Send null for unused fields.
tools = [
    {
        "type": "namespace",
        "name": "request_status",
        "description": "Markers indicating the final fulfillment status of the user's request.",
        "tools": [
            _function("completed", "Call this completion marker when the user's request has been fully fulfilled.", {}),
            _function(
                "unable_to_complete",
                "Call this marker when the user's request cannot be fulfilled.",
                {"reason": {"type": "string", "minLength": 1, "description": "The specific reason why the user's request cannot be fulfilled. Must be written in Korean."}},
            ),
        ],
    },
    {
        "type": "namespace",
        "name": "place",
        "description": "Search places by name and retrieve their category-specific information or coordinates.",
        "tools": [
            _function("search_places", "Find places whose names contain the given text.", {"name": {"type": "string"}}),
            _function(
                "get_place_info", 
                "Retrieve place information: transport required extra time after arrival/before departure, "
                "accommodation check-in/out, or opening hours and minimum visit duration.", 
                {"place_id": _ID}
            ),
            _function("get_place_location", "Retrieve a place's longitude and latitude.", {"place_id": _ID}),
        ],
    },
        {
        "type": "namespace",
        "name": "travel_time",
        "description": "Look up walking and public transit durations between places.",
        "tools": [
            _function("get_travel_time", "Retrieve walking and public transit travel times in minutes for a directed origin/destination pair. Durations may be null when unavailable.", {"origin_id": _ID, "destination_id": _ID}),
        ],
    },
    {
        "type": "namespace",
        "name": "itinerary",
        "description": "Create and retrieve itineraries, and create, reschedule, or delete their segments.",
        "tools": [
            _function("init_itinerary", "Create an itinerary. start_time must be before end_time.", _RANGE),
            _function("get_itinerary", "Retrieve itinerary segments sorted by start time.", {"itinerary_id": _ID}),
            _function(
                "create_segment",
                "Create a segment within the itinerary's time range without overlaps. "
                "STOP requires place_id and null transport_mode; LEG requires null place_id and transport_mode. "
                "start_time must be before end_time.",
                {
                    "itinerary_id": _ID,
                    "segment_type": {"type": "string", "enum": ["STOP", "LEG"]},
                    **_RANGE,
                    "place_id": {"type": ["integer", "null"]},
                    "transport_mode": {"type": ["string", "null"], "enum": ["WALK", "TRANSIT", None]},
                },
            ),
            _function(
                "update_segment",
                "Update a segment's start and end times within its itinerary's time range without overlaps. "
                "start_time must be before end_time.",
                {"itinerary_id": _ID, "segment_id": _ID, **_RANGE},
            ),
            _function("delete_segment", "Delete a segment belonging to the specified itinerary.", {"itinerary_id": _ID, "segment_id": _ID}),
        ],
    },
]

# namespace/name -> HTTP method, path template, JSON body fields
_ROUTES = {
    ("place", "search_places"): ("GET", "/place/search", ()),
    ("place", "get_place_info"): ("GET", "/place/{place_id}/information", ()),
    ("place", "get_place_location"): ("GET", "/place/{place_id}/location", ()),
    ("itinerary", "init_itinerary"): ("POST", "/itinerary/init", ("start_time", "end_time")),
    ("itinerary", "get_itinerary"): ("GET", "/itinerary/{itinerary_id}", ()),
    ("itinerary", "create_segment"): ("POST", "/itinerary/segment", ("itinerary_id", "segment_type", "start_time", "end_time", "place_id", "transport_mode")),
    ("itinerary", "update_segment"): ("PATCH", "/itinerary/{itinerary_id}/segment/{segment_id}", ("start_time", "end_time")),
    ("itinerary", "delete_segment"): ("DELETE", "/itinerary/{itinerary_id}/segment/{segment_id}", ()),
    ("travel_time", "get_travel_time"): ("GET", "/travel-time/{origin_id}/{destination_id}", ()),
}


def execute_tool(
    namespace: str,
    name: str,
    arguments: dict[str, Any],
    *,
    base_url: str | None = None,
    timeout: float = 30,
) -> Any:
    """Return a status marker or execute an API tool over HTTP.

    API errors retain their HTTP status and detail so the model can correct its
    request. Connection errors are raised to the caller (no automatic retries
    for mutations).
    """
    key = (namespace, name)
    if key not in _ROUTES and key not in {
        ("request_status", "completed"),
        ("request_status", "unable_to_complete"),
    }:
        raise ValueError(f"Unknown tool: {namespace}.{name}")
    
    definition = next(
        function
        for group in tools if group["name"] == namespace
        for function in group["tools"] if function["name"] == name
    )
    expected = set(definition["parameters"]["properties"])
    if set(arguments) != expected:
        raise ValueError(f"Expected arguments: {sorted(expected)}")

    if namespace == "request_status":
        if name == "completed":
            return {"status": "completed"}
        reason = arguments["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty Korean string")
        return {"status": "unable_to_complete", "reason": reason}

    method, template, body_fields = _ROUTES[key]
    # Only integer IDs are interpolated into URL paths.
    for field, value in arguments.items():
        if "{" + field + "}" in template and type(value) is not int:
            raise ValueError(f"{field} must be an integer")
    path = template.format(**arguments)
    url = (base_url or os.environ.get("TRIP_EDIT_API_URL", "http://127.0.0.1:8000")).rstrip("/") + path
    response = requests.request(
        method,
        url,
        params={"name": arguments["name"]} if key == ("place", "search_places") else None,
        json={field: arguments[field] for field in body_fields} if body_fields else None,
        timeout=timeout,
    )

    if response.status_code == 204:
        return {"status": "deleted"}
    
    try:
        result = response.json()
    except (ValueError, json.JSONDecodeError):
        result = {"detail": response.text}
    
    if not response.ok:
        return {"status_code": response.status_code, "error": result}
    return result
