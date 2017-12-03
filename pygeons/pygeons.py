#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
"""Queries the GeoNames database in MongoDB."""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import argparse
import warnings
import logging
import os.path as P
import datetime
import re
import os
import math
import itertools
import pkg_resources
import sys

import yaml
import pymongo
import pymongo.errors

#
# http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
#
__version__ = pkg_resources.require("Pygeons")[0].version

LOGGER = logging.getLogger(__name__)
#
# Prevent stderr message about "no handlers found".
# It is possible that somebody is using Pygeon without logging.
# https://docs.python.org/2/howto/logging.html#configuring-logging-for-a-library
#
LOGGER.addHandler(logging.NullHandler())

DEFAULT_HOST = "localhost"
"""The default hostname of the MongoDB server."""

DEFAULT_PORT = 27017
"""The default port that the MongoDB server listens on."""

DEFAULT_DBNAME = "geonames"
"""The default name of the database to read from."""

DEFAULT_AUTH_DBNAME = "admin"
"""The default name of the database to verify user information against."""

DEFAULT_USERNAME = None
"""The default username.  If None, will not authenticate."""

DEFAULT_PASSWORD = None
"""The default password.  If None, will not authenticate."""

ADM1 = "admin1"
"""Constant for the admin1 collection."""

ADM2 = "admin2"
"""Constant for the admin2 collection."""

ADMD = "admind"
"""Constant for the admind collection."""

CITY = "cities"
"""Constant for the cities collection."""

SCRUB_OK = "O"
"""Indicates that the input field matched completely."""
SCRUB_MOD = "M"
"""Indicates that the input field was modified to achieve a match."""
SCRUB_DERIVED = "D"
"""Indicates that the input field was missing and was derived to achieve
a match."""

CLIENT = None
"""The PyMongo client for connecting to the database."""

DB = None
"""The database object."""

EXPECTED_VERSION = datetime.datetime(2016, 11, 4, 13, 3, 8)
"""The expected database version.  If this is newer than the actual version
at runtime, a warning will be printed to standard error at runtime."""

DEFAULT_LANG = "en"
"""The default language for queries."""


class Config(object):
    """Our writable namedtuple."""

    def __init__(
            self, host=DEFAULT_HOST, port=DEFAULT_PORT, dbname=DEFAULT_DBNAME,
            auth_dbname=DEFAULT_AUTH_DBNAME, username=DEFAULT_USERNAME,
            password=DEFAULT_PASSWORD):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.auth_dbname = auth_dbname
        self.username = username
        self.password = password

    def __str__(self):
        return "Config(%r, %r, %r, %r, %r, \"*****\")" % (
            self.host, self.port, self.dbname, self.auth_dbname, self.username
        )


def _hide_password(conf):
    conf = dict(conf)
    if 'password' in conf:
        conf['password'] = '*' * len(conf['password'])
    return conf


def _load_configuration_helper(fin):
    conf = yaml.load(fin)
    if not conf:
        conf = {}
    LOGGER.info("conf: %r", _hide_password(conf))
    host = conf.get("host", DEFAULT_HOST)
    port = conf.get("port", DEFAULT_PORT)
    dbname = conf.get("dbname", DEFAULT_DBNAME)
    auth_dbname = conf.get("auth_dbname", DEFAULT_AUTH_DBNAME)
    username = conf.get("username", DEFAULT_USERNAME)
    password = conf.get("password", DEFAULT_PASSWORD)
    return Config(host, port, dbname, auth_dbname, username, password)


def _load_configuration():
    """Reload the configuration from $HOME/pygeons.yaml, if it exists."""
    default_path = P.expanduser("~/pygeons.yaml")
    config_path = P.abspath(os.environ.get("PYGEON_CONFIG_PATH", default_path))
    if P.isfile(config_path):
        LOGGER.info("loading configuration from %r", config_path)
        with open(config_path) as fin:
            return _load_configuration_helper(fin)
    else:
        LOGGER.warn("%r does not exist, using default config", config_path)
    return Config()

CONFIG = _load_configuration()


class NotFound(Exception):
    """Raised when we're unable to find the required place in the DB."""
    pass


