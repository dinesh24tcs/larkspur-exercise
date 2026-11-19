# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: A support agent for disrupted flights, with Larkspur's nine tools (we fixed the search_alternatives and get_flight_status descriptions), five tools written by teammates (reopen_stats, care_entitlements, departures_in_window, seats_left, ground_stop_status), and next_available_day and fare_rules served over MCP.
Does: It looks up the booking, checks the flight status, applies the disruption policy, lists alternative flights, quotes the Handbook rule behind a decision, and hands a group booking to a person (G2HL9V went to the Group Desk).
Number: 69,540 to 115,711 tokens in, total of the five tickets, after adding seven tools (20 turns both times). The tool list alone grew from 2,956 to 4,553 tokens on every turn.
Safety check: It never confirms a rebooking without the customer: in the K7PQ2M trace it offered flights and told the customer to click Confirm themselves, and never called confirm_rebooking.
Next: Make next_available_day count the whole party, not one passenger, so it never promises room to a group that does not fit.
Still broken: An abusive, threatening message (R8KD3F) gets the same calm, normal answer as any other ticket, with no check on tone or escalation. Also, in the gate-2.1 probe none of the five teammate tools was chosen on the next_available_day question, so their routing is unproven.
Lever: intelligence

## Priya asked

Costs:
Wrong:
Runs it:
Left out:
