from pathlib import Path
from dotenv import load_dotenv

import time
import json
from tqdm import tqdm
from typing import Any
from datetime import datetime

from openai import OpenAI
from tools import tools, execute_tool
from benchmark.validators import validate

load_dotenv(Path(__file__).resolve().parent / ".env")

SYSTEM_PROMPT = """
You are a travel itinerary agent that incrementally creates and modifies itineraries in response to the user's requests across multiple conversation turns.

Design principles:
- An itinerary does not need to be complete from the outset. Partial itineraries are valid.
- The user alone chooses which places to visit. Do not add places the user has not requested.
- Distinguish constraints explicitly stated by the user from decisions or assumptions made by the agent.

Default constraints:
- Place categories are transports, accommodations, restaurants, cafes, and attractions.
- Transports are entry and exit points for the travel region and serve as the itinerary's starting and ending points. Examples include train stations, bus terminals, airports, and ferry terminals.
- Stay at an accommodation for at least the entire overnight period from 00:00 to 06:00 each day within the trip.
- Schedule restaurant visits during lunch (11:00-15:00) or dinner (17:00-21:00), with at most one restaurant per meal period per date. Do not plan breakfast.
- Schedule cafe and attraction visits within their opening hours.
- Unless the user specifies otherwise, allow at least the transport's required extra time after arrival and before departure.
- Unless the user specifies a stay duration, allow at least the place's default minimum visit duration.
- Visit times and stay durations explicitly specified by the user take precedence over the default constraints for each place category.
"""

INSTRUCTIONS = """
Fulfill the user's request using the available tools.
- After fully fulfilling the request, call request_status.completed.
- If the request cannot be fulfilled, call request_status.unable_to_complete with a specific reason written in Korean.
"""


def evaluate(
    scenario_path: Path,
    *,
    model: str = "gpt-6-luna",
    base_url: str | None = None,
    max_rounds: int = 20,
    process_bar: tqdm | None = None,
) -> Any:
    scenario_num, turn_num = int(scenario_path.stem), 1
    itinerary_id = None

    results = []  # {turn: 1, success: 1, response_time: 100}

    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")

    client = OpenAI()
    input = [{"role": "system", "content": SYSTEM_PROMPT}]

    with scenario_path.open(encoding="utf-8") as file:
        for line in file:
            line = line.rstrip("\r\n")
            input.append({"role": "user", "content": line})

            if process_bar is not None:
                process_bar.set_postfix_str(f"turn={turn_num}")

            request_status = None

            start = time.perf_counter()
            for _ in range(max_rounds):
                response = client.responses.create(
                    model=model,
                    instructions=INSTRUCTIONS,
                    tools=tools,
                    input=input,
                    parallel_tool_calls=True,
                    tool_choice="required",
                )
                input.extend(response.output)

                calls = [item for item in response.output if item.type == "function_call"]
                for call in calls:
                    arguments = json.loads(call.arguments)
                    if not isinstance(arguments, dict):
                        input.append({
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps({"error": "Tool arguments must be a JSON object"}, ensure_ascii=False),
                        })
                        continue

                    result = execute_tool(
                        call.namespace, call.name, arguments, base_url=base_url,
                    )
                    input.append({
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    })

                    if (
                        call.namespace == "itinerary" 
                        and call.name == "init_itinerary"
                        and isinstance(result, dict) 
                        and "itinerary_id" in result
                    ):
                        itinerary_id = result["itinerary_id"]

                    if call.namespace == "request_status":
                        request_status = call.name  # completed | unable_to_complete

                if request_status is not None:
                    break

            if itinerary_id is None:
                raise ValueError("Itinerary has not been initialized")

            if request_status is None:
                raise RuntimeError(f"No final response within {max_rounds} model requests")

            end = time.perf_counter()
            elapsed_minutes = round((end - start) / 60, 2)

            # Validate the itinerary
            success, reason = validate(scenario_num, turn_num, itinerary_id, request_status)

            results.append({"turn": turn_num, "success": success, "reason": reason, "response_time": elapsed_minutes})
            turn_num += 1

    # Calculate total travel time in minutes
    segments = execute_tool(
        "itinerary", "get_itinerary", {"itinerary_id": itinerary_id},
        base_url=base_url,
    )
    if not isinstance(segments, list):
        raise RuntimeError(f"Failed to retrieve itinerary {itinerary_id}")

    total_travel_time = sum(
        (
            datetime.fromisoformat(segment["end_time"])
            - datetime.fromisoformat(segment["start_time"])
        ).total_seconds() / 60
        for segment in segments
        if segment["segment_type"] == "LEG"
    )
    total_travel_time = round(total_travel_time, 2)
    return results, total_travel_time


def print_metrics(result_path: Path):
    with result_path.open(encoding="utf-8") as file:
        scenarios = [json.loads(line) for line in file if line.strip()]
    if not scenarios:
        print("No evaluation results available.")
        return

    if any(not scenario["result"] for scenario in scenarios):
        raise ValueError("Each scenario must contain at least one turn result")

    turns = [turn for scenario in scenarios for turn in scenario["result"]]
    all_turn_passed = [
        scenario for scenario in scenarios
        if all(turn["success"] for turn in scenario["result"])
    ]
    turn_success_rate = sum(bool(turn["success"]) for turn in turns) / len(turns)
    final_pass_rate = sum(
        bool(max(scenario["result"], key=lambda turn: turn["turn"])["success"])
        for scenario in scenarios
    ) / len(scenarios)
    all_turn_pass_rate = len(all_turn_passed) / len(scenarios)
    response_time = sum(turn["response_time"] for turn in turns) / len(turns)

    print(f"Turn Success Rate: {turn_success_rate:.2%}")
    print(f"Final Pass Rate: {final_pass_rate:.2%}")
    print(f"All-turn Pass Rate: {all_turn_pass_rate:.2%}")
    if all_turn_passed:
        travel_time = sum(scenario["total_travel_time"] for scenario in all_turn_passed) / len(all_turn_passed)
        print(f"Average Total Travel Time (all-turn passed): {travel_time:.2f} min")
    else:
        print("Average Total Travel Time (all-turn passed): N/A")
    print(f"Average Response Time: {response_time:.2f} min")


if __name__ == "__main__":
    SCENARIO_DIR = Path(__file__).resolve().parent / "benchmark" / "scenarios"
    RESULT_PATH = Path(__file__).resolve().parent / "result.jsonl"

    completed_scenarios = set()
    if RESULT_PATH.exists():
        with RESULT_PATH.open(encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    completed_scenarios.add(json.loads(line)["scenario"])

    with RESULT_PATH.open("a", encoding="utf-8") as file:
        paths = sorted(SCENARIO_DIR.glob("*.txt"))
        process_bar = tqdm(paths, desc="Evaluating Scenarios")
        for path in process_bar:
            scenario_num = int(path.stem)
            if scenario_num in completed_scenarios:
                continue

            result, total_travel_time = evaluate(scenario_path=path, process_bar=process_bar)

            file.write(json.dumps({
                "scenario": scenario_num,
                "result": result,
                "total_travel_time": total_travel_time,
            }, ensure_ascii=False) + "\n")
            file.flush()

            completed_scenarios.add(scenario_num)

    process_bar.close()
    
    print_metrics(RESULT_PATH)