def reconnect(connect=True):
    """Reconnect to the database.  If using pygeon in a multi-threaded or
    multi-process application, call this function immediately after you fork.

    See
    http://api.mongodb.org/python/current/faq.html#using-pymongo-with-multiprocessing
    for details."""
    global CLIENT
    global DB
    CLIENT, DB = _reconnect_helper(connect)


def _reconnect_helper(connect=True):
    """Returns a client and database handle."""
    client = pymongo.MongoClient(CONFIG.host, CONFIG.port, connect=connect)
    db = client[CONFIG.dbname]
    if CONFIG.username and CONFIG.password and CONFIG.auth_dbname:
        db.authenticate(CONFIG.username, CONFIG.password,
                        source=CONFIG.auth_dbname)
    return client, db


def _test_connection():
    """If we're not already connected, then connect. Otherwise, do nothing."""
    if not (CLIENT and DB):
        reconnect()

    #
    # Everything that touches the DB should first call _test_connection to
    # ensure a DB connection is available.
    #


def get_version():
    """Return the version of the database to use."""
    _test_connection()
    ver = DB.util.find_one({"name": "version"})
    if ver:
        return datetime.datetime.strptime(ver["value"], "%Y.%m.%d-%H.%M.%S")
    return None


def check_version():
    """Print a warning if the current version is not the expected version."""
    try:
        version = get_version()
    except pymongo.errors.OperationFailure as opf:
        LOGGER.error(opf)
        version = None
    if version is None or version < EXPECTED_VERSION:
        warnings.warn("unexpected version: %s" % repr(version), RuntimeWarning)


def country_to_iso(name):
    """Return the ISO 2-letter code for the specified country.

    :param str name: The name of the country.
    :returns: The ISO2 code.
    :rtype: str
    """
    return country_info(name)["iso"]


def country_info(name):
    """Return the info for the country with the specified name.

    >>> sorted(pygeons.country_info('russia').keys())
    ['_id', 'abbr', 'capital', 'fips', 'iso', 'iso3', 'languages', 'name', 'names', 'names_lang', 'population', 'tld']

    :param str name: The name of the country.
    :returns: The country information.
    :rtype: dict
    """
    if not name:
        raise ValueError("country name may not be empty")
    _test_connection()
    country = DB.countries.find_one({"names": _scrub(name)})
    if country:
        return country

    country = DB.countries.find_one({"abbr": _scrub(name)})
    if country:
        return country

    raise NotFound("no such country: %r" % name)


def norm(collection, country_code, name, lang=DEFAULT_LANG):
    """Normalize the name with respect to a collection and country code.

    >>> pygeons.norm(pygeons.ADM1, 'RU', 'leningrad')
    'Leningradskaya Oblast’'
    >>> pygeons.norm(pygeons.CITY, 'RU', 'peterburg')
    'Saint Petersburg'

    :param str collection: The collection to look within to normalize.
    :param str country_code: The country's ISO2 code.
    :param str name: The name to normalize.
    :param str lang: The language that the name is in.
    :returns: The normalized name.
    :rtype: str
    """
    LOGGER.debug("norm: %r", locals())
    _test_connection()

    if collection not in [ADM1, ADM2, ADMD, CITY]:
        raise ValueError("invalid collection")

    name = _scrub(name)
    query = {"countryCode": country_code, "names_lang.%s" % lang: name}
    LOGGER.debug("norm_admin: collection: %r query: %r", collection, query)
    admin = DB[collection].find_one(query)
    if not admin:
        if lang == DEFAULT_LANG:
            try:
                return expand(collection, country_code, name)
            except NotFound:
                raise NotFound("unknown %s %s: %s" % (collection, lang, name))
        return norm(collection, country_code, name)
    return admin["name"]


