---
name: google
description: Use only after the one-time Google setup below is done (Keychain item google-refresh-token-personal exists); if it is missing, show the setup steps and stop. Then use this instead of the claude.ai Google Drive, Gmail and Google Calendar MCPs whenever Google Workspace is involved — upload to drive, download a drive file, find a file or folder, replace a file in place, trash a file, read or write a google doc, google sheet or slides deck, read my email, search gmail, make a gmail draft, list calendar events, add a calendar event, send an email, fill a doc table, format a sheet, google tasks — via the Google REST APIs with curl and your own OAuth token. Triggers on "google drive", "upload to drive", "drive folder", "gmail", "read my email", "google doc", "google sheet", "slides", "calendar", "my tasks".
user-invocable: true
argument-hint: "what to do (upload / read mail / doc / sheet / calendar)"
---

# Google via REST (no MCP)

Calls Google's REST APIs directly with one all-scopes token (Drive, Docs, Sheets, Slides, Gmail, Calendar, Tasks) for the
Google account the user signs in with. Every call below was run live against a real account.

**Long recipes (Docs editing and tables, Sheets formatting, Slides editing, Gmail send/reply/attachments/labels) are in
`${CLAUDE_PLUGIN_ROOT}/skills/google/editing.md`: Read that file before any task that edits a doc, sheet or deck or sends mail.**

## Step 1: first-run gate (always do this first)

```bash
for s in google-oauth-client-id google-oauth-client-secret google-refresh-token-personal; do security find-generic-password -s $s >/dev/null 2>&1 && echo "$s ok" || echo "$s MISSING"; done
```

If any line says MISSING, **STOP. Do not call any Google API and do not use another Google MCP.** Do not do the setup for
them. Show this one-time setup and wait:

1. In https://console.cloud.google.com create a project (or pick one).
2. APIs & Services, Library: enable the Google Drive, Docs, Sheets, Slides, Gmail, Calendar and Tasks APIs.
3. APIs & Services, OAuth consent screen: set it up. **Google Workspace accounts: choose "Internal"** (tokens do not expire).
   **Personal Gmail accounts: choose "External" and add yourself as a test user; while the app is in Testing mode the login
   expires every 7 days** and step 6 has to be repeated.
4. APIs & Services, Credentials: Create credentials, OAuth client ID, application type **Desktop app**. Copy the client id and secret.
5. In your own terminal (not in this chat; never paste secrets into chat) run these two, replacing the placeholders with the values from step 4:
   ```
   security add-generic-password -a "$USER" -s google-oauth-client-id -w '<CLIENT_ID>' -U
   security add-generic-password -a "$USER" -s google-oauth-client-secret -w '<CLIENT_SECRET>' -U
   ```
6. Run `! python3 "${CLAUDE_PLUGIN_ROOT}/skills/google/google_auth.py" login`, a browser opens, click **Allow**.
   This saves `google-refresh-token-personal` to the Keychain.

If the gate passes but the token command prints `invalid_grant` or `token endpoint error`, the login was revoked or expired:
tell the user to repeat step 6 only. Never ask them to paste secrets. Never print the token or any Keychain value.

## Helper

```bash
T=$(python3 "${CLAUDE_PLUGIN_ROOT}/skills/google/google_auth.py" token)   # 1-hour token; fetch once per Bash call
g() { local m=$1 u=$2; shift 2; curl -s -X $m -H "Authorization: Bearer $T" -H "Content-Type: application/json" "$u" "$@"; }
# usage: g GET "https://www.googleapis.com/drive/v3/files?pageSize=3&fields=files(id,name)" > out.json; jq . out.json
```

**Copy listed commands exactly; never guess an endpoint path.** On 404 recheck this file, don't try variations.
Paste into each Bash call (shell state does not persist). Save JSON to files, don't pipe it through zsh `echo`.

## Operations

