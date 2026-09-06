from movie_planner.venue_locations import KNOWN_VENUE_LOCATIONS

# --- canonical_name: issue #196 ---


def test_every_alias_in_a_group_shares_the_same_canonical_name() -> None:
    group = ["De Munt", "De Munt 4DX", "De Munt Dolby", "De Munt Relax", "De Munt Dolby Cinema"]

    canonical_names = {KNOWN_VENUE_LOCATIONS[name].canonical_name for name in group}

    assert canonical_names == {"De Munt"}


def test_a_single_name_group_is_its_own_canonical_name() -> None:
    # "Eye" - genuinely a one-name group, unlike "Tuschinski" below,
    # which gained a second alias (movie-planner#227).
    assert KNOWN_VENUE_LOCATIONS["Eye"].canonical_name == "Eye"


def test_canonical_name_is_the_first_name_listed_in_its_group() -> None:
    # "City"/"Pathé City" - "City" is listed first, so it's canonical.
    assert KNOWN_VENUE_LOCATIONS["City"].canonical_name == "City"
    assert KNOWN_VENUE_LOCATIONS["Pathé City"].canonical_name == "City"


def test_pathe_tuschinski_resolves_to_the_tuschinski_group() -> None:
    # movie-planner#227: needed once pathe.py stops leaving the city
    # baked into this template's cinema field - "Pathé Tuschinski" (no
    # city) needs to itself already be a known alias, or the fix just
    # trades one unresolved duplicate for another.
    assert KNOWN_VENUE_LOCATIONS["Pathé Tuschinski"].canonical_name == "Tuschinski"


def test_pathe_arena_no_accent_resolves_to_the_arena_group() -> None:
    assert KNOWN_VENUE_LOCATIONS["Pathe Arena"].canonical_name == "Arena"


def test_pathe_de_munt_lowercase_de_resolves_to_the_de_munt_group() -> None:
    assert KNOWN_VENUE_LOCATIONS["Pathe de Munt"].canonical_name == "De Munt"


def test_de_munt_dolby_atmos_resolves_to_the_de_munt_group() -> None:
    assert KNOWN_VENUE_LOCATIONS["De Munt Dolby Atmos"].canonical_name == "De Munt"


def test_legacy_city_suffixed_cinema_strings_resolve_to_their_canonical_venue() -> None:
    # The ticketbevestiging/reservering templates baked ", Amsterdam"
    # into cinema before #227's parser fix - real rows already sitting
    # in Ryan's database under these exact strings (a one-time-only
    # fix; no future parse will ever produce them again, since the
    # parser itself is already fixed).
    assert KNOWN_VENUE_LOCATIONS["Pathé Tuschinski, Amsterdam"].canonical_name == "Tuschinski"
    assert KNOWN_VENUE_LOCATIONS["Pathé De Munt, Amsterdam"].canonical_name == "De Munt"
    assert KNOWN_VENUE_LOCATIONS["Pathé Arena, Amsterdam"].canonical_name == "Arena"
    assert KNOWN_VENUE_LOCATIONS["Pathé City, Amsterdam"].canonical_name == "City"


def test_every_known_venue_location_has_a_canonical_name_that_is_itself_a_key() -> None:
    # Every alias's canonical_name must itself be a real, resolvable key
    # in the table - otherwise resolving an alias to its canonical name
    # and then looking that up again would silently fail.
    for name, location in KNOWN_VENUE_LOCATIONS.items():
        assert location.canonical_name in KNOWN_VENUE_LOCATIONS, (
            f"{name!r}'s canonical_name {location.canonical_name!r} isn't itself a known name"
        )
