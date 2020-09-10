"""Functions from the original pygeon API.

The plan is to eventually deprecate and remove most of these.
"""

import logging
import re

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import pygeons.api
import pygeons.db

DEFAULT_LANG = "en"
"""The default language for queries."""

CITY = 'CITY'
ADM1 = 'ADM1'
ADM2 = 'ADM2'
ADMD = 'ADMD'

SCRUB_OK = "O"
"""Indicates that the input field matched completely."""
SCRUB_MOD = "M"
"""Indicates that the input field was modified to achieve a match."""
SCRUB_DERIVED = "D"
"""Indicates that the input field was missing and was derived to achieve
a match."""

_LOGGER = logging.getLogger(__name__)


def country_to_iso(name: str) -> str:
    """Return the ISO 2-letter code for the specified country.

    >>> country_to_iso('russia')
    'RU'
    """
    return pygeons.api.Country(name).iso  # type: ignore


def country_info(name: str) -> Dict[str, Any]:
    """Return the info for the country with the specified name.

    >>> country_info('russia')['capital']
    'Moscow'
    """
    return pygeons.api.Country(name).data._asdict()


def norm_country(country_name: str, lang: str = DEFAULT_LANG) -> str:
    """Return the canonical name for a country.

    >>> norm_country('JP')
    'Japan'
    >>> norm_country('日本', lang='ja')
    '日本'
    """
    return pygeons.api.Country(country_name).normalize(language=lang)


def norm(collection: str, country_code: str, name: str, lang: str = DEFAULT_LANG) -> str:
    """Normalize the name with respect to a collection and country code.

    >>> norm(CITY, 'RU', 'leningrad')
    'Saint Petersburg'
    >>> norm(CITY, 'RU', 'peterburg')
    'Saint Petersburg'
    >>> norm(CITY, 'RU', 'peterburg', lang='ru')
    'Санкт-Петербург'
    """
    country = pygeons.api.Country(country_code)
    if collection == CITY:
        return country.cities[name].normalize(language=lang)
    elif collection == ADM1:
        return country.admin1[name].normalize(language=lang)
    elif collection == ADM2:
        return country.admin2[name].normalize(language=lang)
    else:
        raise NotImplementedError


def norm_ppc(country_code: str, place_name: str) -> str:
    """Return the canonical name for a place with a postcode.

    :param str country_code: The ISO2 code of the country for which to search.
    :param str place_name: The place name to normalize.
    :returns: The canonical place name.
    :rtype: str

    In the new API, use::

        Country(country_code).Postcode(place_name).normalize()

    """
    raise NotImplementedError


def is_ppc(country_code: str, place_name: str) -> None:
    """Is the place_name in the postcode database?

    >>> is_ppc('AU', 'randwick')
    True
    >>> is_ppc('NZ', 'randwick')
    False
    """
    try:
        matches = pygeons.db.TRIE[place_name.lower()]
    except KeyError:
        pass
    else:
        for m in matches:
            if m[0] == b'Z' and m[1] == country_code.encode(pygeons.db.ENCODING):
                return True

    return False


def is_city(country_code: str, city_name: str, lang: str = DEFAULT_LANG) -> bool:
    """Is city_name in the city database?

    >>> is_city('JP', 'Sapporo')
    True
    >>> is_city('JP', '札幌')
    True
    """
    return city_name in pygeons.api.Country(country_code)


def is_admin1(country_code: str, admin1_name: str, lang: str = DEFAULT_LANG) -> bool:
    """Is admin1_name in the admin1 database?

    >>> is_admin1('RU', 'leningrad oblast')
    True
    >>> is_admin1('RU', 'ленинградская область')
    True
    """
    return admin1_name in pygeons.api.Country(country_code).admin1


def is_admin2(country_code: str, admin2_name: str, lang: str = DEFAULT_LANG) -> bool:
    """Is admin2_name in the admin2 database?

    >>> is_admin2('GB', 'shropshire')
    True
    """
    return admin2_name in pygeons.api.Country(country_code).admin2


def is_country(country_name: str, lang: str = DEFAULT_LANG) -> bool:
    """Returns True if the specified country name is in the database.

    >>> is_country('russia')
    True
    >>> is_country('russian federation')
    True
    >>> is_country('ru')
    True
    >>> is_country('россия')
    True
    >>> is_country('российская федерация')
    True
    """
    try:
        pygeons.api.Country(country_name)
    except KeyError:
        return False
    else:
        return True


