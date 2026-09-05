## Purpose

Fetches cinema booking-confirmation emails from a configured mail
source and turns the ones it recognizes into an import-ready JSON file,
entirely outside movie-planner's own CRUD/CalDAV surface.

## ADDED Requirements

### Requirement: Fetch mail from a configured source
The system SHALL support at least two interchangeable mail sources,
selected by configuration, both searched the same way for messages from
configured cinema-chain sender domains and both producing the same
envelope shape for everything downstream:
- **IMAP** (host, port, username, and a password or password command).
  The same client SHALL work against either a local Proton Mail Bridge
  instance or a Gmail account with no chain-specific connection logic.
- **A local mbox file** - any standard mbox-format mailbox (mutt's own
  storage, or Thunderbird's default local-folder format, which is also
  plain mbox), read directly from disk with no network connection or
  credentials involved.

#### Scenario: Successful IMAP connection and search
- **WHEN** the tool runs with valid IMAP configuration and at least one
  configured sender domain
- **THEN** it connects to the mailbox and retrieves every message from
  a configured sender domain

#### Scenario: IMAP connection failure
- **WHEN** the configured IMAP host, credentials, or mailbox is invalid
- **THEN** the tool reports the connection failure and does not produce
  a partial or corrupt output file

#### Scenario: Successful mbox read
- **WHEN** the tool runs configured to read a local mbox file and at
  least one configured sender domain
- **THEN** it reads the file and retrieves every message from a
  configured sender domain, with no network access attempted

#### Scenario: mbox file missing or unreadable
- **WHEN** the configured mbox file path doesn't exist or can't be read
- **THEN** the tool reports that failure and does not produce a partial
  or corrupt output file

#### Scenario: Same dispatch regardless of source
- **WHEN** the same message is available both via IMAP and in a local
  mbox export of the same mailbox
- **THEN** it produces the same envelope, and is dispatched to the same
  chain's translation script, either way

### Requirement: Dispatch each email to its chain's translation script
For each fetched message, the system SHALL extract a plain envelope
(sender address, subject, date, and the plain-text body) and SHALL
invoke the external translation script configured for that sender's
domain, passing it the envelope and reading a parsed result back. No
chain-specific parsing logic SHALL exist inside the tool itself.

#### Scenario: Sender domain has a configured translation script
- **WHEN** a fetched email's sender domain matches a configured chain
- **THEN** that chain's translation script is invoked with the email's
  envelope and its result is used

#### Scenario: Sender domain has no configured translation script
- **WHEN** a fetched email's sender domain matches no configured chain
- **THEN** the email is treated as unrecognized, the same as a
  configured script that fails to parse it

### Requirement: Emit every recognized booking as one import row
The system SHALL write every email a translation script successfully
parses as one row in a single output JSON file, matching
`examples/movies.schema.json`'s row shape, and SHALL NOT include a
`booking_ref` field on any row. The system SHALL set each row's
`source` field to the sender domain that matched it, regardless of
what the translation script itself returned for that field.

#### Scenario: One or more bookings recognized
- **WHEN** at least one fetched email is successfully parsed
- **THEN** the output file contains one row per successfully parsed
  email, valid against `examples/movies.schema.json`, each with
  `source` set to the sender domain that matched it (for example
  `"pathe.nl"`)

#### Scenario: No bookings recognized
- **WHEN** no fetched email is successfully parsed
- **THEN** the output file is an empty array, not omitted or malformed

### Requirement: Report unrecognized email for manual review
The system SHALL display every email that no configured translation
script could parse as a table of its sender, subject, and date, and
SHALL NOT include it in the output JSON file.

#### Scenario: An email fails every configured chain's parsing
- **WHEN** a fetched email's translation script exits indicating it
  doesn't recognize the email, or no chain is configured for its sender
  domain
- **THEN** the email's sender, subject, and date are shown to the user,
  and no row is written for it

### Requirement: No knowledge of what's already logged
The system SHALL NOT read movie-planner's store or CalDAV calendar, and
SHALL NOT track which emails were processed on a previous run. Every
run SHALL re-fetch and re-emit every currently-matching email in the
mailbox.

#### Scenario: Running the tool twice
- **WHEN** the tool is run twice against an unchanged mailbox
- **THEN** both runs produce the same set of rows, independent of
  whether the first run's output was ever imported
