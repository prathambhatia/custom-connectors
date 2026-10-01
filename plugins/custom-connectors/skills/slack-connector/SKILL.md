---
name: slack-connector
description: ALWAYS use this instead of the Slack MCP whenever Slack is mentioned or any Slack action is involved — send, reply in a thread, DM, edit, delete, upload a file, read a channel or thread, search messages/channels/users, react, read a profile — via the Slack REST API with curl. Triggers on "slack", "dm", "ping", "message X", "post in #channel", "read #channel", "reply on that thread", "send this file", "search slack". Faster and lighter on context than the MCP. Sets itself up on first use by reading your Slack session from Chrome.
user-invocable: true
argument-hint: "channel / person, and what to do"
---

# Slack via REST (no MCP)

Calls `https://slack.com/api/<method>` directly with your own Slack web session, so messages go out as you.

## First run: setup (do this automatically, don't make the user do it)

1. Check for saved credentials: `security dump-keychain | grep -o '"slack-[a-z0-9-]*-xoxc"'`.
2. If none (or any call returns `invalid_auth` / `token_expired` / `not_authed`), ask with exactly this one line (Slack has no token page; the session is read from Chrome):
   > Please open https://app.slack.com in Chrome, sign in, and say done (click Allow if macOS asks)
3. Once they say done, run the setup script below. It finds every signed-in workspace in Chrome,
   checks it with `auth.test`, and saves `slack-<workspace>-xoxc` and `slack-<workspace>-d` to the
   Keychain (`<workspace>` is the subdomain, e.g. `acme` for acme.slack.com). Nothing else is written anywhere.
4. Report which workspaces were saved. If none, ask them to sign in at app.slack.com in Chrome and retry.

```bash
python3 - <<'PY'
import glob, hashlib, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, urllib.request, urllib.parse
base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
pw = subprocess.run(["security","find-generic-password","-s","Chrome Safe Storage","-w"],capture_output=True,text=True).stdout.strip()
if not pw: sys.exit("Couldn't read 'Chrome Safe Storage' from Keychain (click Allow when macOS asks).")
key = hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", 1003, 16).hex()
def cookie(profile):
    tmp = tempfile.mktemp(); shutil.copy(os.path.join(profile,"Cookies"), tmp)
    db = sqlite3.connect(tmp); ver = int((db.execute("SELECT value FROM meta WHERE key='version'").fetchone() or [0])[0])
    row = db.execute("SELECT encrypted_value FROM cookies WHERE host_key='.slack.com' AND name='d'").fetchone(); db.close(); os.remove(tmp)
    if not row or row[0][:3] != b"v10": return None
    out = subprocess.run(["openssl","enc","-d","-aes-128-cbc","-K",key,"-iv","20"*16],input=row[0][3:],capture_output=True).stdout
    return (out[32:] if ver >= 24 else out).decode("utf8","ignore")
def test(tok, c):
    req = urllib.request.Request("https://slack.com/api/auth.test", data=b"", headers={"Authorization":f"Bearer {tok}","Cookie":f"d={urllib.parse.quote(c) if '%' not in c else c}"})
    return json.load(urllib.request.urlopen(req))
done = {}
for prof in glob.glob(base+"/Default")+glob.glob(base+"/Profile *"):
    if not os.path.exists(os.path.join(prof,"Cookies")): continue
    c = cookie(prof)
    if not c: continue
    toks = set()
    for f in glob.glob(prof+"/Local Storage/leveldb/*.[lL]*"):
        toks |= set(re.findall(rb"xoxc-[0-9A-Za-z-]{40,}", open(f,"rb").read()))
    for t in toks:
        r = test(t.decode(), c)
        ws = r.get("url","").split("//")[-1].split(".")[0]
        if not r.get("ok") or ws in done: continue
        done[ws] = r["user"]
        if True:
            for svc,val in ((f"slack-{ws}-xoxc",t.decode()),(f"slack-{ws}-d",c)):
                subprocess.run(["security","add-generic-password","-a",os.environ["USER"],"-s",svc,"-T","/usr/bin/security","-w",val,"-U"],check=True)
        print(f"saved: {ws} (team {r['team_id']}) as {r['user']}")
if not done: print("No logged-in Slack workspace found. Open https://app.slack.com in Chrome, sign in, then rerun.")
PY
```

Uses only macOS built-ins (`python3`, `openssl`, `security`). Chrome only; other browsers aren't read.

## The helper (paste into each Bash call, shell state doesn't persist)

Every call needs both `Authorization: Bearer <xoxc>` and `Cookie: d=<d>`.

