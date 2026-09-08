from movie_planner.venue_locations import KNOWN_VENUE_LOCATIONS, VenueLocation

# --- street_address/postal_code: issue #283 ---


def test_venue_location_street_address_and_postal_code_default_to_none() -> None:
    location = VenueLocation(chain=None, city="Amsterdam", country="Netherlands")

    assert location.street_address is None
    assert location.postal_code is None


def test_tuschinski_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Tuschinski"]
    assert location.street_address == "Reguliersbreestraat 26-34"
    assert location.postal_code == "1017 CN"


def test_de_munt_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["De Munt"]
    assert location.street_address == "Vijzelstraat 15"
    assert location.postal_code == "1017 HD"


def test_city_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["City"]
    assert location.street_address == "Kleine-Gartmanplantsoen 15-19"
    assert location.postal_code == "1017 RP"


def test_arena_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Arena"]
    assert location.street_address == "Johan Cruijff Boulevard 600"
    assert location.postal_code == "1101 DS"


def test_amsterdam_noord_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Amsterdam Noord"]
    assert location.street_address == "Buikslotermeerplein 2003"
    assert location.postal_code == "1025 XL"


def test_gsc_gurney_plaza_has_a_verified_unit_address_but_no_postal_code() -> None:
    # GSC's own official page names the unit but never lists a postal
    # code (unlike every Dutch venue above) - left unset rather than
    # guessed, same "omit, never guess" rule as everything else here.
    location = KNOWN_VENUE_LOCATIONS["Gsc Gurney Plaza Penang"]
    assert location.street_address == "Lot 170-07-01, Plaza Gurney, Persiaran Gurney"
    assert location.postal_code is None


def test_eye_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Eye"]
    assert location.street_address == "IJpromenade 1"
    assert location.postal_code == "1031 KT"


def test_cinecenter_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Cinecenter"]
    assert location.street_address == "Lijnbaansgracht 236"
    assert location.postal_code == "1017 PH"


def test_filmhallen_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Filmhallen"]
    assert location.street_address == "Hannie Dankbaarpassage 12"
    assert location.postal_code == "1053 RT"


def test_rialto_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Rialto"]
    assert location.street_address == "Ceintuurbaan 338"
    assert location.postal_code == "1072 GN"


def test_rialto_vu_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Rialto VU"]
    assert location.street_address == "De Boelelaan 1111"
    assert location.postal_code == "1081 HV"


def test_studio_k_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Studio/K"]
    assert location.street_address == "Timorplein 62"
    assert location.postal_code == "1094 CC"


def test_lab111_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["Lab111"]
    assert location.street_address == "Arie Biemondstraat 111"
    assert location.postal_code == "1054 PD"


def test_de_balie_has_a_verified_street_address() -> None:
    location = KNOWN_VENUE_LOCATIONS["De Balie"]
    assert location.street_address == "Kleine-Gartmanplantsoen 10"
    assert location.postal_code == "1017 RR"


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