def expand(collection: Any, country_code: str, abbr: str) -> str:
    """Expand the specified abbreviation.

    >>> expand(ADM1, 'AU', 'nsw')
    'State of New South Wales'
    >>> expand(ADM1, 'AU', 'vic')
    'State of Victoria'
    >>> expand(ADM1, 'AU', 'qld')
    'State of Queensland'
    """
    return pygeons.api.expand(abbr, country_code=country_code)[0].name


def expand_country(abbr: str) -> str:
    """Expand the specified country name abbreviation.

    >>> expand_country('RU')
    'Russian Federation'
    >>> expand_country('RUS')
    'Russian Federation'
    """
    return pygeons.api.Country(abbr).normalize()


def is_state(state: str, country: str) -> bool:
    """Return True if the state exists within the specified country.
    >>> is_state('new south wales', 'australia')
    True
    """
    return state in pygeons.api.Country(country).states


def csc_find(
    city: str,
    state: Optional[str] = None,
    country: Optional[str] = None,
    dedup=True,
) -> List[pygeons.db.Geoname]:
    """Return a list of all cities that satisfy the (city, state, country)
    combination.

    >>> [x.country_code for x in csc_find('sydney')]
    ['AU', 'CA', 'US', 'US', 'ZA', 'VU', 'US', 'US', 'CA']
    """
    clean_city, clean_state, iso2, _ = _csc_clean_params(city, state, country)
    cities = pygeons.api.csc_list(clean_city, clean_state, iso2)
    #
    # FIXME: deduplication
    #
    return cities


def _scrub(s):
    """Strip punctuation, make everything lowercase."""
    if not s:
        return s
    return "".join([x for x in s.lower().strip() if x not in ".,"])


def _clean_nonalpha(stringy):
    """Replace leading and trailing non-alphabetical characters."""
    if not stringy:
        return stringy
    isalpha = lambda x: x.isalpha() or x in "()"
    try:
        start = min([i for (i, l) in enumerate(stringy) if isalpha(l)])
    except ValueError:
        return ""
    end = max([i for (i, l) in enumerate(stringy) if isalpha(l)]) + 1
    return stringy[start:end]


def _csc_clean_params(city, state, country):
    """Clean csc_scrub parameters deterministically."""
    city_alt = []
    city = _clean_nonalpha(city)
    state = _clean_nonalpha(state)
    country = _clean_nonalpha(country)

    if country:
        try:
            country = country_to_iso(country)
        except ValueError:
            _LOGGER.warning("invalid ISO2 country code: %r" % country)
            country = None

    #
    # Map UK => GB
    # TODO: what if we're searching in the Ukraine?
    #
    if country == "UK":
        _LOGGER.info("interpreting UK country code as Great Britain")
        country = "GB"

    #
    # Map PR/US to ''/PR
    #
    if state == "PR" and country == "US":
        state, country = "", "PR"

    if not city:
        return city, _scrub(state), country, city_alt

    match = re.search(r"\s+\(([^)]+)\)$", city, flags=re.UNICODE)
    if match and _clean_nonalpha(match.group(1)):
        city_alt.append(_clean_nonalpha(match.group(1)))

    #
    # Clean up (D&B) prefixes that shouldn't be space-separated
    #
    city = re.sub(r"(Mc)\s", r"\1", city)
    city = re.sub(r"(O)\s", r"\1'", city)

    #
    # Try stripping some standard suffixes/prefixes to give additional
    # alternates to try e.g. Coal City, Oak Park Township, etc.
    # Perhaps we should handle these in the data rather than here, but there's
    # an ambiguity problem - if there's an Oak Park *and* an Oak Park Township
    # in a state, we probably shouldn't add any variants at all.
    #
    match = re.search(r"(\s+(City|Township|Twp|Village))$", city, flags=re.I)
    if match:
        city_alt.append(re.sub(match.group(1), "", city))
    if match and match.group(1).lower().strip() in ["township", "twp"]:
        city_alt.append(re.sub(match.group(1), " City", city))
    elif match:
        city_alt.append(re.sub(match.group(1), " Township", city))

    city_alt = [_scrub(c) for c in city_alt]

    return _scrub(city), _scrub(state), country, city_alt


