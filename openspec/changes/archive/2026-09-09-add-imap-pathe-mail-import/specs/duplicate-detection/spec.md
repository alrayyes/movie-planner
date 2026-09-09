## ADDED Requirements

### Requirement: Detect an overlapping screening time
The system SHALL flag a candidate entry as a likely duplicate when its
screening time overlaps an existing entry's screening time on the same
date, independent of title similarity. Each entry's time range is
`[start_time, end_time)` when both are known, or a zero-width point at
`start_time` when only that is known; each range is expanded by a
30-minute buffer on both ends before comparing for overlap. An entry
with no time at all (date-only) SHALL NOT be compared this way - it is
only subject to the existing fuzzy-title/same-day check.

#### Scenario: Overlapping times, different titles
- **WHEN** a candidate entry's buffered time range overlaps an existing
  same-day entry's buffered time range, and the titles do not
  fuzzy-match
- **THEN** the candidate is flagged as a likely duplicate

#### Scenario: Overlapping times, same title
- **WHEN** a candidate entry's buffered time range overlaps an existing
  same-day entry's buffered time range, and the titles also fuzzy-match
- **THEN** the candidate is flagged as a likely duplicate (same outcome
  as the existing title-based check, not a second, separate flag)

#### Scenario: Same day, no time overlap
- **WHEN** a candidate entry's buffered time range does not overlap any
  existing same-day entry's buffered time range
- **THEN** this check does not flag the candidate (the existing
  fuzzy-title/same-day check still applies independently)

#### Scenario: Candidate has no time data
- **WHEN** a candidate entry has no `start_time`
- **THEN** this check does not apply to it, regardless of any existing
  entry's time
