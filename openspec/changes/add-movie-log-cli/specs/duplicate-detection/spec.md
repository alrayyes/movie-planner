## Purpose

Flags likely-duplicate viewing entries before they're added, using
fuzzy title matching and date proximity, without blocking legitimate
rewatches on a different day.

## ADDED Requirements

### Requirement: Detect a likely duplicate
The system SHALL compare a candidate entry's normalized title against
existing entries' normalized titles using fuzzy matching, and SHALL
flag a candidate as a likely duplicate only when its fuzzy match score
is above a configured threshold AND its date is the same day as the
matched existing entry.

#### Scenario: Same title, same day
- **WHEN** a candidate entry's title fuzzy-matches an existing entry
  above the threshold and both share the same date
- **THEN** the candidate is flagged as a likely duplicate

#### Scenario: Same title, different day
- **WHEN** a candidate entry's title fuzzy-matches an existing entry
  above the threshold but the dates differ
- **THEN** the candidate is not flagged as a duplicate

### Requirement: Title normalization before matching
The system SHALL normalize titles — case-folded, punctuation-
insensitive, with known noise suffixes such as trailing " - Movies"
stripped — before fuzzy comparison.

#### Scenario: Suffix noise ignored
- **WHEN** a candidate titled "Midnight Ferry: Part Two" is compared
  against an existing entry titled "Midnight Ferry: Part Two -
  Movies" logged the same day
- **THEN** the two are treated as matching for duplicate detection

### Requirement: Confirm before adding in interactive logging
When interactive logging flags a likely duplicate, the system SHALL
show the matched existing entry and ask for confirmation before saving
the new entry.

#### Scenario: User confirms a rewatch
- **WHEN** a flagged entry is confirmed by the user
- **THEN** the entry is saved as normal

### Requirement: Skip and report during bulk import
When a bulk import flags a row as a likely duplicate, the system SHALL
skip persisting that row by default and SHALL include it in an
end-of-import summary, unless the import is run with a force option.

#### Scenario: Import with duplicates, default behavior
- **WHEN** a bulk import contains a row that is a likely duplicate of
  an existing entry
- **THEN** that row is not persisted, and it is listed in the import
  summary

#### Scenario: Import with force option
- **WHEN** a bulk import is run with the force option and contains a
  row that is a likely duplicate
- **THEN** that row is persisted despite being flagged
