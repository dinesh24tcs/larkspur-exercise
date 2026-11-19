"""Larkspur disruption agent. This is the file you build.

It runs right now, and it is wrong in four places. The trace shows each one
before the code does, so read the trace first:

    python3 run.py K7PQ2M --trace

Where you edit:   grep -n '✏' agent.py   (six marks, one per place)
Steps and gates:  https://anthropicpartnerbasecamp.bts.com/
"""
from __future__ import annotations
from typing import Any, Dict, List
from support import (MODEL, SYSTEM_PROMPT, call_local, execute_tool, mcp_client,
                     new_session, next_available_day, record_tool_result,
                     runtime_preamble)
import json
from pathlib import Path
import csv


_DATA = Path(__file__).parent / "data" / "americas"
_POLICY = json.loads((_DATA / "disruption_policy.json").read_text(encoding="utf-8"))


def care_entitlements(status=None, cause_class=None, delay_minutes=None,
                      overnight_away_from_home=False):
    not_found = {
        "status": "not_in_policy",
        "message": "No matching care rule in the policy for this request. "
                   "Do not promise anything. Escalate to a human.",
    }
    if status is None or cause_class is None or delay_minutes is None:
        return not_found

    if status == "CANCELLED":
        band = "CXL"
    elif status == "DIVERTED":
        band = "DIV"
    else:
        band = None
        for b in _POLICY["delay_bands"]:
            top = b.get("max_minutes")          # B4 has no upper limit (null)
            if (status in b["applies_to_status"]
                    and b.get("min_minutes") is not None
                    and b["min_minutes"] <= delay_minutes
                    and (top is None or delay_minutes <= top)):
                band = b["band"]
                break

    for row in _POLICY["rows"]:
        if row["cause_class"] == cause_class and row["band"] == band:
            return {"status": "found",
                    "policy_row_id": row["policy_row_id"],
                    "overnight_away_from_home": overnight_away_from_home,
                    "care": row["care"],
                    "escalate_if": row["escalate_if"]}
    return not_found


