# Editing recipes (Docs, Sheets, Slides, Gmail send)

Read when a task edits a Doc, Sheet or deck, or sends mail. Same helper `g`, `T`, and variables as SKILL.md. Every call
below returned 200 live (Gmail batch/delete 204). `DOCS=https://docs.googleapis.com/v1/documents`,
`SH=https://sheets.googleapis.com/v4/spreadsheets`, `SL=https://slides.googleapis.com/v1/presentations`.
Write big request bodies to a file and send with `-d @req.json`. A `batchUpdate` is all-or-nothing: one bad request fails the lot.

## Docs

Send all as `g POST "$DOCS/<DOC>:batchUpdate" -d '{"requests":[ ... ]}'`. Indexes are UTF-16 positions; a new doc body starts at 1.
Read the doc first (`g GET "$DOCS/<DOC>"`) and use each paragraph's `startIndex`/`endIndex`; **edits earlier in the doc shift every index after them**,
so in one batch go from the end of the doc to the start, or re-read between batches.

| Task | Request |
|---|---|
| Template fill (also works inside table cells) | `{"replaceAllText":{"containsText":{"text":"{{name}}","matchCase":true},"replaceText":"Asha"}}` (reply `occurrencesChanged`) |
| Insert text | `{"insertText":{"location":{"index":1},"text":"Hello\n"}}` |
| Delete text | `{"deleteContentRange":{"range":{"startIndex":59,"endIndex":63}}}` (never include the final newline of the doc) |
| Bold / italic / link | `{"updateTextStyle":{"range":{"startIndex":1,"endIndex":5},"textStyle":{"bold":true},"fields":"bold"}}`; `"italic":true` / `{"link":{"url":"https://..."}}` with matching `fields` |
| Heading, centre | `{"updateParagraphStyle":{"range":{"startIndex":48,"endIndex":59},"paragraphStyle":{"namedStyleType":"HEADING_1","alignment":"CENTER"},"fields":"namedStyleType,alignment"}}` |
| Bullets | `{"createParagraphBullets":{"range":{"startIndex":30,"endIndex":48},"bulletPreset":"BULLET_DISC_CIRCLE_SQUARE"}}` (indexes do not shift) |
| Page break | `{"insertPageBreak":{"location":{"index":59}}}` |
| Image from a public URL | `{"insertInlineImage":{"location":{"index":1},"uri":"https://...png","objectSize":{"width":{"magnitude":100,"unit":"PT"},"height":{"magnitude":34,"unit":"PT"}}}}` |

**Read as text:** `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "mimeType=text/markdown" "$D/files/<DOC>/export"` is the simplest
(headings, bullets and tables survive as Markdown; `text/plain` also works and starts with a BOM, tables come out tab separated). Walking the Docs JSON works
but is longer; use it when you need indexes.

### Tables

Insert (3 rows, 2 columns) at an index inside a paragraph: `{"insertTable":{"location":{"index":14},"rows":3,"columns":2}}`. Read the doc back: the table is the
`body.content[]` element with `.table`; its start is that element's `startIndex`; each cell's first paragraph
`tableRows[r].tableCells[c].content[0].startIndex` is where to insert text. **Fill from the LAST cell to the FIRST, using indexes from one read, in one batch.**
Filling first to last with the same stale indexes was tested: it returned 200 but piled all text into the first cell.

```bash
g GET "$DOCS/<DOC>" > d.json
python3 - <<'PY'
import json
d = json.load(open("d.json")); t = [c for c in d["body"]["content"] if "table" in c][0]["table"]
vals = [["h1", "h2"], ["a", "b"], ["c", "d"]]          # rows x cols, same shape as the table
reqs = [{"insertText": {"location": {"index": cell["content"][0]["startIndex"]}, "text": vals[r][c]}}
        for r, row in reversed(list(enumerate(t["tableRows"]))) for c, cell in reversed(list(enumerate(row["tableCells"])))]
json.dump({"requests": reqs}, open("fill.json", "w"))
PY
g POST "$DOCS/<DOC>:batchUpdate" -d @fill.json      # then re-read: each cell text ends with \n
```

