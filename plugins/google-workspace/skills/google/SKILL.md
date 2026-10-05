---
name: google
description: Use only after the one-time Google setup below is done (Keychain item google-refresh-token-personal exists); if it is missing, show the setup steps and stop. Then use this instead of the claude.ai Google Drive, Gmail and Google Calendar MCPs whenever Google Workspace is involved — upload to drive, download a drive file, find a file or folder, replace a file in place, trash a file, read or write a google doc, google sheet or slides deck, read my email, search gmail, make a gmail draft, list calendar events, add a calendar event, google tasks — via the Google REST APIs with curl and your own OAuth token. Triggers on "google drive", "upload to drive", "drive folder", "gmail", "read my email", "google doc", "google sheet", "slides", "calendar", "my tasks".
user-invocable: true
argument-hint: "what to do (upload / read mail / doc / sheet / calendar)"
---

# Google via REST (no MCP)

Calls Google's REST APIs directly with one all-scopes token (Drive, Docs, Sheets, Slides, Gmail, Calendar, Tasks) for the
Google account the user signs in with. Every call below was run live against a real account.

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
| Export Doc/Sheet/Slides | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "mimeType=application/pdf" "$D/files/<ID>/export" -o x.pdf` (also `text/plain`) |
| Rename | `g PATCH "$D/files/<ID>?fields=name" -d '{"name":"new"}'` |
| Trash (preferred) | `g PATCH "$D/files/<ID>?fields=trashed" -d '{"trashed":true}'` |
| Permanent delete | `g DELETE "$D/files/<ID>"` (204, no undo, ask first) |
| List permissions (read-only) | `g GET "$D/files/<ID>/permissions?fields=permissions(id,role,type)"` |

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

### Docs

| Task | Call |
|---|---|
| Create | `g POST https://docs.googleapis.com/v1/documents -d '{"title":"X"}' > c.json; jq -r .documentId c.json` (always save to a file: the reply holds `\n` escapes that zsh `echo` turns into real newlines, and then `jq` fails) |
| Insert text | `g POST "https://docs.googleapis.com/v1/documents/<DOC>:batchUpdate" -d '{"requests":[{"insertText":{"location":{"index":1},"text":"Hello\n"}}]}'` |
| Read text | `g GET "https://docs.googleapis.com/v1/documents/<DOC>" > d.json; jq -r '[.body.content[].paragraph.elements[]?.textRun.content]\|join("")' d.json` |
| Read as plain text (simpler) | Drive export with `mimeType=text/plain` (output starts with a BOM) |

### Sheets

`SH=https://sheets.googleapis.com/v4/spreadsheets`

| Task | Call |
|---|---|
| Create | `g POST "$SH?fields=spreadsheetId,sheets.properties" -d '{"properties":{"title":"X"}}'` |
| Write cells | `g PUT "$SH/<ID>/values/Sheet1!A1:B2?valueInputOption=USER_ENTERED" -d '{"values":[["Name","Qty"],["a","=1+1"]]}'` (formulas evaluate; `"=1+1"` reads back as `"2"`) |
| Read cells | `g GET "$SH/<ID>/values/Sheet1!A1:B3"` (`Sheet1` alone reads the whole used range) |
| Append rows | `g POST "$SH/<ID>/values/Sheet1!A1:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS" -d '{"values":[["b",5]]}'` |
| Bold header row | `g POST "$SH/<ID>:batchUpdate" -d '{"requests":[{"repeatCell":{"range":{"sheetId":0,"startRowIndex":0,"endRowIndex":1},"cell":{"userEnteredFormat":{"textFormat":{"bold":true}}},"fields":"userEnteredFormat.textFormat.bold"}}]}'` |

### Slides

| Task | Call |
|---|---|
| Create | `g POST "https://slides.googleapis.com/v1/presentations?fields=presentationId" -d '{"title":"X"}'` |
| Add slide | `g POST "https://slides.googleapis.com/v1/presentations/<ID>:batchUpdate" -d '{"requests":[{"createSlide":{"slideLayoutReference":{"predefinedLayout":"TITLE_AND_BODY"}}}]}'` |
| Read | `g GET "https://slides.googleapis.com/v1/presentations/<ID>?fields=slides.objectId"` (a new deck starts with 1 slide) |

