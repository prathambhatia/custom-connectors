---
name: fathom-connector
description: ALWAYS use this instead of the Fathom MCP whenever Fathom or a recorded meeting is mentioned — list recent meetings, find a meeting by title/attendee/company/date, get its summary, full transcript or action items, search what was said across calls — via the Fathom REST API with curl. Triggers on "fathom", "my last meeting", "that call with X", "meeting notes", "transcript of", "what did X say", "action items from", "summarise the call". Faster and lighter on context than the MCP. Sets itself up on first use.
user-invocable: true
argument-hint: "which meeting (title / person / date) and what you want from it"
---

# Fathom via REST (no MCP)

Calls `https://api.fathom.ai/external/v1` directly with your own API key. Only sees meetings you
recorded or that were shared with you.

## First run: setup (do this automatically)

1. Check: `security find-generic-password -s fathom-api-key -w >/dev/null 2>&1 && echo ok`.
2. If missing (or any call returns 401):
   First open the page for them: `open "https://fathom.video/customize#api-access-header"` (opens in their default browser; if they're
   logged out they see that service's login page first, and may need to open the link again after). Then ask with this one line, optionally starting with "I've opened the … page in your browser.":
   > Please give your Fathom API key from here: https://fathom.video/customize#api-access-header
3. Save it, then test (expect HTTP 200):
   ```bash
   security add-generic-password -a "$USER" -s fathom-api-key -l "Fathom API Key" -T /usr/bin/security -w "<KEY>" -U
   curl -s -o /dev/null -w '%{http_code}\n' -H "X-Api-Key: $(security find-generic-password -s fathom-api-key -w)" https://api.fathom.ai/external/v1/meetings
   ```
   Don't echo the key back in chat.

## Auth

Send the key as **`X-Api-Key`**. `Authorization: Bearer` returns 401.

```bash
fathom() { curl -s -H "X-Api-Key: $(security find-generic-password -s fathom-api-key -w)" \
  "https://api.fathom.ai/external/v1/$1"; }
# usage: fathom 'meetings?created_after=2026-09-25T00:00:00Z' | jq .
```

That helper expands to full URLs like `https://api.fathom.ai/external/v1/meetings`. **There is no `/my/` prefix** (`/v1/my/meetings` is a 404). Other paths: `/v1/recordings/<id>/summary`, `/v1/recordings/<id>/transcript`, `/v1/teams`, `/v1/team_members`, `/v1/meeting_types`.

**Copy the commands below exactly; never guess an endpoint path.** If a call returns 404, the path is wrong: recheck this file, don't try variations.


Paste it into each Bash call (shell state doesn't persist). Never print the key. On 401, rerun setup.

**Save responses to a file, don't pipe through `echo`.** Transcripts and summaries contain `\n`;
zsh's `echo` expands them and jq fails with "control characters must be escaped".

## Quirks that silently mislead

- **Always 10 meetings per page.** `limit=` is ignored. Use `next_cursor` (pass back as `cursor=`).
  Null cursor means last page. A "last 30 meetings" answer from one page is wrong.
- **No search or get-by-id for meetings.** Find a meeting by listing (narrow with dates/filters)
  and filtering locally with jq.
- **List responses omit content by default**: `transcript`, `default_summary`, `action_items` are
  `null` unless you add `include_transcript=true`, `include_summary=true`, `include_action_items=true`.
  Including transcripts makes each page large (one call had 699 lines), so only add it when needed.
- Array filters need brackets, URL-encoded: `calendar_invitees_domains%5B%5D=acme.com`.
- `teams` and `team_members` are empty unless your Fathom account has teams.
- Rate limit **60 calls/min** (`ratelimit-remaining` header). Tested 01/10/2026: call 58 of a burst got
  HTTP 429 with `retry-after: 20`; after sleeping 20s the next call was 200. On 429, `sleep` the
  `retry-after` value and retry once.
- **Unknown query params are silently ignored**: a misspelt filter returns the unfiltered list with
  no error. If a filter's results look unfiltered, check the param name against the table, don't trust it.
- `recording_id` (e.g. `188628610`) is what the per-recording endpoints take. `url` / `share_url`
  are the links to give the user.

## Operations

| Task | Call |
|---|---|
| Recent meetings | `fathom meetings > m.json` (newest first, 10) |
| By date range | `fathom 'meetings?created_after=2026-09-01T00:00:00Z&created_before=2026-09-05T00:00:00Z'` |
| By attendee company | `fathom 'meetings?calendar_invitees_domains%5B%5D=acme.com'` |
| By attendee email | **No API filter exists** (any guessed param is silently ignored). Use `fathom_all`, then `jq 'select([.calendar_invitees[].email]\|index("x@y.com"))'` |
| By who recorded | `fathom 'meetings?recorded_by%5B%5D=you@company.com'` |
| Internal vs external | `fathom 'meetings?calendar_invitees_domains_type=one_or_more_external'` (or `only_internal`). Impromptu calls (no invite) come back as **external** even with only you invited, so don't trust this for them |
| Highlights | add `include_highlights=true` |
| By meeting type | `fathom meeting_types` for valid names, then `meetings?meeting_type=<name>`; an unknown name returns an empty list |
| Summary | `fathom recordings/$RID/summary > s.json; jq -r .summary.markdown_formatted s.json` |
| Transcript | `fathom recordings/$RID/transcript > t.json; jq -r '.transcript[]\|"[\(.timestamp)] \(.speaker.display_name): \(.text)"' t.json` |
| Action items | `fathom "meetings?include_action_items=true&created_after=…"` then `.items[]\|select(.recording_id==$RID)\|.action_items[]` |
| Teams / members | `fathom teams`, `fathom team_members` |

Action item fields: `description`, `completed`, `assignee.name`, `recording_timestamp`,
`recording_playback_url` (jumps to that moment, give it to the user).

### Paging helper (find a meeting, or search across many)

```bash
fathom_all() { local q=$1 max=${2:-5} cur="" n=0 pg=$(mktemp); : > fa.jsonl   # q = query string, max = pages
  while [ $n -lt $max ]; do
    fathom "meetings?${q}${cur:+&cursor=$cur}" > $pg
    jq -e .items $pg >/dev/null 2>&1 || { echo "page $n not JSON (rate limit?): $(head -c 150 $pg)"; sleep 20; continue; }
    jq -c '.items[]' $pg >> fa.jsonl
    cur=$(jq -r '.next_cursor // empty' $pg); n=$((n+1)); [ -z "$cur" ] && break; done
  rm -f $pg; echo "$(wc -l < fa.jsonl | tr -d ' ') meetings in fa.jsonl"; }
# run it in your own scratch folder (cd to a fresh dir first), so parallel sessions don't share fa.jsonl
# find by title or attendee name:
fathom_all 'created_after=2026-09-01T00:00:00Z' 5
jq -r 'select((.title+" "+([.calendar_invitees[]?.name]|join(" ")))|ascii_downcase|contains("john"))|"\(.recording_id) \(.recording_start_time) \(.title)"' fa.jsonl
# search what was said (pulls transcripts, keep the date window tight):
fathom_all 'include_transcript=true&created_after=2026-09-25T00:00:00Z' 3
jq -r '. as $m|.transcript[]?|select(.text|ascii_downcase|contains("pricing"))|"\($m.title) [\(.timestamp)] \(.speaker.display_name): \(.text)"' fa.jsonl
```

## Presenting results

- Times are UTC ISO. Show IST 12-hour: `TZ=Asia/Kolkata date -r $(date -j -u -f '%Y-%m-%dT%H:%M:%SZ' 2026-10-01T13:20:35Z +%s) '+%b %d %I:%M %p IST'` → Oct 01 06:50 PM IST (strip fractional seconds first). Don't format in the same `date -u` call: `-u` forces UTC output and you get 01:20 PM, silently wrong.
- Many titles are "Impromptu Google Meet Meeting"; identify those by date + `calendar_invitees` names.
- Lead with the summary or the answer; quote transcript lines with speaker and timestamp, plus the
  `url` so the user can open the call. Don't paste a whole transcript unless asked.
- Transcript speaker names come from Google Meet display names and can be wrong; say so if it matters.

**How to apply:** use this skill for every Fathom request, even when the Fathom MCP is connected.
Don't call the MCP's tools.
