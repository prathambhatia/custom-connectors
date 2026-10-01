---
name: chrome-devtools-connector
description: ALWAYS use this instead of the chrome-devtools MCP whenever the browser or Chrome is involved — open/navigate a URL, read a page, click, fill a form, type, take a screenshot or snapshot, read console logs or network requests, run JS on a page, emulate a device, Lighthouse audit — by calling a local chrome-devtools bridge with curl, so none of the 27 tool schemas load into context. Sets itself up on first use; no token needed.
user-invocable: true
argument-hint: "what to do in the browser"
---

# Chrome DevTools via a local bridge (no MCP tool schemas)

The browser tools are the official `chrome-devtools-mcp` package. Instead of loading its 27 tool
definitions into every session, a small bridge (`supergateway`) keeps one copy running on
`http://127.0.0.1:4330/mcp`, and Claude calls it with `curl`. **No token or account needed**; it
all runs on this Mac. Needs Node.js (`node --version`; else `brew install node`).

## Setup

Nothing to do by hand: the first `cdt` call starts the bridge, which opens **its own Chrome window
with a separate profile** (`~/.cache/chrome-devtools-mcp/chrome-profile`), exactly like the normal
chrome-devtools MCP does. Logins you make in that window are remembered next time.

To drive the user's everyday Chrome instead, set `CDT_FLAGS=--autoConnect` before the first call, have
them enable `chrome://inspect/#remote-debugging`, and click **Allow** when Chrome asks. Stop the bridge
with `lsof -ti tcp:4330 | xargs kill`. **Never `pkill -f supergateway`**: it matches and kills the shell running it.

## Helper (paste into each Bash call)

```bash
cdt_start() { [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:4330/mcp)" != 000 ] && [ -z "$1" ] && return 0
  lsof -ti tcp:4330 | xargs kill 2>/dev/null; sleep 1; mkdir -p ~/.cache/cdt-bridge; rm -f ~/.cache/cdt-bridge/sid
  nohup npx -y supergateway --stdio "npx -y chrome-devtools-mcp@latest --no-usage-statistics --workspace=$HOME --workspace=/tmp --workspace=/private/tmp ${CDT_FLAGS:-}" \
    --outputTransport streamableHttp --stateful --sessionTimeout 86400000 --port 4330 > ~/.cache/cdt-bridge/bridge.log 2>&1 &
  for i in $(seq 1 45); do grep -q "Listening on port 4330" ~/.cache/cdt-bridge/bridge.log 2>/dev/null && return 0; sleep 2; done
  echo "bridge failed to start, see ~/.cache/cdt-bridge/bridge.log"; return 1; }
cdt() { local args=$2; [ -z "$args" ] && args='{}'; local U=http://127.0.0.1:4330/mcp F=~/.cache/cdt-bridge/sid
  local H=(-H "Content-Type: application/json" -H "Accept: application/json, text/event-stream")
  _cdt_init() { curl -s -D /tmp/cdt_h.txt -o /dev/null -m 60 -X POST $U "${H[@]}" -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"claude","version":"1"}}}'
    grep -i '^mcp-session-id' /tmp/cdt_h.txt | cut -d' ' -f2 | tr -d '\r' > $F
    curl -s -o /dev/null -m 10 -X POST $U "${H[@]}" -H "Mcp-Session-Id: $(cat $F)" -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'; }
  _cdt_call() { curl -s -m 120 -X POST $U "${H[@]}" -H "Mcp-Session-Id: $(cat $F 2>/dev/null)" -d "$(jq -cn --arg n "$1" --argjson a "$2" '{jsonrpc:"2.0",id:1,method:"tools/call",params:{name:$n,arguments:$a}}')"; }
  [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' -X POST $U)" = 000 ] && { cdt_start || return 1; }
  [ -s $F ] || _cdt_init
  local r; r=$(_cdt_call "$1" "$args")
  if ! printf %s "$r" | grep -q '^data: '; then _cdt_init; r=$(_cdt_call "$1" "$args"); fi
  if printf %s "$r" | grep -q 'browser is already running'; then cdt_start force && _cdt_init && r=$(_cdt_call "$1" "$args"); fi
  printf %s "$r" | sed -n 's/^data: //p' | jq -r 'if .error then "ERROR: \(.error.message)" elif .result.isError then "TOOLERR: \([.result.content[]?.text]|join(" "))" else ([.result.content[]? | if .type=="text" then .text else "[\(.type)]" end]|join("\n")) end'; }
# usage: cdt list_pages; cdt new_page '{"url":"https://example.com"}'
```