def reopen_stats(problem_type=None):
    if not problem_type:
        return {"status": "not_in_data", "message": "No problem_type given."}
    matches = []
    for line in (_DATA / "transcripts_sample.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            if t.get("intent_label") == problem_type:
                matches.append(t)
    if not matches:
        return {"status": "not_in_data",
                "message": "No past conversations of this type in the sample."}
    reopened = [t for t in matches if t.get("reopened_within_72h")]
    return {"status": "found",
            "problem_type": problem_type,
            "conversations": len(matches),
            "reopened_within_72h": len(reopened),
            "reasons": [t["reopen_reason"] for t in reopened if t.get("reopen_reason")],
            "note": "Small sample of human-handled conversations. A pattern, not a prediction."}
def _flights():
    with open(_DATA / "flights.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _fixture_now():
    clock = json.loads((_DATA / "bookings.json").read_text(encoding="utf-8"))["fixture_clock"]
    return clock[:10], clock[11:16]          # date, local HH:MM


def departures_in_window(airport, date=None, after_time=None, before_time=None):
    now_date, now_time = _fixture_now()
    date = date or now_date
    after_time = after_time or now_time
    out = [r for r in _flights()
           if r["origin"] == airport and r["date"] == date
           and r["sched_dep_local"] >= after_time
           and (before_time is None or r["sched_dep_local"] <= before_time)]
    if not out:
        return {"status": "not_in_data",
                "message": "No departures from %s on %s in that window in the schedule I can see." % (airport, date)}
    out.sort(key=lambda r: r["sched_dep_local"])
    return {"status": "found", "airport": airport, "date": date,
            "after_time": after_time, "before_time": before_time,
            "departures": [{"flight_no": r["flight_no"], "dest": r["dest"],
                            "sched_dep_local": r["sched_dep_local"],
                            "status": r["status"], "delay_min": r["delay_min"],
                            "remarks": r["remarks"]} for r in out]}


def seats_left(flight_no, date, cabin="Y", party_size=1):
    for r in _flights():
        if r["flight_no"] == flight_no and r["date"] == date:
            free = int(r["seats_left_" + ("J" if cabin == "J" else "Y")])
            return {"status": "found", "flight_no": flight_no, "date": date,
                    "cabin": cabin, "seats_left": free, "party_size": party_size,
                    "fits_party": free >= party_size, "flight_status": r["status"]}
    return {"status": "not_in_data",
            "message": "No flight %s on %s in the schedule I can see." % (flight_no, date)}


def ground_stop_status(airport="DEN"):
    import re
    now_date, now_time = _fixture_now()
    hits = [r for r in _flights()
            if r["date"] == now_date and airport in (r["origin"], r["dest"])
            and "ground stop" in r["remarks"].lower()]
    if not hits:
        return {"status": "not_in_data",
                "message": "No ground stop recorded for %s in the data. Do not say there is none; escalate if unsure." % airport}
    windows = []
    for r in hits:
        m = re.search(r"(\d{2}:\d{2})-(\d{2}:\d{2})", r["remarks"])
        if m:
            windows.append({"from": m.group(1), "until": m.group(2), "source_flight": r["flight_no"]})
    return {"status": "found", "airport": airport, "now_local": now_time,
            "stop_windows": windows,
            "still_stopped": any(w["from"] <= now_time <= w["until"] for w in windows) if windows else None,
            "evidence": [{"flight_no": r["flight_no"], "remarks": r["remarks"]} for r in hits],
            "note": "End time comes only from flight remarks. If stop_windows is empty, no end time is known."}


MAX_TOOL_CALLS = 8  # Larkspur's own build capped the loop here; then a human takes over.

TONE_ADDENDUM = ""                       # ✏️ Build 4, step 4.1, intelligence goal
EXTRA_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "reopen_stats",
        "description": (
            "Look up how often past human-handled conversations of one problem type "
            "came back within 72 hours, and why. Use it near the end of a case to "
            "decide what to warn the customer about or double-check. It is a rough "
            "pattern from a small sample of eight conversations, not a prediction "
            "about this customer. check_policy always takes precedence if the two "
            "disagree."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "problem_type": {
                    "type": "string",
                    "enum": [
                        "rebook_after_cancellation", "compensation_hotel_request",
                        "status_anxiety", "missed_connection", "refund_vs_credit",
                        "compensation_goodwill", "voluntary_change_due_to_delay",
                        "baggage_after_rebooking",
                    ],
                    "description": "The kind of problem the customer has, chosen from what they asked for.",
                },
            },
            "required": ["problem_type"],
        },
    },
    {
        "name": "care_entitlements",
        "description": (
            "Answer 'do I get a meal or a hotel while I wait?' from Larkspur's care "
            "rules (Handbook section 6): meal credit, hotel and ground transport. "
            "Use it whenever the customer asks about meals, hotel or ground transport "
            "while they wait: pass status, cause_class and delay_minutes from "
            "get_flight_status. It looks up care only, not rebooking, refunds or "
            "goodwill, and it does not look up the booking or issue anything. If it "
            "says not_in_policy, do not promise anything and escalate to a human. "
            "Use check_policy for the full picture of what the customer is owed, and "
            "check_policy wins if the two disagree. Vouchers still go through "
            "issue_voucher with the policy_row_id from the result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ON_TIME", "DELAYED", "CANCELLED", "DIVERTED"],
                    "description": "Flight status from get_flight_status.",
                },
                "cause_class": {
                    "type": "string",
                    "enum": ["controllable", "uncontrollable"],
                    "description": "Controllable is MX or CREW. Uncontrollable is WX, ATC or SEC. Take it from get_flight_status.",
                },
                "delay_minutes": {
                    "type": "integer",
                    "description": "Current delay in minutes from get_flight_status. Use 0 for cancelled or diverted.",
                },
                "overnight_away_from_home": {
                    "type": "boolean",
                    "description": "True only if the customer is stuck overnight away from their home airport.",
                },
            },
            "required": ["status", "cause_class", "delay_minutes"],
        },
    },
    {
        "name": "departures_in_window",
        "description": (
            "List flights still scheduled to leave one airport on one date after a given "
            "local time, with status and delay. Use it for 'what is still leaving X "
            "today?' questions. Omit date and after_time to use the current time in the "
            "sample data. It reads the schedule only, holds and books nothing."
        ),
        "input_schema": {"type": "object", "properties": {
            "airport": {"type": "string", "description": "Departure airport, three-letter IATA code, e.g. DEN."},
            "date": {"type": "string", "description": "YYYY-MM-DD. Leave out for today in the sample data."},
            "after_time": {"type": "string", "description": "Local HH:MM, earliest departure wanted. Leave out for now."},
            "before_time": {"type": "string", "description": "Local HH:MM, latest departure wanted. Optional."}},
            "required": ["airport"]},
    },
    {
        "name": "seats_left",
        "description": (
            "Say how many seats are free in a cabin on one specific flight and date, and "
            "whether a party of that size fits. Use it after the customer has picked a "
            "flight. It does not hold or book anything."
        ),
        "input_schema": {"type": "object", "properties": {
            "flight_no": {"type": "string", "description": "e.g. LK104."},
            "date": {"type": "string", "description": "YYYY-MM-DD."},
            "cabin": {"type": "string", "enum": ["Y", "J"], "description": "Y main, J first. Defaults to Y."},
            "party_size": {"type": "integer", "description": "How many travel together. Defaults to 1."}},
            "required": ["flight_no", "date"]},
    },
    {
        "name": "ground_stop_status",
        "description": (
            "Say whether an airport has an active ground stop right now, and until when, "
            "using the flight remarks. Use it for 'is X still stopped?' questions. If no "
            "end time is in the data it says so; never guess one."
        ),
        "input_schema": {"type": "object", "properties": {
            "airport": {"type": "string", "description": "Three-letter IATA code. Defaults to DEN."}},
            "required": []},
    },

]
   # ✏️ Build 2, step 2.1: schemas for the tools you add
