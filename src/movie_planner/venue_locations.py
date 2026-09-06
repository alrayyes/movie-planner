"""Hardcoded chain/city/country/coordinate data for venues already
logged - see issue #111 (chain/city/country) and #170 (coordinates).
Not geocoded dynamically: a venue name not listed here gets no
location at all, never a guess. Chain and location confirmed by
research (Pathé's own cinema listings, GSC's), not assumed;
coordinates confirmed against a real geocoder (OpenStreetMap's
Nominatim), not estimated from memory.
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
) -> None:
    # The first name in the group is the canonical one - every other
    # name here is a screen/format-suffixed alias of the same real
    # venue (issue #196).
    location = VenueLocation(
        chain=chain,
        city=city,
        country=country,
        coordinates=coordinates,
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
# ", Amsterdam" off it.
_add(["Tuschinski", "Pathé Tuschinski"], **_PATHE, coordinates=(52.3665062, 4.8947073))
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
    ],
    **_PATHE,
    coordinates=(52.3664519, 4.8934706),
)
_add(["City", "Pathé City"], **_PATHE, coordinates=(52.3633802, 4.8838439))
_add(
    # "Pathe Arena" (no accent) - the mobiel template's own real,
    # verbatim capture (movie-planner#200/#227).
    ["Arena", "Pathé Arena", "Pathe Arena"],
    **_PATHE,
    coordinates=(52.3123633, 4.9457053),
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
)

# GSC (Golden Screen Cinemas) - Malaysia's largest chain. Coordinates
# are the Gurney Plaza mall's - GSC's own cinema unit within it has no
# separate published address.
_add(
    ["Gsc Gurney Plaza Penang"],
    chain="GSC",
    city="Penang",
    country="Malaysia",
    coordinates=(5.4372970, 100.3094027),
)

# Independent, single-site Amsterdam cinemas - no chain.
_add(
    ["Eye"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3843350, 4.9008120),
)
_add(
    ["Cinecenter"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3650011, 4.8816806),
)
_add(
    ["Filmhallen", "De FilmHallen"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3668213, 4.8685964),
)
_add(
    ["Rialto"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3529953, 4.8939431),
)
_add(
    ["Rialto VU"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3347864, 4.8636823),
)
_add(
    ["Studio/K"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3651443, 4.9359029),
)
_add(
    ["Lab111"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3636724, 4.8672486),
)
_add(
    ["De Balie"],
    chain=None,
    city="Amsterdam",
    country="Netherlands",
    coordinates=(52.3630433, 4.8828596),
)