**Paste the helper, then call `cdt`; never call `cdt_start` yourself** (it restarts nothing if the bridge is up, but a forced restart closes every open page). **Pass the tool name first and the JSON arguments second.** Copy commands exactly; never guess tool
or argument names, they're all in the table below. If the session is lost the helper reconnects or restarts the bridge on its own; after a restart, open pages are gone and need reopening.

## Rules

- **Snapshots to a file, never inline:** `take_snapshot` with `filePath` (`/tmp/snap_<what>.txt`), then
  `grep -n 'button "Save"' /tmp/snap_<what>.txt` for the uid. Real pages are 100k+ characters.
- **A uid dies at the next view change** (navigation, tab switch, panel toggle). Re-snapshot after
  every change.
- **To read text off a page, snapshot first** and grep it (`grep -n 'heading' /tmp/snap_x.txt`). Don't guess CSS
  selectors in `evaluate_script`; if you must, use `?.` (`document.querySelector("h1")?.textContent`) so a missing
  element returns null instead of throwing.
- **One browser session at a time.** Two Claude sessions driving the bridge at once fight over port 4330
  and the Chrome profile (the normal chrome-devtools MCP has the same limit).
- `take_screenshot` with `filePath`, then Read the PNG to see it. Cheaper than a snapshot for reading.
- Don't touch tabs you didn't open unless asked. `close_page` the ones you open.

## Tools (pageId is a number on every tool except list_pages / new_page)

| Tool | Arguments (required in bold) |
|---|---|
| list_pages | none |
| new_page | **url**, background, isolatedContext, timeout |
| select_page | **pageId**, bringToFront |
| navigate_page | **pageId**, type (`url`/`back`/`forward`/`reload`), url, ignoreCache, initScript, timeout |
| close_page | **pageId** |
| take_snapshot | **pageId**, filePath, verbose |
| take_screenshot | **pageId**, filePath, format (`png`/`jpeg`/`webp`), fullPage, uid, quality |
| click | **pageId**, **uid**, dblClick, includeSnapshot |
| fill | **pageId**, **uid**, **value** |
| fill_form | **pageId**, **elements** `[{"uid":"1_2","value":"x"}]` |
| type_text | **pageId**, **text**, submitKey |
| press_key | **pageId**, **key** (`Enter`, `Control+A`, `Meta+Enter`) |
| hover | **pageId**, **uid** |
| drag | **pageId**, **from_uid**, **to_uid** |
| upload_file | **pageId**, **uid** (the file input's button), **filePaths** `["/abs/path"]` |
| handle_dialog | **pageId**, **action** (`accept`/`dismiss`), promptText |
| wait_for | **pageId**, **text** `["any of these"]`, timeout |
| evaluate_script | **pageId**, **function** (`"() => document.title"`), args, filePath |
| get_css_styles | **pageId**, **uid**, pageIdx, pageSize |
| list_console_messages | **pageId**, types, pageSize, includePreservedMessages |
| get_console_message | **pageId**, **msgid** |
| list_network_requests | **pageId**, resourceTypes, pageSize |
| get_network_request | **pageId**, reqid, requestFilePath, responseFilePath |
| emulate | **pageId**, colorScheme (`dark`/`light`/`auto`), viewport (`390x844x3,mobile,touch`), networkConditions, cpuThrottlingRate, geolocation, userAgent |
| resize_page | **pageId**, **width**, **height** |
| take_heapsnapshot | **pageId**, **filePath** |
| lighthouse_audit | **pageId**, mode (`navigation`/`snapshot`), device, outputDirPath |

**How to apply:** for anything in the browser, use `cdt` here instead of chrome-devtools MCP tools.
Disable the chrome-devtools MCP in `/mcp` so its tools stop loading.
