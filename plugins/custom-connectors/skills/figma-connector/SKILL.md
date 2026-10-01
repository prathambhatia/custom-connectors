---
name: figma-connector
description: ALWAYS use this instead of the Figma MCP for READING Figma — file structure, pages, frames, a node's properties, rendering a frame/node to PNG/SVG, image fills, version history, comments (read, post, reply, react, delete), dev resources — via the Figma REST API with curl. Triggers on "figma", a figma.com/design or figma.com/file link, "what's in this frame", "export this frame", "figma comments", "who changed the figma". NOT for editing designs or design-to-code: the REST API can't do those, so keep the Figma MCP for that. Sets itself up on first use.
user-invocable: true
argument-hint: "figma link or file key, and what you want"
---

# Figma via REST (read-only replacement for the MCP)

Calls `https://api.figma.com` directly with your own personal access token.

**What REST can't do, so keep the Figma MCP for it:** edit or create anything in a design
(`use_figma`), design-to-code context (`get_design_context`), Code Connect, FigJam/Slides authoring.
This skill covers reading, rendering and comments only.

## First run: setup (do this automatically)

1. Check: `security find-generic-password -s figma-token -w >/dev/null 2>&1 && echo ok`.
2. If missing, or a call returns `{"status":401,"err":"Invalid token"}` (or "Token has expired"):
   First open the page for them: `open "https://www.figma.com/settings"` (opens in their default browser; if they're
   logged out they see that service's login page first, and may need to open the link again after). Then ask with this one line, optionally starting with "I've opened the … page in your browser.":
   > Please give your Figma personal access token from here: the Figma settings page I just opened, Security tab, Personal access tokens, Generate
3. Save it, then check it with `fg GET v1/me` (shows the account it belongs to; tell them, since
   comments will be posted as that account):
   ```bash
   security add-generic-password -a "$USER" -s figma-token -l "Figma PAT" -T /usr/bin/security -w "<TOKEN>" -U
   ```
   Don't echo the token back.

## Helper

Header **`X-Figma-Token`**.

```bash
fg() { local m=$1 p=$2; shift 2; curl -s -X $m -H "X-Figma-Token: $(security find-generic-password -s figma-token -w)" \
  -H "Content-Type: application/json" "https://api.figma.com/$p" "$@"; }
# usage: fg GET "v1/files/$K?depth=2" > f.json; jq . f.json
```

**Copy the commands below exactly; never guess an endpoint path.** If a call returns 404, the path is wrong: recheck this file, don't try variations.


Paste into each Bash call; save to files (Figma JSON is huge), never pipe through zsh `echo`. On
401, rerun setup.

## Reading a link

`https://www.figma.com/design/<FILE_KEY>/<name>?node-id=12-345` → file key `<FILE_KEY>`,
node id **`12:345`** (URL uses `-`, the API uses `:`). URL-encode ids in query strings (`%3A`).

## Operations

| Task | Call |
|---|---|
| Who am I | `fg GET v1/me` |
| File metadata (cheap) | `fg GET v1/files/$K/meta` → name, editor type, your role |
| Pages + top frames | `fg GET "v1/files/$K?depth=2"` → `.document.children[]` (pages) and their `.children` (frames). **Always pass `depth`**; the full file is many MB |
| Specific nodes | `fg GET "v1/files/$K/nodes?ids=$N1,$N2&depth=2"` → `.nodes[$id].document` (type, size in `absoluteBoundingBox`, fills, text in `.characters`) |
| Vector geometry | add `&geometry=paths` |
| Render to image | `fg GET "v1/images/$K?ids=$N&format=png&scale=2"` → `.images[$id]` is a temporary S3 URL; `curl -s -o out.png "$URL"`, then Read the PNG to see it. Formats: `png`, `jpg`, `svg`, `pdf` |
| Image fills used in file | `fg GET v1/files/$K/images` → `.meta.images` (ref → URL) |
| Version history | `fg GET v1/files/$K/versions` → `.versions[]` (`created_at`, `user.handle`, `label`) |
| Read an old version | `fg GET "v1/files/$K?version=<version_id>&depth=1"` |
| Comments: read | `fg GET v1/files/$K/comments` → `.comments[]` (`message`, `user.handle`, `client_meta.node_id`, `resolved_at`) |
| Comments: post / reply | `fg POST v1/files/$K/comments -d '{"message":"…","client_meta":{"node_id":"'$N'","node_offset":{"x":0,"y":0}}}'`; reply: `-d '{"message":"…","comment_id":"'$CID'"}'` |
| Comments: delete | `fg DELETE v1/files/$K/comments/$CID` (own comments only) |
| Reactions | `fg POST v1/files/$K/comments/$CID/reactions -d '{"emoji":":eyes:"}'`; list `GET …/reactions`; remove `DELETE "…/reactions?emoji=%3Aeyes%3A"` |
| Published components / styles | `fg GET v1/files/$K/components`, `…/component_sets`, `…/styles` (only **published library** items) |
| Dev resources | `fg GET v1/files/$K/dev_resources` |

**Comments notify people and show the token owner's name.** Draft the text, confirm with
the user before posting, and delete test comments straight away.

## Not available with this token

- **Variables** (`/variables/local`) → 403 `requires the file_variables:read scope`. Enterprise-only;
  read colours/typography from the Styleguide page's nodes instead.
- Listing teams isn't in the API. Projects need a team id from a URL:
  `figma.com/files/team/<TEAM_ID>/…` → `fg GET v1/teams/<TEAM_ID>/projects`, then
  `fg GET v1/projects/<id>/files`.

## Traps

- A whole-file `GET` without `depth` can be tens of MB and very slow. Start with `depth=2`, then
  fetch exactly the node ids you need.
- Render URLs expire (about 30 days) and are S3 links; download, don't paste them as permanent.
- Tall mobile frames render very tall . Use a
  small `scale` for overviews.
- Rate limits are per plan and per file; on 429, wait the `Retry-After` header.

**How to apply:** for anything Figma that only needs reading, rendering or comments, use this skill
instead of the Figma MCP. For edits or design-to-code, load the `figma:*` skills and use the MCP.
