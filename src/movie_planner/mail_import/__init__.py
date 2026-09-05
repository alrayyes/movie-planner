"""Standalone mail-fetch tool: reads a configured mail source (IMAP or a
local mbox file), dispatches each message to an external per-chain
translation script, and emits import-ready rows. Deliberately outside
`movie_planner`'s own CLI/CRUD/CalDAV surface - see
openspec/changes/add-imap-pathe-mail-import/design.md.
"""