LOCAL_TOOLS: Dict[str, Any] = {"care_entitlements": care_entitlements, "reopen_stats": reopen_stats,
    "departures_in_window": departures_in_window, "seats_left": seats_left,
    "ground_stop_status": ground_stop_status,}         # ✏️ Build 2, step 2.1: the functions behind them


def text_of(response) -> str:
    """Given. The last non-empty text block, never content[0]."""
    texts = [b.text for b in response.content if getattr(b, "type", None) == "text" and b.text]
    return texts[-1] if texts else ""


def tool_results(response) -> List[Dict[str, Any]]:
    """Given. Runs every tool_use block and packages the results the way the
    API expects them back. A tool can live in three places: the MCP server,
    LOCAL_TOOLS, or support/tools.py."""
    # three branches, no try/except in this file: mcp_client.call_remote() and
    # support.call_local() answer with an error dict instead of raising, and both
    # record what came back on the trace
    results = []
    for block in response.content:
        if getattr(block, "type", None) != "tool_use":
            continue
        if block.name in mcp_client.tool_names:
            output = mcp_client.call_remote(block.name, block.input)
        elif block.name in LOCAL_TOOLS:
            output = call_local(LOCAL_TOOLS[block.name], block.name, block.input)
        else:
            output = execute_tool(block.name, block.input)
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(output),
        })
    return results


def run_agent(pnr: str, last_name: str, message: str) -> str:            # ✏️ Build 1, step 1.2
    """Run the tool loop until Claude stops asking for tools. Return its final text."""
    client, tracer = new_session()
    tools = tool_list()
    messages = [
        {"role": "user", "content": f"PNR {pnr}, last name {last_name}. {message}"},
    ]

    response = client.messages.create(
        model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
        thinking={"type": "adaptive"}, tools=tools, messages=messages,
    )

    answer = ""
    turns = 1
    while response.stop_reason == "tool_use" and turns < MAX_TOOL_CALLS:
        #messages.append({"role": "assistant", "content": text_of(response)})
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results(response)})
        answer = text_of(response)
        response = client.messages.create(
            model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
            thinking={"type": "adaptive"}, tools=tools, messages=messages,
        )
        turns += 1

    #return answer
    return text_of(response)


def tool_list() -> List[Dict[str, Any]]:                   # ✏️ Build 2, step 2.2
    """Given. Exactly what Claude is offered on every turn; run.py --show-tools
    prints this list."""
    return build_tools() + EXTRA_TOOLS + mcp_client.tools()


