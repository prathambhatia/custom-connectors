---
name: vercel-connector
description: ALWAYS use this instead of the Vercel MCP whenever Vercel is mentioned or a deploy, deployment, preview, production URL, build log, runtime log, env var, domain, alias, rollback or promote is involved — via the Vercel REST API with curl (no CLI needed). Triggers on "vercel", "deploy this", "redeploy", "why did the build fail", "build logs", "runtime logs", "add an env var", "rollback", "promote", "what's deployed". Faster and far lighter on context than the MCP's few hundred tools. Sets itself up on first use. Also for any question about the Vercel API itself (an endpoint, webhooks, a field), even when nothing is run.
user-invocable: true
argument-hint: "project and what to do (deploy / logs / env / rollback)"
---

# Vercel via REST (no MCP, no CLI)

Calls `https://api.vercel.com` directly with your own token. Doesn't need the `vercel` CLI.

## First run: setup (do this automatically)

1. Check: `security find-generic-password -s vercel-token -w >/dev/null 2>&1 && echo ok`.
2. If missing, or a call returns 401, or 403 with `"invalidToken":true` (Vercel's reply to a stale token):
   First open the page for them: `open "https://vercel.com/account/settings/tokens"` (opens in their default browser; if they're
   logged out they see that service's login page first, and may need to open the link again after). Then ask with this one line, optionally starting with "I've opened the … page in your browser.":
   > Please give your Vercel access token from here: https://vercel.com/account/settings/tokens
3. **Test the token first, save only if it works.** Put what they pasted into `T` (single quotes),
   never echo it back:
   ```bash
   T='<PASTED>'; code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $T" https://api.vercel.com/v2/user)
   if [ "$code" = 200 ]; then security add-generic-password -a "$USER" -s vercel-token -l "Vercel Token" -T /usr/bin/security -w "$T" -U && echo SAVED
   else echo "REJECTED (HTTP $code)"; fi; unset T
   ```
   On `REJECTED`, nothing is saved. Tell them in one line and ask again:
   > That token didn't work (HTTP <code>). Please copy it again from: https://vercel.com/account/settings/tokens

   Common causes: a partial copy, extra spaces, or a token from another account. On `SAVED`, carry on
   with what they originally asked.
4. Then find their team id (every call below needs it):
   ```bash
   v GET v2/user > u.json; jq -r '.user.username, .user.defaultTeamId' u.json
   v GET v2/teams > t.json; jq -r '.teams[]|"\(.id) \(.slug)"' t.json
   ```
   Set `TEAM` to `defaultTeamId` (or the team they name) for the rest of the session.

## Helper

```bash
TEAM=<team id from setup>
v() { local m=$1 p=$2; shift 2; curl -s -X $m -H "Authorization: Bearer $(security find-generic-password -s vercel-token -w)" \
  -H "Content-Type: application/json" "https://api.vercel.com/$p" "$@"; }
# usage: v GET "v10/projects?teamId=$TEAM&limit=20" > p.json; jq . p.json
```

**Copy listed commands exactly; never guess an endpoint path.** For anything unlisted, see "Not in the table?". If a call returns 404, the path is wrong: recheck this file, don't try variations.


Paste into each Bash call. Save to files, don't pipe JSON through zsh `echo`. Errors look like
`{"error":{"code":…,"message":…}}`. On 401, or 403 with `invalidToken`, rerun setup.

## Operations

| Task | Call |
|---|---|
| Who am I | `v GET v2/user` |
| List / find projects | `v GET "v10/projects?teamId=$TEAM&limit=100&search=<name>"` |
| Project details | `v GET "v9/projects/$P?teamId=$TEAM"` (`$P` = id or name; `.targets.production.alias`) |
| Update project settings | `v PATCH "v9/projects/$P?teamId=$TEAM" -d '{"buildCommand":"npm run build"}'` |
| List deployments | `v GET "v6/deployments?projectId=$P&teamId=$TEAM&limit=10&target=production"` (`state=ERROR` to find failures) |
| Deployment status | `v GET "v13/deployments/$D?teamId=$TEAM"` → `.readyState` (QUEUED/BUILDING/READY/ERROR), `.alias` |
| Build logs | `v GET "v3/deployments/$D/events?teamId=$TEAM&builds=1&limit=-1" > ev.json; jq -r '.[].text' ev.json` |
| Runtime logs | **live stream only**, see below |
| Redeploy | `v POST "v13/deployments?teamId=$TEAM&forceNew=1" -d '{"name":"<project>","deploymentId":"'$D'","target":"production"}'` (picks up env changes) |
| Deploy local files | see "Deploy a folder" below |
| Promote / rollback | `v POST "v9/projects/$P/promote/$D?teamId=$TEAM" -d '{}'` → 201. Promote an older READY deployment = rollback |
| Aliases | `v GET "v2/deployments/$D/aliases?teamId=$TEAM"` |
| Env: list / add / read value / edit / delete | `v GET "v10/projects/$P/env?teamId=$TEAM"`; `v POST "v10/projects/$P/env?teamId=$TEAM&upsert=true" -d '{"key":"K","value":"V","type":"encrypted","target":["production","preview"]}'`; `v GET "v1/projects/$P/env/$EID?teamId=$TEAM"` (decrypted `.value`); `v PATCH "v9/projects/$P/env/$EID?teamId=$TEAM" -d '{"value":"V2"}'`; `v DELETE "v9/projects/$P/env/$EID?teamId=$TEAM"` |
| Domains | project: `v GET "v9/projects/$P/domains?teamId=$TEAM"`; account: `v GET "v5/domains?teamId=$TEAM"` |
| Delete deployment / project | `v DELETE "v13/deployments/$D?teamId=$TEAM"`; `v DELETE "v9/projects/$P?teamId=$TEAM"` → 204. **Irreversible, confirm first** |

**Env changes don't apply until you redeploy.** Tested: the function returned the new value only
after a redeploy. Don't print decrypted env values unless asked; they're live secrets.

### Wait for a deploy

```bash
for i in $(seq 1 45); do v GET "v13/deployments/$D?teamId=$TEAM" > s.json; st=$(jq -r .readyState s.json)
  [ "$st" = READY -o "$st" = ERROR ] && break; sleep 4; done; echo "$st $(jq -r '.alias[0]' s.json)"
```

On ERROR, read the build logs and show the last ~30 lines.

### Runtime logs (stream; there's no history endpoint here)

`GET v1/projects/$P/deployments/$D/runtime-logs` streams logs **as they happen** and returns nothing for
past requests (tested: a plain call gave 0 lines; streaming while hitting the URL caught every line).
So start the stream, then trigger or wait for traffic:

```bash
( curl -s -m 60 -N "https://api.vercel.com/v1/projects/$P/deployments/$D/runtime-logs?teamId=$TEAM" \
  -H "Authorization: Bearer $(security find-generic-password -s vercel-token -w)" > rl.txt ) &
sleep 3; curl -s -o /dev/null https://<url>/api/thing; wait
jq -r '"\(.level) \(.requestPath) \(.message)"' rl.txt
```

For past errors use the Vercel dashboard's Logs tab, or say plainly that history isn't available.

### Deploy a folder (no git, no CLI)

Upload each file by SHA-1, then create the deployment from the list. Tested with a static page plus
one `api/` function.

```bash
cd <folder>; FILES='[]'
for f in $(git ls-files 2>/dev/null || find . -type f ! -path './node_modules/*' ! -path './.git/*' | sed 's|^\./||'); do
  SHA=$(shasum -a 1 "$f" | cut -d' ' -f1)
  curl -s -o /dev/null -X POST -H "Authorization: Bearer $(security find-generic-password -s vercel-token -w)" \
    -H "x-vercel-digest: $SHA" -H "Content-Type: application/octet-stream" --data-binary @"$f" "https://api.vercel.com/v2/files?teamId=$TEAM"
  FILES=$(jq -c --arg f "$f" --arg s "$SHA" --argjson z $(wc -c < "$f" | tr -d ' ') '.+[{file:$f,sha:$s,size:$z}]' <<<"$FILES"); done
jq -n --argjson files "$FILES" '{name:"<project>",files:$files,projectSettings:{framework:null},target:"production"}' > /tmp/vbody.json
v POST "v13/deployments?teamId=$TEAM&skipAutoDetectionConfirmation=1" -d @/tmp/vbody.json > dep.json; jq -r '.id, .url' dep.json
```

Drop `"target":"production"` for a preview. For a project linked to git, prefer pushing to the branch
over uploading files. First deploy creates the project.

**Not in the table?** Only then (anything listed above: use it as written, no lookup):
1. Search Vercel's OpenAPI spec locally (it's 11 MB, never read it whole):
   `curl -s https://openapi.vercel.sh/ > /tmp/vercel-openapi.json; jq -r '.paths|keys[]' /tmp/vercel-openapi.json | grep -i <word>`
2. Read just that path's parameters: `jq '.paths["/v2/domains/{domain}/records"]' /tmp/vercel-openapi.json`
3. Call it with the `v` helper, adding `teamId=$TEAM`.
Then make a **read-only** call first. For anything that creates, changes or deletes, show the exact call and
ask before running it. If a looked-up call fails, re-read its doc page; don't try variations of the path.

## Traps

- **Deployment Protection is on by default** for new projects (`ssoProtection: all_except_custom_domains`):
  the `*.vercel.app` production alias is public, but unique deployment URLs ask for a Vercel login. To
  check a protected preview, open it in a browser where you're logged in to Vercel.
- Timestamps (`created`, `timestampInMs`) are ms. Local time: `date -r $((MS/1000)) '+%b %d %I:%M %p'`.
- A deleted project's URL can keep serving for ~20s from cache before going 404.

**How to apply:** use this for every Vercel request, even when the Vercel MCP is connected. Don't call
its tools. Show the user the production alias (or deployment URL) after any deploy.
