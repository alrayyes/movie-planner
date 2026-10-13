"""Hardcoded chain/city/country/coordinate data for venues already
logged - see issue #111 (chain/city/country), #170 (coordinates), and
#283 (street address/postal code). Not geocoded dynamically: a venue
name not listed here gets no location at all, never a guess. Chain and
location confirmed by research (Pathé's own cinema listings, GSC's),
not assumed; coordinates confirmed against a real geocoder
(OpenStreetMap's Nominatim), not estimated from memory. Street
addresses/postal codes confirmed against each venue's own official
site where one exists, cross-checked against a second independent
source (a review/listing site, a local postcode lookup) and against the
venue's own already-verified coordinates - never guessed, and left
unset for GSC Gurney Plaza's postal code, which no source confirms.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueLocation:
    chain: str | None
    city: str
    country: str
    # (latitude, longitude) - only ever set from a verified source
    # (see module docstring), never guessed. None when a venue's
    # coordinates haven't been looked up yet, even if its chain/city/
    # country are already known.
    coordinates: tuple[float, float] | None = None
    # Street address/postal code (issue #283) - same "verified against
    # a real source, never guessed" rule as every other field here,
    # independent of one another: a venue can have one confirmed
    # without the other. Used to extend LOCATION to a full geocodable
    # address and to set X-STREET-ADDRESS/X-POSTAL-CODE, only when
    # each is actually known.
    street_address: str | None = None
    postal_code: str | None = None
    # The one name every alias in a group (see _add's `names` below)
    # should collapse to - always itself a key in this table, so
    # resolving an alias to its canonical name and looking that up
    # again always finds something (issue #196). Set by _add, never
    # passed directly.
    canonical_name: str = ""


KNOWN_VENUE_LOCATIONS: dict[str, VenueLocation] = {}


def _add(
    names: list[str],
    *,
    chain: str | None,
    city: str,
    country: str,
    coordinates: tuple[float, float] | None = None,
    street_address: str | None = None,
    postal_code: str | None = None,
) -> None:
    # The first name in the group is the canonical one - every other
    # name here is a screen/format-suffixed alias of the same real
    # venue (issue #196).
    location = VenueLocation(
        chain=chain,
        city=city,
        country=country,
        coordinates=coordinates,
        street_address=street_address,
        postal_code=postal_code,
        canonical_name=names[0],
    )
    for name in names:
        KNOWN_VENUE_LOCATIONS[name] = location


# Pathé - confirmed operator of all five Amsterdam venues below (Pathé
# acquired the former MGM Netherlands chain, including Tuschinski, in
# 1995; the others are long-standing Pathé-branded multiplexes).
# Several logged names bake a screen/format (4DX, Dolby, Atmos, Relax)
# into the venue string rather than naming a separate physical venue -
# these are grouped under the same real-world location.
_PATHE = {"chain": "Pathé", "city": "Amsterdam", "country": "Netherlands"}
# "Pathé Tuschinski" - the ticketbevestiging/reservering templates' own
# cinema capture before movie-planner#227's fix stripped the trailing
# ", Amsterdam" off it. "Pathé Tuschinski, Amsterdam" (with the city
# still attached) is the *pre-#227* shape of that same capture - a
# one-time-only alias for rows already sitting in a database from
# before the parser fix landed; no future parse will ever produce this
# exact string again, since the parser itself is already fixed.
_add(
    ["Tuschinski", "Pathé Tuschinski", "Pathé Tuschinski, Amsterdam"],
    **_PATHE,
    coordinates=(52.3665062, 4.8947073),
    street_address="Reguliersbreestraat 26-34",
    postal_code="1017 CN",
)
_add(
    [
        "De Munt",
        "De Munt 4DX",
        "De Munt Dolby",
        "De Munt Relax",
        "De Munt Dolby Cinema",
        "De Munt Dolby Atmos",
        "Pathé De Munt",
        # No accent, lowercase "de" (movie-planner#227) - a real,
        # verbatim capture from the historical gmail archive, source
        # template not identified.
        "Pathe de Munt",
        # Pre-#227 shape, same reasoning as Tuschinski above.
        "Pathé De Munt, Amsterdam",
    ],
    **_PATHE,
    coordinates=(52.3664519, 4.8934706),
    street_address="Vijzelstraat 15",
    postal_code="1017 HD",
)
_add(
    ["City", "Pathé City", "Pathé City, Amsterdam"],
    **_PATHE,
    coordinates=(52.3633802, 4.8838439),
    street_address="Kleine-Gartmanplantsoen 15-19",
    postal_code="1017 RP",
)
_add(
    # "Pathe Arena" (no accent) - the mobiel template's own real,
    # verbatim capture (movie-planner#200/#227).
    ["Arena", "Pathé Arena", "Pathe Arena", "Pathé Arena, Amsterdam"],
    **_PATHE,
    coordinates=(52.3123633, 4.9457053),
    # "Johan Cruijff Boulevard" - the street was renamed from "ArenA
    # Boulevard" to this; the current name is what actually geocodes.
    street_address="Johan Cruijff Boulevard 600",
    postal_code="1101 DS",
)
_add(
    [
        "Amsterdam Noord",
        "Amsterdam Noord Dolby Cinema",
        "Amsterdam Noord Atmos",
        "Amsterdam Noord Dolby Atmos",
        "Pathe Noord",
        "Pathé Noord",
        "Pathé Amsterdam Noord",
    ],
    **_PATHE,
    coordinates=(52.4008640, 4.9344210),
    street_address="Buikslotermeerplein 2003",
    postal_code="1025 XL",
)

# GSC (Golden Screen Cinemas) - Malaysia's largest chain. Coordinates
# are the Gurney Plaza mall's. GSC's own official page names the unit
# address but never publishes a postal code for it - left unset rather
# than guessed.
_add(
    ["Gsc Gurney Plaza Penang"],
    chain="GSC",
    city="Penang",
    country="Malaysia",
    coordinates=(5.4372970, 100.3094027),
    street_address="Lot 170-07-01, Plaza Gurney, Persiaran Gurney",
)

# Independent, single-site Amsterdam cinemas - no chain.
_add(
    ["Eye"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3843350, 4.9008120),
    street_address="IJpromenade 1",
    postal_code="1031 KT",
)
_add(
    ["Cinecenter"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3650011, 4.8816806),
    street_address="Lijnbaansgracht 236",
    postal_code="1017 PH",
)
_add(
    ["Filmhallen", "De FilmHallen"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3668213, 4.8685964),
    # Not "Bellamyplein" (the wider De Hallen complex's own square) -
    # the cinema's actual entrance address is this pedestrian passage.
    street_address="Hannie Dankbaarpassage 12",
    postal_code="1053 RT",
)
_add(
    ["Rialto"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3529953, 4.8939431),
    street_address="Ceintuurbaan 338",
    postal_code="1072 GN",
)
_add(
    ["Rialto VU"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3347864, 4.8636823),
    street_address="De Boelelaan 1111",
    postal_code="1081 HV",
)
_add(
    ["Studio/K"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3651443, 4.9359029),
    street_address="Timorplein 62",
    postal_code="1094 CC",
)
_add(
    ["Lab111"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3636724, 4.8672486),
    street_address="Arie Biemondstraat 111",
    postal_code="1054 PD",
)
_add(
    ["De Balie"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3630433, 4.8828596),
    street_address="Kleine-Gartmanplantsoen 10",
    postal_code="1017 RR",
)
