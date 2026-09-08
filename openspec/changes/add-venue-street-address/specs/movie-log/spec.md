## MODIFIED Requirements

### Requirement: User-editable medium and venue lists
The system SHALL let the user add, list, and remove values from the
medium list and the venue list, and SHALL offer only currently-defined
values, plus an option to add a new one, when prompting. A venue whose
name matches a hardcoded chain/location table SHALL have its chain,
city, and country filled in automatically; a venue that doesn't match
gets none of that, never a guess. The system SHALL also let the user
refresh an already-existing venue row's chain, city, country,
coordinates, street address, and postal code from the current state of
that hardcoded table, dry-run by default, only ever filling in a field
the table verifies that the row doesn't already carry - never
overwriting a value the row already has with a different one.

#### Scenario: Adding a new venue
- **WHEN** the user adds venue "Starlight Cinema" via the locations command
- **THEN** "Starlight Cinema" appears as a selectable venue on subsequent log
  entries

#### Scenario: Adding a venue matching the chain/location table
- **WHEN** the user adds a venue whose name matches the hardcoded table
- **THEN** the venue's chain, city, and country are set automatically

#### Scenario: Removing a medium in use
- **WHEN** the user attempts to remove a medium that existing entries
  reference
- **THEN** the system rejects the removal and explains which entries
  reference it

#### Scenario: Refreshing an existing venue row that predates a table update
- **WHEN** the user refreshes venue locations with `--apply`, for a venue
  row created before the hardcoded table gained new verified fields for it
- **THEN** the row is updated to match the table's current values for
  every field the table has confirmed

#### Scenario: Refresh without --apply only reports what would change
- **WHEN** the user runs the refresh command without `--apply`
- **THEN** no venue row is modified, and the command reports which rows
  would change and how

#### Scenario: Refresh never overwrites an already-set field with nothing
- **WHEN** a venue row already has a value for a field the table doesn't
  have for that venue
- **THEN** refreshing that row leaves the existing value untouched