def norm_country(country_name, lang=DEFAULT_LANG):
    """Return the canonical name for a country.

    >>> pygeons.norm_country('JP')
    'Japan'
    >>> pygeons.norm_country('日本', lang='ja')
    'Japan'

    :param str country_name: The name of the country to normalize.
    :param str lang: The language that the country name is in.
    :returns: The canonical country name.
    :rtype: str"""
    meth_name = "norm_country"
    _test_connection()
    country_name = _scrub(country_name)
    LOGGER.debug("%s: country_name: %s lang: %s",
                 meth_name, repr(country_name), repr(lang))
    query = {"names_lang.%s" % lang: country_name}
    LOGGER.debug("%s: query: %s", meth_name, query)
    country = DB.countries.find_one(query)
    if country:
        return country["name"]

    if lang == DEFAULT_LANG:
        try:
            return expand_country(country_name)
        except NotFound:
            raise NotFound("unknown %s country: %s" % (lang, country_name))
    return norm_country(country_name)


def norm_ppc(country_code, place_name):
    """Return the canonical name for a place with a postcode.

    :param str country_code: The ISO2 code of the country for which to search.
    :param str place_name: The place name to normalize.
    :returns: The canonical place name.
    :rtype: str
    """
    _test_connection()
    #
    # TODO: make placeNames lowercase on the DB side for these lookups to
    # be more reliable
    #
    query = {"countryCode": country_code, "placeName": place_name.title()}
    place = DB.postcodes.find_one(query)
    if place:
        return place["placeName"]
    raise NotFound("unknown place: %s" % repr(place_name))


def is_ppc(country_code, place_name):
    """Is the place_name in the postcode database?

    :param str country_code: The ISO2 code of the country for which to search.
    :param str place_name: The place name to look for.
    :rtype: boolean
    """
    try:
        norm_ppc(country_code, place_name)
        return True
    except NotFound:
        return False


def is_city(country_code, city_name, lang=DEFAULT_LANG):
    """Is city_name in the city database?

    >>> pygeons.is_city('JP', 'Sapporo')
    True
    >>> pygeons.is_city('JP', '札幌')
    False
    >>> pygeons.is_city('JP', '札幌', lang='ja')
    True

    :param str country_code: The ISO2 code of the country for which to search.
    :param str city_name: The city name to look for.
    :param str lang: The language that the city name is in.
    :rtype: boolean
    """
    meth_name = "is_city"
    try:
        norm(CITY, country_code, city_name, lang)
        LOGGER.debug("%s: yes", meth_name)
        return True
    except NotFound:
        try:
            norm_ppc(country_code, city_name)
            LOGGER.debug("%s: yes (ppc)", meth_name)
            return True
        except NotFound:
            LOGGER.debug("%s: no", meth_name)
            return False


def is_admin1(country_code, admin1_name, lang=DEFAULT_LANG):
    """Is admin1_name in the admin1 database?

    >>> pygeons.is_admin1('RU', 'leningrad oblast')
    True
    >>> pygeons.is_admin1('RU', 'ленинградская область')
    False
    >>> pygeons.is_admin1('RU', 'ленинградская область', lang='ru')
    True

    :param str country_code: The ISO2 code of the country for which to search.
    :param str admin1_name: The admin1 name to look for.
    :param str lang: The language that the city name is in.
    :rtype: boolean
    """
    try:
        norm(ADM1, country_code, admin1_name, lang)
        return True
    except NotFound:
        return False


def is_admin2(country_code, admin2_name, lang=DEFAULT_LANG):
    """Is admin2name in the admin2 database?

    :param str country_code: The ISO2 code of the country for which to search.
    :param str admin1_name: The admin2 name to look for.
    :param str lang: The language that the city name is in.
    :rtype: boolean
    """
    try:
        norm(ADM2, country_code, admin2_name, lang)
        return True
    except NotFound:
        return False


def is_admind(country_code, name, lang=DEFAULT_LANG):
    """Is admin2name in the admin2 database?

    :param str country_code: The ISO2 code of the country for which to search.
    :param str admind_name: The admin2 name to look for.
    :param str lang: The language that the city name is in.
    :rtype: boolean
    """
    try:
        norm(ADMD, country_code, name, lang)
        return True
    except NotFound:
        return False


def is_country(country_name, lang=DEFAULT_LANG):
    """Returns True if the specified country name is in the database.

    >>> pygeons.is_country('russia')
    True
    >>> pygeons.is_country('russian federation')
    True
    >>> pygeons.is_country('ru')
    True
    >>> pygeons.is_country('россия', lang='ru')
    True
    >>> pygeons.is_country('российская федерация', lang='ru')
    True

    :param str country_name: The name of the country.
    :param str lang: The language that the country name is in.
    :rtype: boolean
    """
    try:
        norm_country(country_name, lang)
        return True
    except NotFound:
        return False