`D=https://www.googleapis.com/drive/v3` `G=https://gmail.googleapis.com/gmail/v1/users/me` `C=https://www.googleapis.com/calendar/v3` `TK=https://tasks.googleapis.com/tasks/v1`

### Drive

| Task | Call |
|---|---|
| Who am I | `g GET "$D/about?fields=user(emailAddress)"` |
| List files | `g GET "$D/files?pageSize=3&fields=nextPageToken,files(id,name,mimeType)"` |
| Next page | add `&pageToken=<nextPageToken>` to the same call |
| Search by name | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "q=name contains 'foo' and trashed=false" --data-urlencode "fields=files(id,name)" "$D/files"` |
| Children of a folder | same, with `q='<FOLDER_ID>' in parents and trashed=false` |
| Create folder | `g POST "$D/files?fields=id" -d '{"name":"X","mimeType":"application/vnd.google-apps.folder"}'` |
| File metadata | `g GET "$D/files/<ID>?fields=id,name,mimeType,size,trashed"` |
| Download content | `curl -s -H "Authorization: Bearer $T" "$D/files/<ID>?alt=media" -o file` |
| Export Doc/Sheet/Slides | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "mimeType=application/pdf" "$D/files/<ID>/export" -o x.pdf`. Tested: Doc to `text/plain`, `text/markdown`, `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (.docx); Sheet to `text/csv` and `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (.xlsx) |
| Rename | `g PATCH "$D/files/<ID>?fields=name" -d '{"name":"new"}'` |
| Trash (preferred) | `g PATCH "$D/files/<ID>?fields=trashed" -d '{"trashed":true}'` |
| Permanent delete | `g DELETE "$D/files/<ID>"` (204, no undo, ask first) |
| Copy | `g POST "$D/files/<ID>/copy?fields=id,name,parents" -d '{"name":"copy"}'` (add `"parents":["<FOLDER>"]` to copy into a folder) |
| Move | `g PATCH "$D/files/<ID>?addParents=<NEW>&removeParents=<OLD>&fields=id,parents" -d '{}'` (get `<OLD>` from `fields=parents`) |
| Star / description | `g PATCH "$D/files/<ID>?fields=starred,description" -d '{"starred":true,"description":"x"}'`; find starred with `q=starred=true` |
| Revisions | `g GET "$D/files/<ID>/revisions?fields=revisions(id,modifiedTime)"` |
| Comments on a Doc | create / list / reply / delete, see editing.md (`fields` is required) |
| Shared drives (read-only) | `g GET "$D/drives?pageSize=5&fields=drives(id,name)"`; search them with `corpora=allDrives`, `supportsAllDrives=true`, `includeItemsFromAllDrives=true` |
| List permissions (read-only) | `g GET "$D/files/<ID>/permissions?fields=permissions(id,role,type)"` |
| Share (asks first) | `g POST "$D/files/<ID>/permissions?sendNotificationEmail=false&fields=id,role" -d '{"type":"user","role":"reader","emailAddress":"<WHO>"}'` (`role` reader/commenter/writer) |
| Unshare | `g DELETE "$D/files/<ID>/permissions/<PERM_ID>"` (204; confirm with the list call) |

### Upload a file (two ways, both tested)

```bash
# A) multipart: metadata + content in one call (put the file in a folder via parents)
echo '{"name":"report.csv","parents":["<FOLDER_ID>"]}' > meta.json
curl -s -H "Authorization: Bearer $T" -F "metadata=@meta.json;type=application/json" -F "file=@report.csv;type=text/csv" \
  "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,mimeType"
# B) create empty, then PATCH raw bytes (this is also how to REPLACE a file in place: same ID, new bytes)
ID=$(g POST "$D/files?fields=id" -d '{"name":"report.csv","parents":["<FOLDER_ID>"],"mimeType":"text/csv"}' | jq -r .id)
curl -s -X PATCH -H "Authorization: Bearer $T" -H "Content-Type: text/csv" --data-binary @report.csv \
  "https://www.googleapis.com/upload/drive/v3/files/$ID?uploadType=media&fields=id,size"
```

