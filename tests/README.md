# Reliability tests (maintainer only)

Not part of the plugin: `/plugin install` only copies `plugins/custom-connectors/`, so users never load or run this.

Each case runs in a fresh Claude Code session with only this plugin installed and every MCP off, then gets
scored: **task done** (final answer matches the expected regex) and **first try** (no API call failed on the way).

```bash
cp cases.example.tsv cases.tsv     # once; fill in real ids and expected answers (git-ignored, keep it private)
./run.sh                           # all cases, 2 runs each, max $25
./run.sh -n 3 fathom-last aws-rds  # just these, 3 runs each
```

Uses `~/claude-connector-test` (a Claude config with the plugin installed and logged in); override with
`CONN_TEST_CONFIG`. Each run costs about $0.15-0.65. Chrome cases always run one at a time.
