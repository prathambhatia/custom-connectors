---
name: clickup-connector
description: ALWAYS use this instead of the ClickUp MCP whenever ClickUp is mentioned or a ClickUp task, list, ticket, comment, tag, status, assignee, checklist, attachment, custom field or time entry is involved — create, read, update, search, comment, tag, delete — via the ClickUp REST API with curl and your own token. Triggers on "clickup", "ticket", "task", "move it to qa", "comment on the ticket", "what's on my board". Faster and lighter on context than the MCP. Sets itself up on first use.
user-invocable: true
argument-hint: "task / list / what to do"
---

# ClickUp via REST (no MCP)

Calls `https://api.clickup.com/api/v2` directly with your own personal token, so everything is done
as you (the MCP may be connected as someone else, and its tool list is huge).

## First run: setup (do this automatically)

1. Check: `security find-generic-password -s clickup-api-token -w >/dev/null 2>&1 && echo ok`.
2. If missing, or a call returns an `OAUTH_` error code (e.g. `{"err":"Oauth token not found","ECODE":"OAUTH_019"}`, a stale token):
   First open the page for them: `open "https://app.clickup.com/settings/apps"` (opens in their default browser; if they're
   logged out they see that service's login page first, and may need to open the link again after). Then ask with this one line, optionally starting with "I've opened the … page in your browser.":
   > Please give your ClickUp personal access token from here: https://app.clickup.com/settings/apps (API Token, Generate)
3. **Test the token first, save only if it works.** Put what they pasted into `T` (single quotes),
   never echo it back:
   ```bash
   T='<PASTED>'; code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: $T" https://api.clickup.com/api/v2/user)
   if [ "$code" = 200 ]; then security add-generic-password -a "$USER" -s clickup-api-token -l "ClickUp API Token" -T /usr/bin/security -w "$T" -U && echo SAVED
   else echo "REJECTED (HTTP $code)"; fi; unset T
   ```
   On `REJECTED`, nothing is saved. Tell them in one line and ask again:
   > That token didn't work (HTTP <code>). Please copy it again from: https://app.clickup.com/settings/apps

   Common causes: a partial copy, extra spaces, or a token from another account. On `SAVED`, carry on
   with what they originally asked.
4. Then `cu GET user` (their name) and `cu GET team` (their workspaces). Remember their user id and the
   workspace id they work in for the rest of the session.

## Helper

Sent as the raw token in `Authorization`, **no `Bearer`**.

```bash
cu() { local m=$1 p=$2; shift 2; curl -s -X $m -H "Authorization: $(security find-generic-password -s clickup-api-token -w)" \
  -H "Content-Type: application/json" "https://api.clickup.com/api/v2/$p" "$@"; }
# usage: cu GET task/abc123 > t.json; jq . t.json
```

**Copy the commands below exactly; never guess an endpoint path.** If a call returns 404, the path is wrong: recheck this file, don't try variations.


Paste into each Bash call. Save responses to files and jq them; don't pipe JSON through zsh `echo`
(it expands `
` and jq fails). Errors come back as `{"err":…,"ECODE":…}`, check for them.

## Finding ids

Never guess ids. `cu GET team` → workspaces (`$TEAM`); `cu GET "team/$TEAM/space?archived=false"` →
spaces; `cu GET "space/$SP/folder?archived=false"` and `cu GET "space/$SP/list?archived=false"` →
lists (`$L`); a list's people: `cu GET list/$L/member`. If the user names a list, find it by name
across spaces; if they paste a ClickUp URL, the list id is the number after `/li/` and a task id is
after `/t/`.

## Operations

| Task | Call |
|---|---|
| Who am I | `cu GET user` |
| Workspaces / spaces / lists | `cu GET team`; `cu GET "team/$TEAM/space?archived=false"`; `cu GET "space/$SP/list?archived=false"` |
| List details + statuses | `cu GET list/$L` → `.statuses[].status` |
| List members (find a user id) | `cu GET list/$L/member` → `.members[]\|select((.username//"")\|test("name";"i"))` (`team/$TEAM/member` is 404) |
| Tasks in a list | `cu GET "list/$L/task?include_closed=true&order_by=created&subtasks=true&page=0"` (100 per page; bump `page`) |
| Search across workspace | `cu GET "team/$TEAM/task?assignees%5B%5D=$ME&statuses%5B%5D=in%20progress&include_closed=true"` (also `tags%5B%5D=`, `list_ids%5B%5D=`, `date_created_gt=<ms>`) |
| Get task | `cu GET task/$T` |
| Create task | `cu POST list/$L/task -d '{"name":"…","markdown_description":"…","assignees":[$ME],"status":"backlog","time_estimate":900000,"priority":4}'` |
| Subtask | same create with `"parent":"$T"` |
| Update | `cu PUT task/$T -d '{"status":"qa","priority":2,"time_estimate":1200000}'` |
| Delete task | `cu DELETE task/$T` → HTTP 204, irreversible, confirm first |
| Add / remove tag | `cu POST task/$T/tag/<tag>`, `cu DELETE task/$T/tag/<tag>` (empty body; read back to verify) |
| Space tags | `cu GET space/$SP/tag` |
| Create / recolour / delete space tag | `cu POST space/$SP/tag -d '{"tag":{"name":"pos","tag_fg":"#FFFFFF","tag_bg":"#2ECC71"}}'`; recolour: same body with `PUT space/$SP/tag/<name>` (stays on every task that has it); delete: `DELETE space/$SP/tag/<name>` with the same body. Check `GET` first so you don't duplicate a tag |
| Comment: add / list / edit / delete | `cu POST task/$T/comment -d '{"comment_text":"…","notify_all":false}'`; `cu GET task/$T/comment`; `cu PUT comment/$CID -d '{"comment_text":"…"}'`; `cu DELETE comment/$CID` |
| Checklist + item | `cu POST task/$T/checklist -d '{"name":"…"}'` → `.checklist.id`; `cu POST checklist/$CK/checklist_item -d '{"name":"…"}'` |
| Attachment | `curl -s -X POST -H "Authorization: $(security find-generic-password -s clickup-api-token -w)" -F "attachment=@file.pdf" https://api.clickup.com/api/v2/task/$T/attachment` (multipart, no JSON header) |
| Custom fields | `cu GET list/$L/field`; set: `cu POST task/$T/field/$FID -d '{"value":"…"}'` |
| Time entry: add / list / delete | `cu POST team/$TEAM/time_entries -d '{"tid":"'$T'","start":<ms>,"duration":<ms>}'`; `cu GET "team/$TEAM/time_entries?task_id=$T"`; `cu DELETE team/$TEAM/time_entries/$ID` |

## Units and traps

- **`time_estimate`, `duration`, `start`, `date_*` are milliseconds.** 15 min = `900000`. ClickUp counts
  1 day = 8 hours. Read back and divide by 60000.
- Priority: `1` urgent, `2` high, `3` normal, `4` low.
- Status must match a list status exactly (lowercase as shown by `GET list/$L`).
- `tags` in the create payload is unreliable; create, then `POST …/tag/<name>`.
- Time entries can fail with `TIMEENTRY_064` on plans that cap time tracking; then set `time_estimate` instead.
- Never send a `statuses` array to `PUT list/$L`; there's no reorder endpoint and it can drop statuses.
- Show `task.url` to the user after any create or update. Convert `date_*` ms to IST:
  `date -r $((MS/1000)) '+%b %d %I:%M %p'`.

**How to apply:** use this skill for every ClickUp request, even when a ClickUp MCP is connected. Don't call `clickup_*` MCP tools. Ask before deleting anything; deletes are irreversible.