**Convert on upload:** set the target Google type as `mimeType` in the metadata of method A and upload the real file, e.g.
`{"name":"x","mimeType":"application/vnd.google-apps.spreadsheet"}` with a `.csv` or `.xlsx`, or `application/vnd.google-apps.document` with a `.docx`
(all three returned the Google type and the right content). A PATCH of new CSV bytes onto a converted Sheet replaces its content (same id).

**Over 5 MB: resumable.** Tested with 6 MB, size matched after download:

```bash
curl -s -D hdr.txt -o /dev/null -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json; charset=UTF-8" -H "X-Upload-Content-Type: application/octet-stream" \
  -d '{"name":"big.bin","parents":["<FOLDER_ID>"]}' "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id,size"
LOC=$(grep -i '^location:' hdr.txt | cut -d' ' -f2 | tr -d '\r')
curl -s -X PUT -H "Content-Type: application/octet-stream" --data-binary @big.bin "$LOC"     # returns {id,size}
```

### Docs

| Task | Call |
|---|---|
| Create | `g POST https://docs.googleapis.com/v1/documents -d '{"title":"X"}' > c.json; jq -r .documentId c.json` (always save to a file: the reply holds `\n` escapes that zsh `echo` turns into real newlines, and then `jq` fails) |
| Insert text | `g POST "https://docs.googleapis.com/v1/documents/<DOC>:batchUpdate" -d '{"requests":[{"insertText":{"location":{"index":1},"text":"Hello\n"}}]}'` |
| Read text | `g GET "https://docs.googleapis.com/v1/documents/<DOC>" > d.json; jq -r '[.body.content[].paragraph.elements[]?.textRun.content]\|join("")' d.json` |
| Read as text (simplest) | Drive export with `mimeType=text/markdown` (keeps headings and tables) or `text/plain` (starts with a BOM) |
| Fill `{{placeholders}}`, bold, headings, bullets, page break, image | editing.md, Docs |
| Tables: insert, fill every cell, add/delete rows and columns, cell colour | editing.md, Tables (**fill last cell first**) |

### Sheets

`SH=https://sheets.googleapis.com/v4/spreadsheets`

| Task | Call |
|---|---|
| Create | `g POST "$SH?fields=spreadsheetId,sheets.properties" -d '{"properties":{"title":"X"}}'` |
| Write cells | `g PUT "$SH/<ID>/values/Sheet1!A1:B2?valueInputOption=USER_ENTERED" -d '{"values":[["Name","Qty"],["a","=1+1"]]}'` (formulas evaluate; `"=1+1"` reads back as `"2"`) |
| Read cells | `g GET "$SH/<ID>/values/Sheet1!A1:B3"` (`Sheet1` alone reads the whole used range) |
| Append rows | `g POST "$SH/<ID>/values/Sheet1!A1:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS" -d '{"values":[["b",5]]}'` |
| Bold header row | `g POST "$SH/<ID>:batchUpdate" -d '{"requests":[{"repeatCell":{"range":{"sheetId":0,"startRowIndex":0,"endRowIndex":1},"cell":{"userEnteredFormat":{"textFormat":{"bold":true}}},"fields":"userEnteredFormat.textFormat.bold"}}]}'` |

| Clear / batchGet / tabs / formats / merge / freeze / sort / find-replace / delete rows / chart | editing.md, Sheets |

### Slides

| Task | Call |
|---|---|
| Create | `g POST "https://slides.googleapis.com/v1/presentations?fields=presentationId" -d '{"title":"X"}'` |
| Add slide | `g POST "https://slides.googleapis.com/v1/presentations/<ID>:batchUpdate" -d '{"requests":[{"createSlide":{"slideLayoutReference":{"predefinedLayout":"TITLE_AND_BODY"}}}]}'` |
| Read | `g GET "https://slides.googleapis.com/v1/presentations/<ID>?fields=slides.objectId"` (a new deck starts with 1 slide) |
| Fill placeholders, text into a shape, text box, duplicate or delete a slide, image | editing.md, Slides (object ids need 5+ characters) |

