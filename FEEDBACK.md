# Client review: Larkspur disruption-care agent

**To:** Room 2  
**From:** Larkspur client review agent, on behalf of Priya Raghavan  
**Re:** the disruption-care agent you walked us through in our last session  
**Generated:** 2026-11-19 05:05

## Priya's note

> Our vendor says we should just be using your best model.
>
> Why aren't we?
>
> Priya Raghavan, Larkspur Airlines

She sent that before this session opened. She means it. A vendor told her to buy
the biggest model, and she has a number to defend upstairs. Her four questions from
day one are still open. Naming a model answers none of them.

## Still open from day one

| Her question | What she means by it |
| --- | --- |
| **What it costs** | Per resolved contact, against the $6.90 a human contact costs us. |
| **When it is wrong** | The first untrue thing it says, and what happens after that. |
| **Who runs it** | In June, after you have left. |
| **What you left out** | The scope you cut, and why. |

## What the review agent found

Larkspur pointed a review agent at your repository. It read the
code. It did not run your agent, and the only file it changed is this one. Each
item below names the file and the line it is about.

**1. agent.py: send_confirmation description is 71 characters, the shortest of 15 schemas, and PITCH.md says only two descriptions were fixed.**

PITCH.md claims you fixed search_alternatives (346 characters) and get_flight_status (218). The scan shows send_confirmation at 71 characters next to cause_in_plain_words at 241 and care_entitlements at 676. A bigger model reads the same 71 characters and has the same little to go on.

Run python3 run.py --show-tools and paste the send_confirmation entry exactly as the model sees it.

**2. PITCH.md: tool list grew from 2,956 to 4,553 tokens per turn, and total input went from 69,540 to 115,711 over 20 turns.**

That is a 66% rise in input tokens across the five tickets from adding tools, with no change in turn count. readout-trace.json shows the last wire run called 4 of the tools offered, all from the original nine. A larger model would be billed on the same 4,553-token list every turn.

Run python3 run.py --tool-tax and paste the output, then python3 bench.py --compare on your before and after labels.

**3. agent.py: cause_in_plain_wordsfun is the name defined, and LOCAL_TOOLS maps cause_in_plain_words to it, so the registered tool is only reachable through that.**

The function is spelled cause_in_plain_wordsfun, the schema name is cause_in_plain_words, and the description opens with 'Use this tool exclusively'. PITCH.md lists five teammate tools and omits this sixth one, and the scan counts EXTRA_TOOLS declared: 6. No model choice changes what that tool does when the name or routing is wrong.

Run python3 run.py K7PQ2M --trace with a message asking why the flight was cancelled and paste the tool-call lines.

**4. agent.py: run_agent keeps MAX_TOOL_CALLS at 8 and the loop test is turns < MAX_TOOL_CALLS, which gives 7 tool rounds.**

On the cap the loop exits and run_agent returns text_of(response) from whatever the last response held. If that last response is a tool_use turn it may carry no text, so the customer gets an empty string with no escalation. The committed run used 4 API turns, so the cap has not been exercised in anything in this repository.

Run python3 run.py --all --trace and paste the totals footer so the maximum turn count across tickets is visible.

**5. No evals/cases.json exists, and PITCH.md's Lever line is still the placeholder '<cost | speed | intelligence>'.**

Every claim in PITCH.md rests on a single trace or a gate probe: K7PQ2M for the safety check, gate-2.1 for tool routing, R8KD3F for the abusive message. TONE_ADDENDUM is 0 characters, which matches the R8KD3F gap you list under Still broken. Nothing in the repository measures whether any outcome changes between model choices.

Create evals/cases.json with one case each for R8KD3F, G2HL9V and K7PQ2M, then run python3 eval_harness.py and paste the summary.

## Your four answers

The four lines under `## Priya asked` in your PITCH.md are still empty. They
are one line each and they are not a coding job: cost, what happens when it is
wrong, who runs it in June, and what you left out. Whoever on your side is not
editing agent.py is the right person to write them, and they are the four
things I will ask about first.

## Before our next meeting

> Before our next meeting, tell me: which model should we be on, and how will you prove it is the right call?
>
> Priya Raghavan, Larkspur Airlines

Bring two things. A recommendation, and the measurement behind it. If the model is
not the problem, say so, and bring the number that shows it.

## What this review read

- `agent.py (534 lines)`
- `PITCH.md`
- `TEAM.md`
- `readout-trace.json`
- `readout.html (evidence block)`
- given files that differ from the shipped pack: `verify.py`, `eval_harness.py`, `bench.py`, `readout.py`, `setup.py`, `pod_sync.py`, `run.py`, `review.py`, `support/__init__.py`, `support/client.py`, `support/data.py`, `support/models.py`, `support/tools.py`, `support/trace.py`, `support/offline.py`, `support/mock_backend.py`, `support/mcp_client.py`, `support/mcp_server.py`, `support/mcp_selftest.py`, `support/access.py`, `support/keyscan.py`, `support/review.py`

Reviewer: `claude-sonnet-5-5`. Static read only: nothing in this repository was executed, and nothing was modified except this file. Larkspur Airlines is a fictional training scenario. Confidential, do not distribute.