```bash
slack() { local ws=$1 m=$2; shift 2
  local T=$(security find-generic-password -s slack-$ws-xoxc -w) C=$(security find-generic-password -s slack-$ws-d -w)
  local a=(); for kv in "$@"; do a+=(--data-urlencode "$kv"); done
  curl -s -X POST "https://slack.com/api/$m" -H "Authorization: Bearer $T" -H "Cookie: d=$C" "${a[@]}"; }
# usage: slack acme conversations.history channel=C123 limit=5 | jq .
findch() { local ws=$1 name=$2 cur=""; while :; do
  r=$(slack $ws conversations.list types=public_channel,private_channel exclude_archived=true limit=1000 cursor=$cur)
  id=$(printf %s "$r" | jq -r --arg n "$name" '.channels[]|select(.name==$n)|.id'); [ -n "$id" ] && { echo $id; return; }
  cur=$(printf %s "$r" | jq -r '.response_metadata.next_cursor // empty'); [ -z "$cur" ] && return 1; done; }
finduser() { local ws=$1 q=$2 cur=""; while :; do
  r=$(slack $ws users.list limit=1000 cursor=$cur)
  printf %s "$r" | jq -r --arg q "$q" '.members[]|select(.deleted|not)|select(((.real_name//"")+" "+.name+" "+(.profile.display_name//""))|ascii_downcase|contains($q|ascii_downcase))|"\(.id) \(.real_name) @\(.name)"'
  cur=$(printf %s "$r" | jq -r '.response_metadata.next_cursor // empty'); [ -z "$cur" ] && return; done; }
```

Never print the token or cookie. Save responses to a file or use `printf %s "$r"`, never zsh `echo` (it expands `\n` inside the JSON and jq fails). Check `.ok` on every response; on `false` read `.error`.
If only one workspace is saved, use it; if several and the user didn't say which, ask.

## Operations

| Task | Call |
|---|---|
| Send | `slack $WS chat.postMessage channel=$CH "text=$TEXT"` (thread: `thread_ts=$TS`; also post to channel: `reply_broadcast=true`) |
| DM someone | `DM=$(slack $WS conversations.open users=$U \| jq -r .channel.id)` then send to `$DM` |
| Draft | No API call: show the exact text and target, wait for the user's OK |
| Read channel | `slack $WS conversations.history channel=$CH limit=20` |
| Read thread | `slack $WS conversations.replies channel=$CH ts=$PARENT_TS` |
| Search messages | `slack $WS search.messages "query=foo in:#general from:@someone" count=20 sort=timestamp` |
| Find channel | `findch $WS <name>` (private channels have `G…` ids, not `C…`) |
| Find user | `finduser $WS <name>`; by email: `users.list` + `select(.profile.email=="x@y.com")` |
| Upload file | `slackfile $WS $CH <path> "<comment>" [thread_ts]` (below) |
| Delete | message: `slack $WS chat.delete channel=$CH ts=$TS`; file: `slack $WS files.delete file=$FID` (own only; confirm first) |
| Edit message | `slack $WS chat.update channel=$CH ts=$TS "text=$NEW"` |
| Unreact | `slack $WS reactions.remove channel=$CH timestamp=$TS name=eyes` |
| Channel info / members / pins | `conversations.info channel=$CH`, `conversations.members channel=$CH`, `pins.list channel=$CH` |
| Presence / full profile | `users.getPresence user=U123`, `users.profile.get user=U123` |
| React | `slack $WS reactions.add channel=$CH timestamp=$TS name=eyes` |
| Profile | `slack $WS users.info user=U123` |
| Link to a message | `slack $WS chat.getPermalink channel=$CH message_ts=$TS` |

### Upload a file (tested 01/10/2026: text file to a DM, content verified via `files.info`)

Works with session tokens. Three steps: get an upload URL, POST the bytes, complete into a channel.

```bash
slackfile() { local ws=$1 ch=$2 f=$3 msg=$4 ts=$5   # file to channel/DM, optional comment + thread
  local r=$(slack $ws files.getUploadURLExternal "filename=$(basename "$f")" length=$(wc -c < "$f" | tr -d ' '))
  local url=$(printf %s "$r" | jq -r .upload_url) id=$(printf %s "$r" | jq -r .file_id); [ "$url" = null ] && { echo "$r"; return 1; }
  curl -s -o /dev/null -F "file=@$f" "$url"
  local a=("files=[{\"id\":\"$id\",\"title\":\"$(basename "$f")\"}]" channel_id=$ch)
  [ -n "$msg" ] && a+=("initial_comment=$msg"); [ -n "$ts" ] && a+=(thread_ts=$ts)
  slack $ws files.completeUploadExternal "${a[@]}"; }
# usage: slackfile $WS $CH ./report.pdf "<@U123> Here's the report" [$THREAD_TS]
```

**Files the user gives you in this session:** a file dragged or @-referenced into Claude Code has a
local path, so pass that path. A pasted screenshot may exist only in context with no path on disk;
if so, ask the user to save it and give the path rather than inventing one. Never upload a file the
user didn't ask to send. After uploading, read back with `conversations.history limit=1` and check
`.files[0].name`; for text files `files.info file=$FID` returns `.content` to verify.

**Not supported with session tokens** (`not_allowed_token_type`): `chat.scheduleMessage` and
`users.lookupByEmail`. Say so and suggest scheduling it in the Slack app.

## Rules

- **Never guess a user id.** Resolve with `finduser`, and reuse ids already resolved in the conversation.
- Mentions are `<@USERID>`, channels `<#C123>`. `![](@USERID)` doesn't ping.
- Show names, not raw ids, when reading; convert `ts` to local time with `date -r <seconds>`.
- **One link per message.** Several URLs in one message can get mangled; send separate messages.
- If the user hasn't seen the exact wording, draft first. After sending, read it back and give the permalink.

**How to apply:** use this skill for every Slack request, even when a Slack MCP is connected. Don't call `slack_*` MCP tools. Exception: scheduling, which session tokens can't do.