### Gmail

Read-only calls are safe. **Never print message bodies or snippets unless the user names the message; ask before showing mail content.**

| Task | Call |
|---|---|
| Profile | `g GET "$G/profile"` |
| Labels | `g GET "$G/labels"` |
| List messages | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "maxResults=3" --data-urlencode "q=newer_than:1d" "$G/messages"` (ids only; `nextPageToken` for more) |
| Headers only | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "format=metadata" --data-urlencode "metadataHeaders=From" --data-urlencode "metadataHeaders=Subject" --data-urlencode "metadataHeaders=Date" "$G/messages/<ID>"` |
| List threads | `g GET "$G/threads?maxResults=2"` |
| One thread | `g GET "$G/threads/<TID>?format=metadata"` |
| Create draft | `g POST "$G/drafts" -d "{\"message\":{\"raw\":\"$RAW\"}}"` |
| Send (asks first) | `g POST "$G/messages/send" -d "{\"raw\":\"$RAW\"}"`; reply in a thread, attachments, labels, archive, trash, batchModify: editing.md, Gmail |
| Delete draft | `g DELETE "$G/drafts/<DRAFT_ID>"` (204) |

Build `RAW` (base64url of an RFC822 message, no padding):

```bash
RAW=$(printf 'To: a@b.com\r\nSubject: Hi\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nBody' | base64 | tr '+/' '-_' | tr -d '=\n')
```

### Read a message body

Only for a message the user named. Show that one message, never a batch, and cap the output (`head -c 4000`) unless asked for all of it.
Tested on drafts built with a known body (plain, HTML only, mixed with an attachment) and on real inbox messages (structure and
length only): every round trip matched. Save the JSON to a file, then decode:

```bash
g GET "$G/messages/<ID>?format=full" > m.json
python3 - <<'PY'
import base64, html, json, re
def b64d(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")
def walk(p, o):
    mt, body = p.get("mimeType", ""), p.get("body", {})
    if p.get("filename"): o["att"].append((p["filename"], body.get("attachmentId")))
    elif mt in ("text/plain", "text/html") and body.get("data"): o[mt].append(b64d(body["data"]))
    for c in p.get("parts") or []: walk(c, o)
o = {"text/plain": [], "text/html": [], "att": []}; walk(json.load(open("m.json"))["payload"], o)
if o["text/plain"]: t = "\n".join(o["text/plain"])
else:
    h = re.sub(r"(?is)<(script|style).*?</\1>", "", "\n".join(o["text/html"]))
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", h); t = html.unescape(re.sub(r"<[^>]+>", "", h)).strip()
print(t[:4000]); print("attachments:", [a[0] for a in o["att"]])
PY
```

- Prefer the `text/plain` part. If a message has only HTML, the tag-stripping above gives readable text.
- Parts nest (`multipart/mixed` > `related` > `alternative`), so always walk the tree; never read `payload.body` alone (empty on multipart).
- Newsletters can decode to 15,000+ characters: summarise or cap instead of printing.
- Inline images and calendar invites show up as attachments with a filename; ignore them unless asked.
- Attachment download (tested): `g GET "$G/messages/<ID>/attachments/<ATT_ID>"` returns `{size,data}`; decode `data` with the same `b64d`
  (the attachment text round-tripped exactly). `<ATT_ID>` is `payload.parts[].body.attachmentId` of the `format=full` message.
- Drafts also appear in `messages.list`. Add `labelIds=INBOX` to list only received mail.

### Calendar