def expand(collection, country_code, abbr):
    """Expand the specified abbreviation.

    >>> pygeons.expand(pygeons.ADM1, 'AU', 'nsw')
    'State of New South Wales'
    >>> pygeons.expand(pygeons.ADM1, 'AU', 'vic')
    'State of Victoria'
    >>> pygeons.expand(pygeons.ADM1, 'AU', 'qld')
    'State of Queensland'

    :param str collection: The collection within which to look.
    :param str country_code: The code of the country within which to look.
    :param str abbr: The abbreviation to expand.
    :returns: The expanded abbreviation.
    :rtype: str
    """
    _test_connection()
    logging.debug("expand: %r", locals())
    if collection not in [ADM1, ADM2, ADMD, CITY]:
        raise ValueError("invalid collection: %r", collection)
    place = DB[collection].find_one({"abbr": _scrub(abbr),
                                     "countryCode": country_code})
    if place:
        return place["name"]
    raise NotFound("no such %r abbreviation: %r" % (collection, abbr))


def expand_country(abbr):
    """Expand the specified country name abbreviation.

    >>> pygeons.expand_country('RU')
    'Russia'
    >>> pygeons.expand_country('RUS')
    'Russia'

    :param str abbr: The abbreviation to expand.
    :returns: The canonical country name.
    :rtype: str
    """
    _test_connection()
    country = DB.countries.find_one({"abbr": _scrub(abbr)})
    if country:
        return country["name"]
    raise NotFound("no such country abbreviation: %s" % repr(abbr))


def find_country(country_name, lang=DEFAULT_LANG):
    _test_connection()
    country = DB.countries.find_one(
        {"names_lang.%s" % lang: _scrub(country_name)}
    )
    if country:
        return country
    elif lang == DEFAULT_LANG:
        country = DB.countries.find_one({"abbr": _scrub(country_name)})
        if country:
            return country
        raise NotFound("no such country: %r" % country_name)
    return find_country(country_name)


def _scrub(s):
    """Strip punctuation, make everything lowercase."""
    if not s:
        return s
    return "".join([x for x in s.lower().strip() if x not in ".,"])


def csc_exists(city_str, state_str, country_str):
    """Return True if the specified city, state, country combination exists
    in the GeoNames database.

    >>> pygeons.csc_exists('sydney', 'new south wales', 'AU')
    True

    :param str city_str: The city name.
    :param str state_str: The state name.
    :param str country_str: The country name.
    :rtype: boolean
    """
    LOGGER.debug("csc_exists: %r" % locals())
    _test_connection()

    iso = country_to_iso(country_str)
    city_str = _scrub(city_str)
    state_str = _scrub(state_str)

    if not (city_str and state_str):
        return False

    def find(subquery):
        query = {"names": city_str, "countryCode": iso}
        query.update(subquery)
        LOGGER.debug("query: %r", query)
        return DB.cities.find(query).count()

    adm1 = find({"admin1names": state_str})
    adm2 = find({"admin2names": state_str})
    if adm1:
        LOGGER.debug("csc_exists: adm1: %r", adm1)
        return True
    elif adm2:
        LOGGER.debug("csc_exists: adm2: %r", adm2)
        return True

    #
    # TODO: should we try harder and consider ADMD?
    #
    return False


def csc_find(city, state, country, dedup=True):
    """Return a list of all cities that satisfy the (city, state, country)
    combination.

    >>> [x['countryCode'] for x in pygeons.csc_find('sydney', None, None)]
    ['AU', 'CA', 'US', 'US', 'ZA', 'ZA', 'VU', 'US', 'US']

    :param str city: The name of the city.
    :param str state: The name of the state.  May be None.
    :param str country: The name of the country.  May be None.
    :param boolean dedup: Whether to deduplicate the found results.
    :returns: Cities that match the (city, state, country) query.
    :rtype: list of dict
    """
    LOGGER.debug("csc_find: %r", locals())
    _test_connection()
    clean_city, state, iso2, _ = _csc_clean_params(city, state, country)
    return _csc_find(clean_city, state, iso2, dedup=dedup)