To overwrite a filled cell, `deleteContentRange` from the cell's `startIndex` to `endIndex-1`, then insert (again last cell first). For a template table with
`{{placeholders}}` in cells, `replaceAllText` is simpler and needs no index math.

Table structure (`TS` = the table's `startIndex`, row and column indexes are 0-based):

| Task | Request |
|---|---|
| Add row below | `{"insertTableRow":{"tableCellLocation":{"tableStartLocation":{"index":TS},"rowIndex":0,"columnIndex":0},"insertBelow":true}}` |
| Add column right | `{"insertTableColumn":{"tableCellLocation":{"tableStartLocation":{"index":TS},"rowIndex":0,"columnIndex":1},"insertRight":true}}` |
| Delete row | `{"deleteTableRow":{"tableCellLocation":{"tableStartLocation":{"index":TS},"rowIndex":1,"columnIndex":0}}}` |
| Cell background (header row) | `{"updateTableCellStyle":{"tableRange":{"tableCellLocation":{"tableStartLocation":{"index":TS},"rowIndex":0,"columnIndex":0},"rowSpan":1,"columnSpan":3},"tableCellStyle":{"backgroundColor":{"color":{"rgbColor":{"red":0.8,"green":0.9,"blue":1}}}},"fields":"backgroundColor"}}` |
| Column width | `{"updateTableColumnProperties":{"tableStartLocation":{"index":TS},"columnIndices":[0],"tableColumnProperties":{"widthType":"FIXED_WIDTH","width":{"magnitude":120,"unit":"PT"}},"fields":"widthType,width"}}` |

Structure edits shift indexes: re-read before the next insert.

### Doc comments (Drive API)

`fields` is **required** (400 without). Create: `g POST "$D/files/<DOC>/comments?fields=id,content" -d '{"content":"x"}'`. List:
`g GET "$D/files/<DOC>/comments?fields=comments(id,content,resolved)"`. Reply: `POST .../comments/<CID>/replies?fields=id` with `{"content":"x"}`;
add `"action":"resolve"` to resolve. Delete: `g DELETE "$D/files/<DOC>/comments/<CID>"` (204).

## Sheets

Formatting and layout go through `g POST "$SH/<ID>:batchUpdate" -d '{"requests":[...]}'`. `sheetId` is the tab's numeric id (first tab is usually 0; read
`g GET "$SH/<ID>?fields=sheets.properties"`). Rows and columns are 0-based, `endIndex` exclusive.

