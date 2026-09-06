from movie_planner.venue_locations import KNOWN_VENUE_LOCATIONS

# --- canonical_name: issue #196 ---


def test_every_alias_in_a_group_shares_the_same_canonical_name() -> None:
    group = ["De Munt", "De Munt 4DX", "De Munt Dolby", "De Munt Relax", "De Munt Dolby Cinema"]

    canonical_names = {KNOWN_VENUE_LOCATIONS[name].canonical_name for name in group}

    assert canonical_names == {"De Munt"}


def test_a_single_name_group_is_its_own_canonical_name() -> None:
    assert KNOWN_VENUE_LOCATIONS["Tuschinski"].canonical_name == "Tuschinski"


def test_canonical_name_is_the_first_name_listed_in_its_group() -> None:
    # "City"/"Pathé City" - "City" is listed first, so it's canonical.
    assert KNOWN_VENUE_LOCATIONS["City"].canonical_name == "City"
    assert KNOWN_VENUE_LOCATIONS["Pathé City"].canonical_name == "City"


def test_every_known_venue_location_has_a_canonical_name_that_is_itself_a_key() -> None:
    # Every alias's canonical_name must itself be a real, resolvable key
    # in the table - otherwise resolving an alias to its canonical name
    # and then looking that up again would silently fail.
    for name, location in KNOWN_VENUE_LOCATIONS.items():
        assert location.canonical_name in KNOWN_VENUE_LOCATIONS, (
            f"{name!r}'s canonical_name {location.canonical_name!r} isn't itself a known name"
        )