def _csc_find(city, state, iso2, dedup=True):
    """Same as _csc_find, but doesn't perform parameter cleaning."""
    LOGGER.debug("_csc_find: %r", locals())
    if not city:
        raise ValueError("city may not be empty or null")

    cities = {}
    for state_col in ["admin1names", "admin2names"]:
        query = {"names": city}
        if state:
            query[state_col] = state
        if iso2:
            query["countryCode"] = iso2
        LOGGER.debug("_csc_find: query: %r", query)
        cities.update({c["_id"]: c for c in DB.cities.find(query)})

    #
    # Perhaps state is an admin1, but city is an admin2 or admind?
    # Only try this if we haven't found anything already, because otherwise
    # we can end up with ambiguous results.
    #
    if not cities:
        pairs = [("admin2", "admin2names"), ("admind", "names")]
        for collection, field in pairs:
            query = {field: city}
            if state:
                query["admin1names"] = state
            if iso2:
                query["countryCode"] = iso2
            cities.update({c["_id"]: c for c in DB[collection].find(query)})

    cities = sorted(cities.values(), key=lambda x: x.get("population", 0),
                    reverse=True)
    if cities and dedup:
        return _geonames_cities_dedup(cities)
    return cities


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
        except (ValueError, NotFound):
            LOGGER.warning("invalid ISO2 country code: %r" % country)
            country = None

    #
    # Map UK => GB
    # TODO: what if we're searching in the Ukraine?
    #
    if country == "UK":
        LOGGER.info("interpreting UK country code as Great Britain")
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


def _cluster_cities(cities, threshold=10):
    """Group cities closer than threshold km together into clusters."""

    are_close = {}
    for (a, b) in itertools.combinations(cities, 2):
        id1, lat1, lng1 = a["_id"], a["latitude"], a["longitude"]
        id2, lat2, lng2 = b["_id"], b["latitude"], b["longitude"]
        dist = _haversine_dist(lat1, lng1, lat2, lng2)
        are_close[(id1, id2)] = dist < threshold
        are_close[(id2, id1)] = dist < threshold

    def overlaps(cluster1, cluster2):
        for (city1, city2) in itertools.product(cluster1, cluster2):
            if are_close[(city1["_id"], city2["_id"])]:
                return True
        return False

    #
    # Iteratively merge overlapping clusters until nothing left to merge.
    #
    clusters = [[c] for c in cities]
    merged = True
    while merged:
        merged = False

        for (cluster1, cluster2) in list(itertools.combinations(clusters, 2)):
            if overlaps(cluster1, cluster2):
                clusters.remove(cluster1)
                clusters.remove(cluster2)
                clusters.append(cluster1 + cluster2)
                merged = True
                break

    return clusters


def _dedup_lat_lng(cities):
    """Remove duplicates from a list of cities.  Returns a new list."""
    LOGGER.debug("geonames_cities_dedup: %r", locals())

    def generator():
        for cluster in _cluster_cities(cities):
            cluster.sort(key=lambda x: x.get("population", 0), reverse=True)
            yield cluster[0]
    return list(generator())


def _geonames_cities_dedup(cities):
    """Remove duplicates from a list of cities.  Returns a new list."""
    seen = {}
    for city in cities:
        key = (city.get("name"), city.get("admin2"),
               city.get("admin1"), city.get("countryCode"))

        current_pop = city.get("population", 0)
        try:
            previous_pop = seen[key].get("population", 0)
        except KeyError:
            seen[key] = city
        else:
            if current_pop > previous_pop:
                seen[key] = city

    cities = _dedup_lat_lng(list(seen.values()))
    return sorted(cities, key=lambda x: x.get("population", 0), reverse=True)


def is_state(state, country):
    """Return True if the state exists within the specified country.

    :param str state: The name of the state.
    :param str country: The name of the country.
    :rtype: boolean
    """
    if not (state and country):
        raise ValueError("state and country may not be empty or None")
    _test_connection()
    collections = [("admin1", "admin1names"), ("admin2", "admin2names"),
                   ("admind", "names")]
    clean_state = _clean_nonalpha(state)
    clean_country = _clean_nonalpha(country)
    try:
        clean_country = country_to_iso(country)
    except (ValueError, NotFound):
        raise ValueError("no such country: %r", country)
    for col, field in collections:
        if DB[col].find({field: clean_state, "countryCode": clean_country}):
            return True
    return False