| Task | Call |
|---|---|
| My calendars | `g GET "$C/users/me/calendarList?fields=items(id,summary,primary)"` |
| Events in a time range | same call with extra `--data-urlencode "timeMin=2026-10-06T00:00:00+05:30" --data-urlencode "timeMax=2026-10-07T00:00:00+05:30"`; count with `jq '.items\|length'` |
| Upcoming events | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "timeMin=$(date -u +%Y-%m-%dT%H:%M:%SZ)" --data-urlencode "maxResults=3" --data-urlencode "singleEvents=true" --data-urlencode "orderBy=startTime" "$C/calendars/primary/events"` |
| Add event (no attendees; example date and zone, use the user's) | `g POST "$C/calendars/primary/events?sendUpdates=none&fields=id,status" -d '{"summary":"X","start":{"dateTime":"2026-10-06T03:00:00+05:30","timeZone":"Asia/Kolkata"},"end":{"dateTime":"2026-10-06T03:30:00+05:30","timeZone":"Asia/Kolkata"}}'` |
| Get one event | `g GET "$C/calendars/primary/events/<ID>?fields=summary,start,status"` |
| Change title or time | `g PATCH "$C/calendars/primary/events/<ID>?sendUpdates=none&fields=summary,start" -d '{"summary":"new","start":{...},"end":{...}}'` (PATCH merges; PUT replaces the whole event) |
| Add a Google Meet link | add `conferenceDataVersion=1` to the URL and `"conferenceData":{"createRequest":{"requestId":"<unique>","conferenceSolutionKey":{"type":"hangoutsMeet"}}}` to the body, on create or PATCH; read `hangoutLink` |
| Add attendees (invites them: ask first) | add `"attendees":[{"email":"<WHO>"}]` to the body; keep `sendUpdates=none` unless the user wants invites sent |
| Repeating event | add `"recurrence":["RRULE:FREQ=DAILY;COUNT=3"]`; `.../events/<ID>/instances` lists the occurrences; deleting the series id removes all |
| Quick add | `curl -s -X POST -H "Authorization: Bearer $T" -G --data-urlencode "text=Lunch on 2026-10-07 at 1pm" --data-urlencode sendUpdates=none "$C/calendars/primary/events/quickAdd"` (parsed text becomes the title and time) |
| Free/busy | `g POST "$C/freeBusy" -d '{"timeMin":"2026-10-07T00:00:00+05:30","timeMax":"2026-10-07T06:00:00+05:30","items":[{"id":"primary"}]}'` (`calendars.primary.busy[]`) |
| Delete event | `g DELETE "$C/calendars/primary/events/<ID>?sendUpdates=none"` (204; a GET afterwards shows `status: cancelled`) |

### Tasks

| Task | Call |
|---|---|
| Task lists | `g GET "$TK/users/@me/lists"` |
| Add task | `g POST "$TK/lists/@default/tasks" -d '{"title":"X"}'` |
| Edit title / notes / due | `g PATCH "$TK/lists/@default/tasks/<ID>" -d '{"title":"y","notes":"n","due":"2026-10-08T00:00:00.000Z"}'` (PATCH merges; **PUT wipes notes and due** unless you resend them) |
| Mark done | `g PATCH "$TK/lists/@default/tasks/<ID>" -d '{"status":"completed"}'` (sets `completed`) |
| Move / make subtask | `curl -s -X POST -H "Authorization: Bearer $T" -G --data-urlencode "parent=<PARENT_ID>" "$TK/lists/<LIST>/tasks/<ID>/move"`; `previous=<ID>` instead sets the order (no `parent` = top level) |
| Clear completed | `g POST "$TK/lists/<LIST>/clear" -d '{}'` (204; untested whether they then vanish from the plain list) |
| New / delete a list | `g POST "$TK/users/@me/lists" -d '{"title":"X"}'`; `g DELETE "$TK/users/@me/lists/<LIST_ID>"` (204) |
| Delete task | `g DELETE "$TK/lists/@default/tasks/<ID>"` (204) |

## Not in the table?

Not run live, so treat as untested: writing to a shared drive's files, Gmail settings changes, sending a draft (`drafts.send`), Docs headers/footers and
named ranges, Sheets pivot tables and conditional formatting, Slides layouts and tables. Look up the endpoint in Google's REST reference first (read-only), run a
harmless GET or a temp-item test, and ask the user before anything that sends, shares, edits or deletes.

## Traps (all hit or observed)

- **Always pass `fields=`** on Drive. Without it, files.list returns only `id,name,mimeType,kind`.
- **`curl -G` plus a `?query` in the URL breaks the request.** With `-G`, pass every parameter (including `fields`) as `--data-urlencode` and keep the URL bare.
- **URL-encode `q`**: use `curl -G --data-urlencode`, not a hand-built URL (quotes and spaces break).
- **Google-native files** (Doc/Sheet/Slides) cannot use `alt=media`: 403 `fileNotDownloadable`. Use `/export?mimeType=...`.
- **Pagination**: Drive, Gmail and Calendar return `nextPageToken` when more exists; pass it back as `pageToken`.
- **Upload mime**: set `Content-Type` on the PATCH to the real type; set `mimeType` on create to match.
- **Token** lasts 1 hour (Google default; not waited out). A bad token gives 401 `UNAUTHENTICATED`.
- **Error shapes**: Drive 404 is `{error:{code:404,errors:[{reason:"notFound"}]}}`. Gmail with a bad message id returns 400 `INVALID_ARGUMENT`, not 404.
- **Deletes return 204 with an empty body**: check the status code, not JSON.
- **Gmail drafts** created via API carry label `DRAFT` and stay in the mailbox until deleted.
- **Shared drives**: add `supportsAllDrives=true` and `includeItemsFromAllDrives=true` on lists; `corpora=allDrives` returned 200. Only listing was tested, no shared-drive file was written.
- **Docs and Slides batchUpdate**: indexes shift after every edit; fill tables from the last cell to the first (editing.md). Slides object ids must be 5+ characters.
- **Sheets reads return formatted text** (`"$2.00"`); add `valueRenderOption=UNFORMATTED_VALUE` for numbers. A CSV converted to a Sheet has its tab named after the file, not `Sheet1`.
- **Drive comments** need `fields=` (400 otherwise). **Sharing** sends an email unless `sendNotificationEmail=false`.
- **Calendar**: PUT replaces the event, PATCH merges. **Tasks**: PUT replaces too (notes and due go null).
- **Gmail** `messages.send` to yourself arrives in the inbox as unread; `messages.delete` is permanent and returns 204; user label ids look like `Label_N`.

## Known not to work

- `alt=media` on a Doc/Sheet/Slides (403, use export).
- Drive MCP uploads (base64 only, corrupts files). Use the uploads above.
- Docs table fill from the first cell to the last with indexes from one read: returns 200 but puts the text in the wrong cells (fill last cell first).
- Slides object ids shorter than 5 characters (400). Drive `comments.create` or `comments.list` without `fields=` (400).
- Reading `Sheet1!...` on a Sheet converted from a CSV (400 `Unable to parse range`): the tab carries the file name.

## Guardrails

Ask the user before any outward-facing or hard-to-undo action: sending or replying to email, sharing a file or adding a permission, inviting attendees or
editing or deleting a calendar event, permanent delete, any bulk action (many files, many mails). Defaults that keep it quiet: `sendNotificationEmail=false` on
shares, `sendUpdates=none` on every calendar write. Prefer trash (`trashed:true`) over permanent delete. Never `emptyTrash`. Never change Gmail settings.
Test with temp items named `api-test-DELETE-ME`, send test mail only to the user's own address, and delete everything afterwards (then search to confirm nothing is left).
Never print the token, Keychain values, mail bodies or contacts.

**How to apply:** for any Drive, Docs, Sheets, Slides, Gmail, Calendar or Tasks request, use this skill, not the claude.ai MCPs.
