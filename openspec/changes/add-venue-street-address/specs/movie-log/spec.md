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
that hardcoded table, dry-run by default, `--apply` to write - a full
resync of those fields to the table's current values for a matching
venue, since the only way they're ever set is by that same table in the
first place. A venue row whose name isn't in the table at all is left
untouched.

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

#### Scenario: Refresh leaves an unmatched venue untouched
- **WHEN** a venue row's name has no entry in the hardcoded table at all
- **THEN** refreshing leaves that row completely unchanged