### Gmail

Read-only calls are safe. **Never print message bodies or snippets; ask before showing mail content.**

| Task | Call |
|---|---|
| Profile | `g GET "$G/profile"` |
| Labels | `g GET "$G/labels"` |
| List messages | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "maxResults=3" --data-urlencode "q=newer_than:1d" "$G/messages"` (ids only; `nextPageToken` for more) |
| Headers only | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "format=metadata" --data-urlencode "metadataHeaders=From" --data-urlencode "metadataHeaders=Subject" --data-urlencode "metadataHeaders=Date" "$G/messages/<ID>"` |
| List threads | `g GET "$G/threads?maxResults=2"` |
| One thread | `g GET "$G/threads/<TID>?format=metadata"` |
| Create draft | `g POST "$G/drafts" -d "{\"message\":{\"raw\":\"$RAW\"}}"` |
| Delete draft | `g DELETE "$G/drafts/<DRAFT_ID>"` (204) |

Build `RAW` (base64url of an RFC822 message, no padding):

```bash
RAW=$(printf 'To: a@b.com\r\nSubject: Hi\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nBody' | base64 | tr '+/' '-_' | tr -d '=\n')
```

Attachments: `GET $G/messages/<ID>/attachments/<ATT_ID>` returns `{size,data}` with base64url `data`. The `<ATT_ID>` comes from
`payload.parts[].body.attachmentId` of a `format=full` message. Shape from Google docs; a bogus id returned 400, no real one fetched.

### Calendar

| Task | Call |
|---|---|
| My calendars | `g GET "$C/users/me/calendarList?fields=items(id,summary,primary)"` |
| Events in a time range | same call with extra `--data-urlencode "timeMin=2026-10-06T00:00:00+05:30" --data-urlencode "timeMax=2026-10-07T00:00:00+05:30"`; count with `jq '.items\|length'` |
| Upcoming events | `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "timeMin=$(date -u +%Y-%m-%dT%H:%M:%SZ)" --data-urlencode "maxResults=3" --data-urlencode "singleEvents=true" --data-urlencode "orderBy=startTime" "$C/calendars/primary/events"` |
| Add event (no attendees; example date and zone, use the user's) | `g POST "$C/calendars/primary/events?sendUpdates=none&fields=id,status" -d '{"summary":"X","start":{"dateTime":"2026-10-06T03:00:00+05:30","timeZone":"Asia/Kolkata"},"end":{"dateTime":"2026-10-06T03:30:00+05:30","timeZone":"Asia/Kolkata"}}'` |
| Delete event | `g DELETE "$C/calendars/primary/events/<ID>?sendUpdates=none"` (204; a GET afterwards shows `status: cancelled`) |

### Tasks

| Task | Call |
|---|---|
| Task lists | `g GET "$TK/users/@me/lists"` |
| Add task | `g POST "$TK/lists/@default/tasks" -d '{"title":"X"}'` |
| Delete task | `g DELETE "$TK/lists/@default/tasks/<ID>"` (204) |

## Not in the table?

Not run live, so treat as untested: sending mail (`POST $G/messages/send`), sharing (`permissions.create`), shared-drive
files, calendar event update. Look up the endpoint in Google's REST reference first (read-only), run a harmless GET or a
temp-item test, and ask the user before anything that sends, shares, edits or deletes.

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
- **Shared drives**: add `supportsAllDrives=true` (accepted, 200) and `includeItemsFromAllDrives=true` on lists. No shared drive was tested.

## Known not to work

- `alt=media` on a Doc/Sheet/Slides (403, use export).
- Drive MCP uploads (base64 only, corrupts files). Use the uploads above.

## Guardrails

Ask the user before: sending any email, deleting or sharing any Drive file, editing or deleting a calendar event, any bulk
action (many files, many mails). Prefer trash (`trashed:true`) over permanent delete. Create temp test items with the name
`api-test-DELETE-ME` and delete them after. Never print the token, Keychain values, mail bodies or contacts.

**How to apply:** for any Drive, Docs, Sheets, Slides, Gmail, Calendar or Tasks request, use this skill, not the claude.ai MCPs.