| Task | Request |
|---|---|
| Add tab | `{"addSheet":{"properties":{"title":"Tab2"}}}` (reply holds the new `sheetId`) |
| Rename tab | `{"updateSheetProperties":{"properties":{"sheetId":N,"title":"New"},"fields":"title"}}` |
| Delete tab | `{"deleteSheet":{"sheetId":N}}` |
| Number format | `{"repeatCell":{"range":{"sheetId":0,"startRowIndex":1,"endRowIndex":5,"startColumnIndex":2,"endColumnIndex":3},"cell":{"userEnteredFormat":{"numberFormat":{"type":"CURRENCY","pattern":"$#,##0.00"}}},"fields":"userEnteredFormat.numberFormat"}}` |
| Background + bold | `{"repeatCell":{"range":{"sheetId":0,"startRowIndex":0,"endRowIndex":1},"cell":{"userEnteredFormat":{"backgroundColor":{"red":0.8,"green":0.9,"blue":1},"textFormat":{"bold":true}}},"fields":"userEnteredFormat(backgroundColor,textFormat.bold)"}}` |
| Merge | `{"mergeCells":{"range":{"sheetId":0,"startRowIndex":6,"endRowIndex":7,"startColumnIndex":0,"endColumnIndex":3},"mergeType":"MERGE_ALL"}}` |
| Auto-resize columns | `{"autoResizeDimensions":{"dimensions":{"sheetId":0,"dimension":"COLUMNS","startIndex":0,"endIndex":3}}}` |
| Freeze header | `{"updateSheetProperties":{"properties":{"sheetId":0,"gridProperties":{"frozenRowCount":1}},"fields":"gridProperties.frozenRowCount"}}` |
| Delete rows | `{"deleteDimension":{"range":{"sheetId":0,"dimension":"ROWS","startIndex":4,"endIndex":5}}}` (rows below move up) |
| Sort | `{"sortRange":{"range":{"sheetId":0,"startRowIndex":1,"endRowIndex":5,"startColumnIndex":0,"endColumnIndex":3},"sortSpecs":[{"dimensionIndex":0,"sortOrder":"ASCENDING"}]}}` (start at row 1 to keep the header) |
| Find and replace | `{"findReplace":{"find":"a","replacement":"alpha","matchCase":true,"matchEntireCell":true,"allSheets":true}}` (reply has counts) |
| Warn on editing a range | `{"addProtectedRange":{"protectedRange":{"range":{...},"description":"formulas","warningOnly":true}}}`; remove with `{"deleteProtectedRange":{"protectedRangeId":ID}}` |
| Column chart | `{"addChart":{"chart":{"spec":{"title":"t","basicChart":{"chartType":"COLUMN","legendPosition":"BOTTOM_LEGEND","axis":[{"position":"BOTTOM_AXIS"},{"position":"LEFT_AXIS"}],"domains":[{"domain":{"sourceRange":{"sources":[{"sheetId":0,"startRowIndex":0,"endRowIndex":4,"startColumnIndex":0,"endColumnIndex":1}]}}}],"series":[{"series":{"sourceRange":{"sources":[{"sheetId":0,"startRowIndex":0,"endRowIndex":4,"startColumnIndex":1,"endColumnIndex":2}]}}}],"headerCount":1}},"position":{"overlayPosition":{"anchorCell":{"sheetId":0,"rowIndex":8,"columnIndex":4}}}}}}` |

Values calls (not batchUpdate):

- Clear: `g POST "$SH/<ID>/values/Tab!A1:B2:clear" -d '{}'`
- Several ranges: `curl -s -G -H "Authorization: Bearer $T" --data-urlencode "ranges=Sheet1!A1:A2" --data-urlencode "ranges=Sheet1!C1:C2" "$SH/<ID>/values:batchGet"` (`valueRanges[].values`)
- **Reads return the formatted text** (`"$2.00"`). For raw numbers add `valueRenderOption=UNFORMATTED_VALUE` (`FORMULA` shows the formula).
- Append with `insertDataOption=INSERT_ROWS` returns the range it wrote in `updates.updatedRange`.
- A Sheet made by uploading a CSV (SKILL.md) names its tab after the file (`t.csv`), not `Sheet1`. Read the tab name first or use a bare range like `A1:B3`.

## Slides

`g POST "$SL/<ID>:batchUpdate" -d '{"requests":[...]}'`. Object ids you choose must be **5 or more characters** (`tb1` is rejected with 400).
Find shape ids: `g GET "$SL/<ID>?fields=slides(objectId,pageElements(objectId,shape(placeholder/type)))"`; a new `TITLE_AND_BODY` slide has a TITLE and a BODY shape.