def csc_scrub(city: str, state: Optional[str], country: Optional[str]) -> Any:
    """Check the combination of (city, state, country).

    Returning a result object if a unique match can be found (with some level of confidence).
    If either state and country are incorrect, attempts to correct them.

    >>> result = csc_scrub('moscow', None, None)
    >>> city = result.pop('result')
    >>> result
    {'score': 0.3, 'st_status': 'D', 'cc_status': 'D', 'count': 33}
    >>> city.name, city.country_code
    ('Moscow', 'RU')

    :param city: The name of the city.
    :param state: The name of the state.  May be None.
    :param country: The name of the country.  May be None.

    The scrub result includes the best match, as well as some auxiliary information:

        - score: The confidence score.  Higher is better.
        - st_status: How the state for the scrubbed result was attained.
        - cc_status: How the country for the scrubbed result was attained.
        - count: The total number of results that matched the query.
    """

    def mkretval(results, score, st_status, cc_status):
        return {"result": results[0], "score": score, "st_status": st_status,
                "cc_status": cc_status, "count": len(results)}

    had_state = bool(state)
    had_country = bool(country)

    _LOGGER.debug("city: %r state: %r country: %r", city, state, country)
    city, state, country, city_alt = _csc_clean_params(city, state, country)
    _LOGGER.debug("clean city: %r (%r) state: %r country: %r", city, city_alt, state, country)

    if state and country and not is_state(state, country):
        _LOGGER.info("unable to find state %r in country %r, ignoring", state, country)
        state = None

    have_csc = city and state and country
    res = csc_find(city, state, country) if have_csc else None
    if res and len(res) == 1:
        return mkretval(res, 0.9, SCRUB_OK, SCRUB_OK)
    elif res:
        return mkretval(res, 0.8, SCRUB_OK, SCRUB_OK)

    #
    # If we have state and cc, search for them, accepting iff unique.
    #
    if city_alt and state and country:
        _LOGGER.debug("trying alternative names: %r", city_alt)
        for alt in city_alt:
            res = csc_find(alt, state, country)
            if len(res) == 1:
                return mkretval(res, 0.85, SCRUB_OK, SCRUB_OK)

    #
    # Try omitting state.
    #
    res = csc_find(city, None, country) if city and country else None
    if res and len(res) == 1:
        st_status = SCRUB_MOD if had_state else SCRUB_DERIVED
        return mkretval(res, 0.8, st_status, SCRUB_OK)
    elif res and state:
        _LOGGER.info("multiple matches (%d) found for city %r in country %r, \
but none in state %r", len(res), city, country, state)
        return mkretval(res, 0.4, SCRUB_MOD, SCRUB_OK)
    elif res:
        _LOGGER.info("multiple matches (%d) found for (%r, None, %r), \
no state given", len(res), city, country)
        return mkretval(res, 0.5, SCRUB_DERIVED, SCRUB_OK)

    #
    # Perhaps state is really a city?
    #
    res = csc_find(state, None, country) if state and country else None
    if res and len(res) == 1:
        return mkretval(res, 0.7, SCRUB_DERIVED, SCRUB_OK)

    #
    # Either no country given, or city/state/cc match failed - perhaps country
    # is wrong?
    #
    res = csc_find(city, state, None) if city and state else None
    if res and len(res) == 1 and (country or had_country):
        return mkretval(res, 0.8, SCRUB_OK, SCRUB_MOD)
    elif res and len(res) == 1:
        return mkretval(res, 0.8, SCRUB_OK, SCRUB_DERIVED)
    elif res and country:
        _LOGGER.info("multiple matches (%d) found for city %r in state %r, \
but none in country %r", len(res), city, state, country)
        return mkretval(res, 0.4, SCRUB_OK, SCRUB_MOD)
    elif res:
        _LOGGER.info("multiple matches (%d) found for city %r in state %r, \
no country given", len(res), city, state)
        return mkretval(res, 0.5, SCRUB_OK, SCRUB_DERIVED)

    #
    # Perhaps city itself is unique?
    #
    _LOGGER.debug("city: %r state: %r country: %r", city, state, country)
    res = csc_find(city, None, None) if city else None
    if not res:
        return None

    score = 0.6 if len(res) == 1 else 0.3
    st_status = SCRUB_MOD if had_state else SCRUB_DERIVED
    cc_status = SCRUB_MOD if had_country else SCRUB_DERIVED
    return mkretval(res, score, st_status, cc_status)


find_country = country_info