def csc_scrub(city, state, country, hint=None):
    """Check the combination of (city, state, country).

    Returning a result object if a unique match can be found (with some level of confidence).
    If either state and country are incorrect, attempts to correct them.

    >>> scrubbed = pygeons.csc_scrub('moscow', None, None)
    >>> scrubbed_result = scrubbed.pop('result')
    >>> scrubbed
    {'score': 0.3, 'st_status': 'D', 'cc_status': 'D', 'count': 33}
    >>> sorted(scrubbed_result.keys())
    ['_id', 'abbr', 'admin1', 'admin1names', 'admin2', 'admin2names', 'asciiname', 'countryCode', 'featureClass', 'featureCode', 'latitude', 'longitude', 'name', 'names', 'names_lang', 'population']

    :param str city: The name of the city.
    :param str state: The name of the state.  May be None.
    :param str country: The name of the country.  May be None.
    :param str hint: unused
    :rtype: dict

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

    LOGGER.debug("csc_scrub: city: %r state: %r country: %r",
                 city, state, country)
    city, state, country, city_alt = _csc_clean_params(city, state, country)
    LOGGER.debug("csc_scrub: clean city: %r (%r) state: %r country: %r",
                 city, city_alt, state, country)

    if state and country and not is_state(state, country):
        LOGGER.info("unable to find state %r in country %r, ignoring",
                    state, country)
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
        LOGGER.debug("trying alternative names: %r", city_alt)
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
        LOGGER.info("multiple matches (%d) found for city %r in country %r, \
but none in state %r", len(res), city, country, state)
        return mkretval(res, 0.4, SCRUB_MOD, SCRUB_OK)
    elif res:
        LOGGER.info("multiple matches (%d) found for (%r, None, %r), \
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
        LOGGER.info("multiple matches (%d) found for city %r in state %r, \
but none in country %r", len(res), city, state, country)
        return mkretval(res, 0.4, SCRUB_OK, SCRUB_MOD)
    elif res:
        LOGGER.info("multiple matches (%d) found for city %r in state %r, \
no country given", len(res), city, state)
        return mkretval(res, 0.5, SCRUB_OK, SCRUB_DERIVED)

    #
    # Perhaps city itself is unique?
    #
    LOGGER.debug("city: %r state: %r country: %r", city, state, country)
    res = csc_find(city, None, None) if city else None
    if not res:
        return None

    score = 0.6 if len(res) == 1 else 0.3
    st_status = SCRUB_MOD if had_state else SCRUB_DERIVED
    cc_status = SCRUB_MOD if had_country else SCRUB_DERIVED
    return mkretval(res, score, st_status, cc_status)


def sc_scrub(state, country):
    """Validate (state, country) combinations.

    If the country is incorrect, attempts to correct it.

    >>> scrubbed = pygeons.sc_scrub('nsw', 'ca')
    >>> scrubbed_result = scrubbed.pop('result')
    >>> scrubbed
    {'score': 0.8, 'cc_status': 'D'}
    >>> sorted(scrubbed_result.keys())
    ['_id', 'abbr', 'admin1', 'admin1id', 'admin1names', 'admin2', 'asciiname', 'countryCode', 'featureClass', 'featureCode', 'latitude', 'longitude', 'name', 'names_lang', 'population']

    :param str state: The name of the state.
    :param str country: The name of the country.
    :rtype: dict"""
    LOGGER.debug("sc_scrub: %r", locals())
    _test_connection()
    _, state, country, _ = _csc_clean_params(None, state, country)

    def find(coll, key):
        return list(DB[coll].find({key: state, "countryCode": country}))

    pairs = [("admin1", "admin1names"), ("admin2", "admin2names"),
             ("admind", "names")]
    res = []
    for coll, key in pairs:
        res.extend(find(coll, key) if country else [])
        LOGGER.debug("sc_scrub: res: %r", res)
        if len(res) == 1:
            return {"result": res[0], "score": 0.9, "cc_status": SCRUB_OK}

        elif res:
            #
            # There is more than one candidate, so we cannot reliably decide.
            #
            break

        #
        # Perhaps the country is wrong?  Try omitting it.
        #
        res.extend(list(DB[coll].find({key: state})))
        LOGGER.debug("sc_scrub: res: %r", res)
        if len(res) == 1:
            return {"result": res[0], "score": 0.8,
                    "cc_status": SCRUB_DERIVED}

    return {}


def csc_list(city, state, country):
    """Given a (city, state, country) query, return a list of matching
    cities.

    Tries harder than csc_find by considering alternative city names, etc.

    :param str city: The name of the city.
    :param str state: The name of the state.  May be None.
    :param str country: The name of the country.  May be None.
    :returns: Cities that match the (city, state, country) query.
    :rtype: list of dict
    """
    LOGGER.debug("csc_list: %r", locals())
    if not (city or state):
        raise ValueError("city and state may not both be empty")
    city, state, country, city_alt = _csc_clean_params(city, state, country)

    have_csc = city and state and country
    res = csc_find(city, state, country, dedup=False) if have_csc else None
    if res:
        return res

    if city_alt and state and country:
        for alt in city_alt:
            res = csc_find(alt, state, country, dedup=False)
            if res:
                res

    #
    # Try omitting state.
    #
    have_cc = city and country
    res = csc_find(city, None, country, dedup=False) if have_cc else None
    if res:
        return res

    #
    # Perhaps state is really a city?
    #
    have_sc = state and country
    res = csc_find(state, None, country, dedup=False) if have_sc else None
    if res:
        return res

    #
    # Either no country given, or city/state/cc match failed - perhaps country
    # is wrong?
    #
    res = csc_find(city, state, None, dedup=False) if city and state else None
    if res:
        return res

    #
    # Hmmm. Perhaps city itself is unique?
    #
    res = csc_find(city, None, None, dedup=False) if city else None
    if res:
        return res

    return []


def sc_list(state, country):
    """Given a (state, country) query, return a list of matching states.

    >>> ['%(name)s, %(countryCode)s' % x for x in pygeons.sc_list('or', None)]
    ['Oregon, US', 'State of Odisha, IN', 'Provincia di Oristano, IT']

    :param str state: The name of the state.
    :param str country: The name of the country.  May be None.
    """
    _test_connection()

    if not state:
        raise ValueError("state may not be empty")

    def find(coll, key, value, ccode):
        query = {key: value}
        if ccode:
            query["countryCode"] = ccode
        LOGGER.debug("find: query: %r", query)
        return DB[coll].find(query)

    def state_generator(state, country):
        pairs = [("admin1", "admin1names"), ("admin2", "admin2names"),
                 ("admind", "names")]
        for coll, key in pairs:
            for obj in find(coll, key, state, country):
                yield obj

    _, state, country, _ = _csc_clean_params(None, state, country)
    return list(state_generator(state, country))


def _to_radian(degrees):
    return math.pi * degrees / 180


def _haversine_dist(lat1, lng1, lat2, lng2):
    """Calculate the distance between two latitude-long pairs."""
    #
    # https://en.wikipedia.org/wiki/Haversine_formula
    #
    def hav(theta):
        """The haversine function."""
        return math.pow(math.sin(theta / 2), 2)

    R = 6371
    fi1, lam1, fi2, lam2 = [_to_radian(x) for x in [lat1, lng1, lat2, lng2]]
    d = 2 * R * math.asin(
        math.sqrt(
            hav(fi2 - fi1) + math.cos(fi1) * math.cos(fi2) * hav(lam2 - lam1)
        )
    )
    return d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?")
    args = parser.parse_args()

    if args.command is None:
        print(CONFIG.dbname)
    elif args.command == "version":
        print(get_version())
    elif args.command == "expected-version":
        print("-".join([DEFAULT_DBNAME, EXPECTED_VERSION]))
    elif args.command == "db":
        print(CONFIG.dbname)
    else:
        parser.error("invalid command: %s" % args[0])

    sys.exit(0 if get_version() > EXPECTED_VERSION else 1)