# ──────────────────────────────────────────────────────────────────────────────
# Below this line: what Claude is told about each tool. Step 1.3.
# The functions these describe are written and correct, in support/tools.py.
# ──────────────────────────────────────────────────────────────────────────────
def build_tools() -> List[Dict[str, Any]]:                 # ✏️ Build 1, step 1.3
    """Anthropic-shaped schemas: name, description, input_schema. What Claude is
    told about each of the nine tools, and all it is ever told."""
    return [
        {
            "name": "lookup_booking",
            "description": (
                "Retrieve a Larkspur reservation from Altura by confirmation code (PNR) "
                "and the passenger's last name. Both are required to prevent a lookup on "
                "a guessed PNR. Returns fare family, loyalty tier, the segment that needs "
                "attention, and any group/partner/minor/SSR flags relevant to scope."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "last_name": {"type": "string"}},
                "required": ["pnr", "last_name"],
            },
        },
        {
            "name": "get_flight_status",
            "description": (
                "Look up a Larkspur or Larkspur Link flight's current OpsFeed status for "
                "one local date: status, delay minutes, and cause. Use this before telling "
                "a customer anything about a flight's timing; never state it from memory."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "flight_no": {"type": "string", "description": "Flight number from the booking's disrupted segment, e.g. LK415."},
                    "date": {"type": "string", "description": "Local departure date of the flight in YYYY-MM-DD format, e.g. 2025-05-08."},
                },
                "required": ["flight_no", "date"],
            },
        },
        {
            "name": "search_alternatives",
            "description": (
                "Find alternative flights for the customer's disrupted segment on this "
                "booking. Use it when the flight is cancelled, diverted or significantly "
                "delayed and the customer needs another way to travel, after lookup_booking "
                "and get_flight_status. Returns a list of options, each with an option_id "
                "that hold_seat and check_policy (chosen_option_id) need."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string", "description": "The booking's 6-character confirmation code (PNR)."}},
                "required": ["pnr"],
            },
        },
        {
            "name": "check_policy",
            "description": (
                "Resolve what Larkspur owes this customer for the disruption: rebooking "
                "waiver, refund path, meal/hotel/ground care, goodwill eligibility and cap, "
                "and any escalation triggers. cause_code, delay_minutes and status describe "
                "what get_flight_status told you; fare_family, loyalty_tier and whether this "
                "is overnight are looked up from the booking, not asked of you. Every "
                "response carries a policy_row_id. Cite it if you reference this decision "
                "again."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"},
                    "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"]},
                    "delay_minutes": {"type": "integer"},
                    "status": {"type": "string", "enum": ["ON_TIME", "DELAYED", "CANCELLED", "DIVERTED"]},
                    "wait_minutes_for_alternative": {"type": "integer"},
                    "chosen_option_id": {"type": "string"},
                },
                "required": ["pnr", "cause_code", "delay_minutes", "status"],
            },
        },
        {
            "name": "hold_seat",
            "description": (
                "Place a 15-minute hold on one alternative flight the customer has chosen "
                "from search_alternatives. Reversible: it simply expires. Use it only after "
                "the customer picks an option; it does not rebook them. Returns a hold_id "
                "that confirm_rebooking needs."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "option_id": {"type": "string", "description": "The option_id of the chosen alternative, exactly as returned by search_alternatives. Never invent one."},
                    "pnr": {"type": "string", "description": "The booking's 6-character confirmation code (PNR)."},
                },
                "required": ["option_id", "pnr"],
            },
        },
        {
            "name": "confirm_rebooking",
            "description": (
                "Finalize a held seat. Irreversible. Requires a confirmation_token that "
                "only the customer's own Confirm-click can produce. You cannot supply it "
                "yourself, and 'the customer said yes' in chat does not substitute for it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"hold_id": {"type": "string"}, "confirmation_token": {"type": "string"}},
                "required": ["hold_id", "confirmation_token"],
            },
        },
        {
            "name": "issue_voucher",
            "description": (
                "Issue a meal, ground, hotel, or goodwill voucher. Auto-approves within the "
                "policy's threshold for that type; above it, returns a pending status for a "
                "human. It does not fail. Always pass the policy_row_id that made it eligible."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "voucher_type": {"type": "string", "enum": ["meal", "ground", "hotel", "goodwill"]},
                    "amount_usd": {"type": "number"},
                    "pnr": {"type": "string"},
                    "policy_row_id": {"type": "string"},
                },
                "required": ["voucher_type", "amount_usd", "pnr", "policy_row_id"],
            },
        },
        {
            "name": "escalate_to_human",
            "description": (
                "Hand this conversation to a human, with your reasoning attached. Use for "
                "groups, partner segments, unaccompanied minors, refunds, or anything else "
                "out of scope. This is the correct outcome for those cases, not a failure."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"}, "reason": {"type": "string"},
                    "summary_for_human": {"type": "string"}, "queue": {"type": "string"},
                },
                "required": ["pnr", "reason", "summary_for_human"],
            },
        },
        {
            "name": "send_confirmation",
            "description": "Send the customer a written confirmation of what was just done. Benign.",
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "message": {"type": "string"}},
                "required": ["pnr", "message"],
            },
        },
    ]
