# pathe-mail-import

A standalone tool that reads a mailbox (IMAP, or a local mbox file),
finds cinema booking confirmations, and turns them into a JSON file
`movie-planner import` accepts - entirely separate from `movie-planner`
itself. Neither knows the other exists: `movie-planner --help` never
mentions Pathé or IMAP, and this tool never touches the store or the
CalDAV calendar. See [`README.md`](../README.md) for `movie-planner`
itself.

![pathe-mail-import --help](img/pathe-mail-import-help.svg)

## Requirements

- The same [uv](https://docs.astral.sh/uv/)-managed checkout
  `movie-planner` itself uses - there's no separate install; both
  tools come from `uv sync` in this repo.
- An IMAP mailbox (a local [Proton Mail
  Bridge](https://proton.me/mail/bridge) instance, or a Gmail account
  with an app password), or a local mbox-format file (mutt's own
  storage, or Thunderbird's default local-folder format, which is also
  plain mbox).
- One translation script per cinema chain you want recognized -
  `pathe-translate` (also installed by `uv sync`) covers Pathé.

## Installation

From a checkout, same as `movie-planner`:

```sh
git clone https://github.com/alrayyes/movie-planner.git
cd movie-planner
uv sync
```

This installs three commands into the project's `.venv`:
`pathe-mail-import` (this tool), `pathe-translate` (Pathé's own
translation script), and `movie-planner` itself.

**Not currently packaged the way `movie-planner` is** - no AUR
package, no `.deb`/`.rpm`, no published Docker image. It _can_ be
built as its own container image from this same checkout
(`docker build --target pathe-mail-import -t pathe-mail-import .`,
sharing the base image and dependency layers `movie-planner`'s own
image build already has), but that image isn't published to a
registry anywhere yet - building it yourself is the only way to get
it as a container today.

Man pages exist too (`pathe-mail-import.1`, `pathe-mail-import-init.1`,
`pathe-mail-import-fetch.1`), generated the same way `movie-planner`'s
own are - `./scripts/generate-man.sh` writes them to `man/` from a
checkout. They aren't installed anywhere automatically without a
package, same caveat as the preceding paragraph.

## Configuration

A TOML file at `$XDG_CONFIG_HOME/pathe-mail-import/config.toml`
(`~/.config/pathe-mail-import/config.toml` if `XDG_CONFIG_HOME` isn't
set) - its own default path, separate from `movie-planner`'s own
`config.toml`, but the two can share one file (issue #157): point
`--config` at the same path as `movie-planner`'s and `pathe-mail-import
init` adds its own `[mail_import]` section alongside `movie-planner`'s
`[movie_planner]` one, rather than overwriting the file.

```toml
[mail_import.mail]
source = "imap"          # or "mbox", or "maildir"

[mail_import.mail.imap]
host = "127.0.0.1"
port = 1143
username = "you@example.com"
password = "..."
# Or, instead of a plaintext password above, run a command that prints
# it to stdout (e.g. a password manager) - set only one of the two:
# password_command = "pass show imap/pathe-mail-import"

# [mail_import.mail.mbox]
# path = "~/Mail/INBOX"
# extra_paths = ["~/Mail/Archive"]

# [mail_import.mail.maildir]
# path = "~/.local/share/mail/gmail/Archive"

[[mail_import.chains]]
sender_domain = "service.pathe.nl"
translate = "pathe-translate"
```

An older config file with `[mail]`/`[[chains]]` at the top level (no
`[mail_import]` wrapper) still loads exactly as before - nothing to
migrate for an existing setup.

For a mbox source, `path` stays the one required, standard mailbox
(INBOX, typically) - `extra_paths` is optional, and scans one or more
additional mbox files (for example, a `Archive` folder a mail client
moved older messages into) in the same `fetch` run, merging the
results (issue #188). A message present in more than one configured
file (matched by its `Message-ID`) is only ever counted once.

Real Pathé booking confirmations come from `service.pathe.nl`, not the
bare `pathe.nl` domain - other Pathé mail (the newsletter, a club
membership invoice) uses other subdomains and is correctly left
unrecognized by a chain scoped this narrowly.

**One project's history can span more than one mail account, not just
more than one folder of the same account** (issue #200). `extra_paths`
above only adds more mbox files to a single `MboxMailClient` run - a
completely different account (a different mailbox, possibly a different
provider) needs its own `pathe-mail-import fetch --config <path>`
invocation against its own config file, even if it's a different
`source` kind (`--source maildir` for a mutt-synced account with no
mbox copy, say).

For a Maildir source, `path` points at the Maildir directory itself
(the folder holding `cur`/`new`/`tmp`, not one of those three) - mutt's
own default local sync format (issue #208), which
`MboxMailClient`/`extra_paths` can't read regardless of how many mbox
files are configured, since a Maildir mailbox is one file per message
rather than a single mbox file.

Run `pathe-mail-import init` to write a starter copy interactively -
it prompts for anything not given as a flag, or fails clearly (rather
than hanging) if it isn't running in a terminal and a required value
is missing. The IMAP password is never accepted as a flag, only a
masked interactive prompt or `--imap-password-command` - the same
shell-history/process-list concern `movie-planner`'s own CalDAV
password already avoids the same way.

```sh
pathe-mail-import init --source imap --imap-host 127.0.0.1 \
  --imap-port 1143 --imap-username you@example.com
```

## Usage

Fetch everything a configured chain recognizes and write it to a file:

```sh
pathe-mail-import fetch --output import.json
movie-planner import import.json
```

Any email a configured chain's sender domain matches, but its
translation script doesn't recognize, is never written to
`--output` - it's printed as a review table instead:

```text
Wrote 3 row(s) to import.json.

1 email(s) not recognized by any configured chain:
From                          Subject                Date
Pathé Nederland <noreply@...> Your weekly newsletter  2026-07-05
```

`--since`/`--until` scope a run to a date range, for a cron job that
only wants to re-check its own window each time rather than the whole
mailbox - the tool itself keeps no state between runs, so the caller
computing that window is what makes a scoped run possible:

```sh
pathe-mail-import fetch --output import.json --since "1 hour ago"
```

### Composing it by hand instead

`fetch --envelopes-only` and `movie-planner import`'s own stdin
support mean the whole thing can be a real shell pipe instead of two
commands and a temp file:

```sh
pathe-mail-import fetch --envelopes-only \
  | pathe-translate \
  | movie-planner import
```

An email a chain matches but the script doesn't recognize gets a
diagnostic on stderr in this mode (visible directly in the terminal,
since a pipe never reaches stderr) rather than a review table - there's
no coordinating process left to build one.

## Adding a second cinema chain

Nothing in `pathe-mail-import` itself knows about Pathé - `[[chains]]`
just maps a sender domain to an external command. A new chain is a new
translation script plus a new `[[chains]]` entry, no changes to this
tool's own code:

- **Input**: one JSON envelope per line on stdin - `{"from": "...",
"subject": "...", "date": "...", "body": "..."}`.
- **Output**: for a recognized email, one
  [`movies.schema.json`](../examples/movies.schema.json)-shaped JSON
  row on stdout (`source` is overwritten by `pathe-mail-import` itself
  with the matched sender domain, so the script doesn't need to set
  it). For anything it doesn't recognize: nothing on stdout, a
  diagnostic on stderr, and (when it's the last line read) a non-zero
  exit.
- Any language - the contract is stdin/stdout/exit code, not a Python
  API. `pathe-translate` (this repo's own
  [`src/movie_planner/mail_import/pathe_translate.py`](../src/movie_planner/mail_import/pathe_translate.py))
  is a small, readable reference implementation wrapping
  `movie_planner.pathe.parse_pathe_email`.

## Contributing and licence

Same repository, same [`CONTRIBUTING.md`](../CONTRIBUTING.md) and
[licence](../LICENSE) as `movie-planner` itself.