| Task | Request |
|---|---|
| Fill placeholders everywhere | `{"replaceAllText":{"containsText":{"text":"{{who}}","matchCase":true},"replaceText":"World"}}` (reply `occurrencesChanged`) |
| Text into a shape | `{"insertText":{"objectId":"<SHAPE_ID>","text":"Hello","insertionIndex":0}}` |
| Text box | `{"createShape":{"objectId":"textbox1","shapeType":"TEXT_BOX","elementProperties":{"pageObjectId":"<SLIDE_ID>","size":{"width":{"magnitude":3000000,"unit":"EMU"},"height":{"magnitude":500000,"unit":"EMU"}},"transform":{"scaleX":1,"scaleY":1,"translateX":500000,"translateY":3500000,"unit":"EMU"}}}}` then `insertText` on `textbox1` |
| Delete element or slide | `{"deleteObject":{"objectId":"textbox1"}}` |
| Duplicate slide | `{"duplicateObject":{"objectId":"<SLIDE_ID>"}}` (reply gives the new slide id) |
| Image from a public URL | `{"createImage":{"url":"https://...png","elementProperties":{"pageObjectId":"<SLIDE_ID>","size":{"width":{"magnitude":1500000,"unit":"EMU"},"height":{"magnitude":500000,"unit":"EMU"}}}}}` |

## Gmail: send, reply, attach, labels

**Sending is outward-facing: confirm recipient, subject and body with the user first.** To test, send only to the user's own address.
Build each message as RFC822, base64url it without padding (as in SKILL.md), send `g POST "$G/messages/send" -d "{\"raw\":\"$RAW\"}"`.

- **Reply in the same thread:** take the original's `Message-Id` header (metadata read, `metadataHeaders=Message-ID`). New message headers: `Subject: Re: <original subject>`,
  `In-Reply-To: <id>`, `References: <id>`; body `{"raw":"...","threadId":"<original threadId>"}`. Tested: the thread then held both messages.
- **Attachment (multipart/mixed)**, built in Python so the base64 line is exact:

```bash
python3 - <<'PY'
import base64
att = base64.b64encode(open("att.txt", "rb").read()).decode()
msg = ("To: me@example.com\r\nSubject: Report\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=\"BND\"\r\n\r\n"
       "--BND\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nsee attached\r\n"
       "--BND\r\nContent-Type: text/plain; name=\"att.txt\"\r\nContent-Disposition: attachment; filename=\"att.txt\"\r\n"
       "Content-Transfer-Encoding: base64\r\n\r\n" + att + "\r\n--BND--\r\n")
open("raw.txt", "w").write(base64.urlsafe_b64encode(msg.encode()).decode().rstrip("="))
PY
g POST "$G/messages/send" -d "{\"raw\":\"$(cat raw.txt)\"}"
```

| Task | Call |
|---|---|
| Create label | `g POST "$G/labels" -d '{"name":"X","labelListVisibility":"labelShow","messageListVisibility":"show"}'` |
| Rename label | `g PATCH "$G/labels/<LABEL_ID>" -d '{"name":"Y"}'` |
| Delete label | `g DELETE "$G/labels/<LABEL_ID>"` (204) |
| Add label / mark read | `g POST "$G/messages/<ID>/modify" -d '{"addLabelIds":["<LABEL_ID>"],"removeLabelIds":["UNREAD"]}'` |
| Archive | same, `{"removeLabelIds":["INBOX"]}` |
| Many at once | `g POST "$G/messages/batchModify" -d '{"ids":["<ID1>","<ID2>"],"addLabelIds":["..."],"removeLabelIds":["INBOX"]}'` (204) |
| Trash / untrash | `g POST "$G/messages/<ID>/trash"` / `.../untrash` |
| Delete for good | `g DELETE "$G/messages/<ID>"` (204, no undo; ask first) |
| Search queries | `q=` accepts `from:`, `to:`, `subject:`, `has:attachment`, `newer_than:2d`, `label:<name>`, `is:unread`, `in:anywhere` (URL-encode via `--data-urlencode`) |
| Settings (read only) | `g GET "$G/settings/vacation"`, `.../settings/autoForwarding`, `.../settings/sendAs`; never change settings |

A sent message to yourself lands in the inbox as `["UNREAD","SENT","INBOX"]`. System label ids are the names (`INBOX`, `UNREAD`, `TRASH`); user labels are `Label_N`.
