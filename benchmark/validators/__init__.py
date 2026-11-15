from importlib import import_module

from datetime import datetime, timedelta
from database import connect

def validate(scenario_num, turn_num, itinerary_id, request_status):
    module_name = f".{scenario_num:03d}"
    try:
        module = import_module(module_name, package=__package__)
    except ModuleNotFoundError as error:
        if error.name == f"{__package__}{module_name}":
            raise ValueError(f"Unsupported scenario: {scenario_num}") from error
        raise

    override_provider = getattr(module, "travel_time_overrides", None)
    overrides = override_provider(turn_num) if override_provider is not None else None
    success, reason = validate_common(itinerary_id, travel_time_overrides=overrides)
    if not success:
        return success, reason

    validator = getattr(module, "validator")
    return validator(turn_num, itinerary_id, request_status)


def validate_common(itinerary_id, *, travel_time_overrides=None):
    database = connect()

    try:
        itinerary = database.execute(
            "SELECT 1 FROM itineraries WHERE itinerary_id = ?",
            (itinerary_id,),
        ).fetchone()
        if itinerary is None:
            return False, "Itinerary not found."

        segments = database.execute(
            "SELECT * FROM segments WHERE itinerary_id = ? "
            "ORDER BY start_time ASC, segment_id ASC",
            (itinerary_id,),
        ).fetchall()
        if not segments:
            return False, "Itinerary has no segments."

        for index, segment in enumerate(segments):
            expected = "STOP" if index % 2 == 0 else "LEG"
            if segment["segment_type"] != expected:
                return False, "Segments must alternate STOP and LEG."
        
        if segments[-1]["segment_type"] != "STOP":
            return False, "Itinerary must end with a STOP."

        for index in range(1, len(segments), 2):
            leg = segments[index]
            origin = segments[index - 1]["place_id"]
            destination = segments[index + 1]["place_id"]

            mode = leg["transport_mode"]
            minutes = (travel_time_overrides or {}).get((origin, destination, mode))
            if minutes is None:
                travel_time = database.execute(
                    "SELECT walk_minutes, transit_minutes FROM travel_times "
                    "WHERE origin_id = ? AND destination_id = ?",
                    (origin, destination),
                ).fetchone()
                minutes = (
                    travel_time[f"{mode.lower()}_minutes"]
                    if travel_time is not None
                    else None
                )
            if minutes is None:
                return False, f"Travel time unavailable for LEG {leg['segment_id']}."

            duration = datetime.fromisoformat(leg["end_time"]) - datetime.fromisoformat(
                leg["start_time"]
            )
            if duration < timedelta(minutes=minutes):
                return (
                    False,
                    f"LEG {leg['segment_id']} duration must be at least {minutes} minutes.",
                )

        return True, ""
    
    finally:
        database.close()
