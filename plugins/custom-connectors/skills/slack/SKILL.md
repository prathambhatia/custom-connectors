---
name: slack
description: ALWAYS use this instead of the Slack MCP whenever Slack is mentioned or any Slack action is involved — send, reply in a thread, DM, edit, delete, upload a file, read a channel or thread, search messages/channels/users, react, read a profile — via the Slack REST API with curl. Triggers on "slack", "dm", "ping", "message X", "post in #channel", "read #channel", "reply on that thread", "send this file", "search slack". Faster and lighter on context than the MCP. Sets itself up on first use by reading your Slack session from Chrome. Also for any question about the Slack API itself (an endpoint, webhooks, a field), even when nothing is run.
user-invocable: true
argument-hint: "channel / person, and what to do"
---

# Slack via REST (no MCP)

Calls `https://slack.com/api/<method>` directly with your own Slack web session, so messages go out as you.

## First run: setup (do this automatically, don't make the user do it)

1. Check for saved credentials: `security dump-keychain | grep -o '"slack-[a-z0-9-]*-xoxc"'`.
2. If none (or any call returns `invalid_auth` / `token_expired` / `not_authed`), ask with exactly this one line (Slack has no token page; the session is read from Chrome):
   First open it for them in Chrome: `open -a "Google Chrome" https://app.slack.com`. Then ask:
   > Please sign in to Slack in the Chrome tab I just opened, then say done (click Allow if macOS asks)
3. Once they say done, run the setup script below. It finds every signed-in workspace in Chrome and the Slack app,
   checks it with `auth.test`, and saves `slack-<workspace>-xoxc` and `slack-<workspace>-d` to the
   Keychain (`<workspace>` is the subdomain, e.g. `acme` for acme.slack.com). Nothing else is written anywhere.
4. Report which workspaces were saved. If none, ask them to sign in at app.slack.com in Chrome and retry.

```bash
python3 - <<'PY'
import glob, hashlib, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, urllib.request, urllib.parse
SAVE = True
def secret(name):
    return subprocess.run(["security","find-generic-password","-s",name,"-w"],capture_output=True,text=True).stdout.strip()
def cookie(cookies_db, pw):
    if not pw or not os.path.exists(cookies_db): return None
    key = hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", 1003, 16).hex()
    tmp = tempfile.mktemp(); shutil.copy(cookies_db, tmp)
    db = sqlite3.connect(tmp); ver = int((db.execute("SELECT value FROM meta WHERE key='version'").fetchone() or [0])[0])
    row = db.execute("SELECT encrypted_value FROM cookies WHERE host_key='.slack.com' AND name='d'").fetchone(); db.close(); os.remove(tmp)
    if not row or row[0][:3] != b"v10": return None
    out = subprocess.run(["openssl","enc","-d","-aes-128-cbc","-K",key,"-iv","20"*16],input=row[0][3:],capture_output=True).stdout
    return (out[32:] if ver >= 24 else out).decode("utf8","ignore")
def tokens(base):
    # Slack keeps tokens in Local Storage and IndexedDB; compaction can hide one, so read both
    t = set(); files = glob.glob(base+"/Local Storage/leveldb/*") + glob.glob(base+"/IndexedDB/*slack.com*/**/*", recursive=True)
    for f in files:
        if os.path.isfile(f) and os.path.getsize(f) < 50_000_000:
            t |= set(re.findall(rb"xoxc-[0-9A-Za-z-]{40,}", open(f,"rb").read()))
    return t
# every place a signed-in Slack session can live: each Chrome profile, plus the Slack desktop app
chrome = os.path.expanduser("~/Library/Application Support/Google/Chrome")
desktop = os.path.expanduser("~/Library/Application Support/Slack")
sources = [(p, os.path.join(p,"Cookies"), "Chrome Safe Storage") for p in glob.glob(chrome+"/Default")+glob.glob(chrome+"/Profile *")]
sources.append((desktop, os.path.join(desktop,"Cookies"), "Slack Safe Storage"))
done = {}
for base, cdb, keyname in sources:
    if not os.path.exists(cdb): continue
    c = cookie(cdb, secret(keyname))
    if not c: continue
    for t in tokens(base):
        req = urllib.request.Request("https://slack.com/api/auth.test", data=b"", headers={"Authorization":f"Bearer {t.decode()}","Cookie":f"d={c if '%' in c else urllib.parse.quote(c)}"})
        r = json.load(urllib.request.urlopen(req))
        ws = r.get("url","").split("//")[-1].split(".")[0]
        if not r.get("ok") or ws in done: continue
        done[ws] = r["user"]
        if SAVE:
            for svc,val in ((f"slack-{ws}-xoxc",t.decode()),(f"slack-{ws}-d",c)):
                subprocess.run(["security","add-generic-password","-a",os.environ["USER"],"-s",svc,"-T","/usr/bin/security","-w",val,"-U"],check=True)
        src = "Slack app" if base == desktop else "Chrome " + os.path.basename(base)
        print(f"{'saved' if SAVE else 'found'}: {ws} (team {r['team_id']}) as {r['user']}, from {src}")
if not done: print("No signed-in Slack workspace found. Sign in to Slack in Chrome or the Slack app, then rerun.")
else: print(f"{len(done)} workspace(s): {', '.join(done)}")
PY
```

Uses only macOS built-ins (`python3`, `openssl`, `security`). It reads **every Chrome profile and the
Slack desktop app**, and saves each workspace that answers `auth.test`, so someone in five workspaces gets
all five. macOS may ask to allow access to "Slack Safe Storage" too; click **Allow**. Other browsers
(Safari, Arc, Brave) aren't read.

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
  printf %s "$r" | jq -r --arg q "$q" '.members[]|select(.deleted|not)|select(((.real_name//"")+" "+.name+" "+(.profile.display_name//"")+" "+(.profile.email//""))|ascii_downcase|contains($q|ascii_downcase))|"\(.id) \(.real_name) @\(.name)"'
  cur=$(printf %s "$r" | jq -r '.response_metadata.next_cursor // empty'); [ -z "$cur" ] && return; done; }
```

**Copy listed commands exactly; never guess an endpoint path.** For anything unlisted, see "Not in the table?". If a call returns 404, the path is wrong: recheck this file, don't try variations.


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
| Find user | `finduser $WS <name or email>` (pages through everyone; `users.lookupByEmail` is rejected for session tokens) |
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

**Not in the table?** Only then (anything listed above: use it as written, no lookup):
1. Find the method: `curl -s https://api.slack.com/methods/<method>` (e.g. `bookmarks.list`) and read its
   arguments. Call it with the `slack` helper as usual. If Slack answers `not_allowed_token_type`, session
   tokens can't use that method: say so.
Then make a **read-only** call first. For anything that creates, changes or deletes, show the exact call and
ask before running it. If a looked-up call fails, re-read its doc page; don't try variations of the path.

## Rules

- **Never guess a user id.** Resolve with `finduser`, and reuse ids already resolved in the conversation.
- Mentions are `<@USERID>`, channels `<#C123>`. `![](@USERID)` doesn't ping.
- Show names, not raw ids, when reading; convert `ts` to local time with `date -r <seconds>`.
- **One link per message.** Several URLs in one message can get mangled; send separate messages.
- If the user hasn't seen the exact wording, draft first. After sending, read it back and give the permalink.

**How to apply:** use this skill for every Slack request, even when a Slack MCP is connected. Don't call `slack_*` MCP tools. Exception: scheduling, which session tokens can't do.
