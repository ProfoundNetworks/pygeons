#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
"""Process downloaded data prior to import."""
from __future__ import print_function
from __future__ import unicode_literals

import collections

import csv
import json
import logging
import os
import os.path as P
import sys
import tempfile

import plumbum


_LOGGER = logging.getLogger(__name__)
#
# Prevent stderr message about "no handlers found".
# It is possible that somebody is using Pygeon without logging.
# https://docs.python.org/2/howto/logging.html#configuring-logging-for-a-library
#
_LOGGER.addHandler(logging.NullHandler())

_HISTORICAL = frozenset(("ADM1H", "ADM2H", "ADMDH"))

_ENGLISH = "en"
"""The language code for English, all countries speak it."""

_ABBR = "abbr"
"""The language code for English abbreviations."""

_LINK = "link"
"""The language code for Wikipedia links.  We ignore these."""

_UNKNOWN = "??"
"""The language code for names without a language code."""

_ALL_COUNTRIES = "allCountries"
_COUNTRY_INFO = "countryInfo"

Admin = collections.namedtuple("Admin", ["geoid", "code", "name", "names"])
Name = collections.namedtuple("Name", ["geoid", "lang", "name"])


def _read_iso6391():
    curr_dir = P.dirname(P.abspath(__file__))
    with open(P.join(curr_dir, "data/iso639-1.txt")) as fin:
        return fin.read().strip().split("\n")


_ISO639_1 = _read_iso6391()
"""These are the main languages spoken in the world."""


def _scrub(s):
    """Strip punctuation, make everything lowercase."""
    if not s:
        return s
    return "".join([x for x in s.lower().strip() if x != "."])


def _csv_to_name(row):
    row[1] = int(row[1])
    row[3] = row[3]
    if row[2] == "":
        row[2] = _UNKNOWN
    return Name(*row[1:4])


class NameReader(object):
    """Reads names from altNames.tsv one-by-one.

    Expects the file to be sorted by geoid."""

    def __init__(self, fin):
        self.reader = csv.reader(fin, delimiter="\t", quoting=csv.QUOTE_NONE)
        self.last_requested_geoid = None
        self.buf = None

    def _buffered_read(self):
        if self.buf:
            name, self.buf = self.buf, None
            return name
        return _csv_to_name(next(self.reader))

    def read(self, geoid):
        """Read all names for the specified geoid."""
        if self.last_requested_geoid and geoid <= self.last_requested_geoid:
            raise ValueError("geoid must be increasing with each read call")
        self.last_requested_geoid = geoid

        _LOGGER.debug("NameReader.read: called")
        names = []
        while True:
            try:
                name = self._buffered_read()
            except StopIteration:
                _LOGGER.debug("reached end of alt names file")
                break

            if name.geoid == geoid and name.lang != _LINK:
                names.append(name)
            elif name.geoid > geoid:
                self.buf = name
                _LOGGER.debug("moved past required geoid (%d < %d)", geoid, name.geoid)
                break
        return names


class CountryInfo(object):
    """Enables in-memory lookups of countryInfo.txt."""

    def __init__(self, fin):
        self.countries = {}
        for line in fin:
            cinfo = json.loads(line)
            self.countries[cinfo["iso"]] = cinfo

    def languages_spoken_in(self, country):
        """Return the languages spoken in the specified country (ISO2 code).

        Only returns languages specified in ISO639-1."""
        try:
            cinfo = self.countries[country]
        except KeyError:
            return [_ENGLISH]
        else:
            codes = [c.split("-")[0] if "-" in c else c
                     for c in cinfo["languages"]]
            codes = [c for c in codes if c in _ISO639_1]
            return codes


def _get_names(geonames_id, country_code, all_names, cinfo):
    """Get the relevant names for a particular place.

    A name is relevant if it is in the language spoken in that place.
    We assume that the languages spoken in a city are the same as the languages
    spoken in the entire country.

    :param str geonames_id: The GeoNames ID of the place.
    :param str country_code: The country that the place is in.
    :param list all_names: A list of all alternative names for the place.
    :param CountryInfo: the information about various countries.
    :returns: all relevant names, all abbreviations, all names split by language
    :rtype: tuple
    """
    this_country_speaks = cinfo.languages_spoken_in(country_code)
    if _ENGLISH not in this_country_speaks:
        this_country_speaks.append(_ENGLISH)
    this_country_speaks.append(_UNKNOWN)

    _LOGGER.debug("this_country_speaks: %r", this_country_speaks)
    alt_names = [x for x in all_names if x.lang in this_country_speaks]
    _LOGGER.debug("alt_names: %r", alt_names)

    relevant_names_by_language = collections.defaultdict(list)
    for name in alt_names:
        relevant_names_by_language[name.lang].append(_scrub(name.name))

    abbreviations = [x for x in all_names if x.lang == _ABBR]
    abbr = [_scrub(n.name) for n in abbreviations]

    for lang, names in relevant_names_by_language.items():
        relevant_names_by_language[lang] = sorted(set(names))

    relevant_names = [_scrub(n.name) for n in alt_names + abbreviations]

    #
    # N.B. save most of the deduping for later.
    #
    _LOGGER.debug("relevant_names: %r abbr: %r relevant_names_by_language: %r",
                  relevant_names, abbr, relevant_names_by_language)
    return relevant_names, abbr, relevant_names_by_language


def _append_alt_names_country(country, all_names, cinfo):
    geonames_id = country["_id"]
    iso = country["iso"]
    iso3 = country["iso3"]
    names, abbr, names_lang = _get_names(geonames_id, iso, all_names, cinfo)

    scrubbed_name = _scrub(country["name"])
    names.extend([iso.lower(), iso3.lower(), scrubbed_name])
    names = sorted(set(names))

    names_lang["en"].extend([iso.lower(), iso3.lower(), scrubbed_name])
    names_lang["en"] = sorted(set(names_lang["en"]))

    abbr.extend([iso.lower(), iso3.lower()])
    abbr = sorted(set(abbr))

    country["names"] = names
    country["abbr"] = abbr
    country["names_lang"] = dict(names_lang)


def _append_alt_names(place, all_names, cinfo):
    geonames_id = place["_id"]
    country = place["countryCode"]

    names, abbr, names_lang = _get_names(geonames_id, country, all_names, cinfo)

    names.append(place["name"].lower())
    names.append(place["asciiname"].lower())
    names = sorted(set(names))

    names_lang["en"].append(place["name"].lower())
    names_lang["en"].append(place["asciiname"].lower())
    names_lang["en"] = sorted(set(names_lang["en"]))

    place["names"] = names
    place["names_lang"] = dict(names_lang)
    place["abbr"] = abbr


def _place_reader(fin):
    prev_id = None
    for line in sys.stdin:
        place = json.loads(line)
        if prev_id and place["_id"] < prev_id:
            raise ValueError("standard input isn't sorted by geoid")
        prev_id = place["_id"]
        yield place


def append_alt_names(alt_names_path, countries_json_path, input_format,
                     stdin=sys.stdin, stdout=sys.stdout):
    if input_format not in (_ALL_COUNTRIES, _COUNTRY_INFO):
        raise ValueError('invalid input_format')

    with open(countries_json_path) as fin:
        country_info = CountryInfo(fin)

    append_function = {
        _ALL_COUNTRIES: _append_alt_names,
        _COUNTRY_INFO: _append_alt_names_country
    }[input_format]

    with open(alt_names_path) as fin:
        name_reader = NameReader(fin)
        for place in _place_reader(stdin):
            names = name_reader.read(place["_id"])
            _LOGGER.debug("names: %r", names)
            append_function(place, names, country_info)
            stdout.write(json.dumps(place))
            stdout.write("\n")


def _parse_row(row, names, types):
    """Parse a TSV row into a dictionary."""
    if not (len(row) == len(names) == len(types)):
        raise ValueError("row, names, and types must of the same length")
    obj = {}
    for val, key, type_ in zip(row, names, types):
        if type_ == "int":
            obj[key] = int(val) if val else None
        elif type_ == "float":
            obj[key] = float(val) if val else None
        elif type_ == "str":
            obj[key] = val
        elif type_ == "skip":
            pass
        else:
            raise ValueError("unsupported type: %r" % type_)
    return obj


def _get_admin_code(plc, kind):
    """Return the admin code for a place."""
    if kind == "ADM1":
        return ".".join([plc["countryCode"], plc["admin1"]])
    elif kind == "ADM2":
        return ".".join([plc["countryCode"], plc["admin1"], plc["admin2"]])
    else:
        raise ValueError("unexpected kind: %r", kind)


def _adjust_fields(obj):
    """Adjust fields to conform to some existing business logic."""
    if "featureCode" in obj and obj["featureCode"].startswith("ADM1"):
        obj["admin1id"] = _get_admin_code(obj, "ADM1")
    elif "featureCode" in obj and obj["featureCode"].startswith("ADM2"):
        obj["admin2id"] = _get_admin_code(obj, "ADM2")
    if "languages" in obj:
        obj["languages"] = obj["languages"].split(",")


def tsv2json(field_names=None, field_types=None, stdin=sys.stdin, stdout=sys.stdout):
    if not (field_names and field_types):
        raise ValueError('field_names and field_types must be non-empty lists')
    if len(field_names) != len(field_types):
        raise ValueError('field_names and field_types must be the same length')
    reader = csv.reader(stdin, delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in reader:
        _LOGGER.debug(row)
        obj = _parse_row(row, field_names, field_types)
        _adjust_fields(obj)
        stdout.write(json.dumps(obj))
        stdout.write("\n")


def _process_countries(stdin=sys.stdin, stdout=sys.stdout):
    """Read countryInfo.txt from stdin and write JSON to stdout."""
    sort = plumbum.local['sort']['-n', '-k', '17,18', '-t\t']
    sed = plumbum.local['sed']['/^#/d']
    field_names = (
        'iso', 'iso3', 'iso-numeric', 'fips', 'name', 'capital', 'area',
        'population', 'continent', 'tld', 'currencycode', 'currencyname', 'phone',
        'postalcodeformat', 'postalcoderegex', 'languages', '_id',
        'neighbours', 'equivalentfipscode'
    )
    field_types = (
        'str', 'str', 'skip', 'str', 'str', 'str', 'skip', 'int', 'skip',
        'str', 'skip', 'skip', 'skip', 'skip', 'skip', 'str', 'int', 'skip', 'skip'
    )
    tsv2json_kwargs = json.dumps({'field_names': field_names, 'field_types': field_types})
    tsv2json = plumbum.local['pygeons']['tsv2json', '--kwargs', tsv2json_kwargs]
    jq = plumbum.local['jq']['--compact-output', '--unbuffered', 'select(._id != null)']
    chain = (sort < stdin) | sed | tsv2json | jq > stdout
    _run_chain(chain)


def _create_pipeline(alt_tsv_path, countries_json_path):
    field_names = (
        '_id', 'name', 'asciiname', 'altnames', 'latitude', 'longitude',
        'featureClass', 'featureCode', 'countryCode', 'cc2', 'admin1', 'admin2', 'admin3',
        'admin4', 'population', 'elevation', 'dem', 'timezone', 'modificationDate',
    )
    field_types = (
        'int', 'str', 'str', 'skip', 'float', 'float', 'str', 'str', 'str',
        'skip', 'str', 'str', 'skip', 'skip', 'int', 'skip', 'skip', 'skip', 'skip',
    )
    assert len(field_names) == len(field_types), "these need to be the same length"
    tsv2json_kwargs = json.dumps({'field_names': field_names, 'field_types': field_types})
    tsv2json = plumbum.local['pygeons']['tsv2json', '--kwargs', tsv2json_kwargs]
    append_args = json.dumps([alt_tsv_path, countries_json_path, _ALL_COUNTRIES])
    append_flags = ['append_alt_names', '--args', append_args]
    append_alt_names = plumbum.local['pygeons'][append_flags]
    derive_args = json.dumps([countries_json_path])
    derive = plumbum.local['pygeons']['derive', '--args', derive_args]
    chain = tsv2json | append_alt_names | derive
    return chain


def _read_admin_names(fin):
    """Read the file and return a mapping of admin code to names."""
    by_code = {}
    for line in fin:
        place = json.loads(line)
        geoid = place["_id"]
        feature_code = place["featureCode"]
        name = place["name"]
        asciiname = place["asciiname"]

        if feature_code in _HISTORICAL:
            #
            # Ignore historical names because they conflict with current names.
            # e.g. GB.ENG has a historical ADM1 name of "Britannia Superior",
            # which isn't what we want to map to GB.ENG here.
            #
            continue

        admin_code = _get_admin_code(place, place["featureCode"])

        alternative_names = _get_alt_names(place)
        names = alternative_names + [name, asciiname]
        names = sorted(set([x.lower() for x in names]))
        by_code[admin_code] = Admin(geoid, admin_code, name, names)
    return by_code


def _get_alt_names(plc):
    if plc["featureCode"].startswith("ADM1"):
        return plc["admin1names"]
    elif plc["featureCode"].startswith("ADM2"):
        return plc["admin2names"]
    raise ValueError("do not know how to handle featureCode: %r" % plc["featureCode"])


def _append_admin_names(obj, admin1, admin2):
    """Append admin1names/admin2names, convert admin codes to names."""
    admin1code = _get_admin_code(obj, "ADM1")
    admin2code = _get_admin_code(obj, "ADM2")

    if admin1code:
        try:
            place = admin1[admin1code]
        except KeyError:
            _LOGGER.info("unknown admin1 code: %r", admin1code)
            obj["admin1names"] = []
        else:
            obj["admin1"] = place.name
            obj["admin1names"] = place.names

    if admin2code and admin2:
        try:
            place = admin2[admin2code]
        except KeyError:
            _LOGGER.info("unknown admin2 code: %r", admin2code)
            obj["admin2names"] = []
        else:
            obj["admin2"] = place.name
            obj["admin2names"] = place.names


def append_admin_names(adm1_json_path, adm2_json_path=None, stdin=sys.stdin, stdout=sys.stdout):
    with open(adm1_json_path) as fin:
        admin1 = _read_admin_names(fin)

    if adm2_json_path:
        with open(adm2_json_path) as fin:
            admin2 = _read_admin_names(fin)
    else:
        admin2 = {}

    for line in stdin:
        try:
            obj = json.loads(line)
        except ValueError:
            _LOGGER.error("cannot decode JSON from line")
            _LOGGER.error(line)
            raise
        _append_admin_names(obj, admin1, admin2)
        stdout.write(json.dumps(obj))
        stdout.write("\n")


def _run_chain(chain):
    _LOGGER.info('chain: %s', chain)
    handle, tmp_file = tempfile.mkstemp(prefix='pygeon-plumbum-stderr')
    os.close(handle)
    try:
        (chain >= tmp_file)()
    except plumbum.commands.processes.ProcessExecutionError:
        with open(tmp_file) as fin:
            stderr = fin.read()
        _LOGGER.error('<stderr>\n%s\n</stderr>' % stderr)
    finally:
        os.unlink(tmp_file)


def _process_adm1(alt_names_path, countries_path, stdin=sys.stdin, stdout=sys.stdout):
    awk = plumbum.local['awk']['-F', '\\t', '$8 ~ /ADM1H?/']
    pipeline = _create_pipeline(alt_names_path, countries_path)
    jq_flags = ['--compact-output', '. + {"admin1names": .names} | del(.names)']
    jq = plumbum.local['jq'][jq_flags]
    chain = (awk < stdin) | pipeline | jq > stdout
    _run_chain(chain)


def _process_adm2(adm1_json_path, alt_names_path, countries_path,
                  stdin=sys.stdin, stdout=sys.stdout):
    awk = plumbum.local['awk']['-F', '\\t', '$8 ~ /ADM2H?/']
    pipeline = _create_pipeline(alt_names_path, countries_path)
    append_args = json.dumps([adm1_json_path])
    append_admin_names = plumbum.local['pygeons']['append_admin_names', '--args', append_args]
    jq_flags = ['--compact-output', '. + {"admin2names": .names} | del(.names)']
    jq = plumbum.local['jq'][jq_flags]
    chain = (awk < stdin) | pipeline | append_admin_names | jq > stdout
    _run_chain(chain)


def _process_cities(adm1_json_path, adm2_json_path, alt_names_path, countries_path,
                    stdin=sys.stdin, stdout=sys.stdout):
    awk = plumbum.local['awk']['-F', '\\t', '$7 == "P"']
    pipeline = _create_pipeline(alt_names_path, countries_path)
    append_args = json.dumps([adm1_json_path, adm2_json_path])
    append_admin_names = plumbum.local['pygeons']['append_admin_names', '--args', append_args]
    chain = (awk < stdin) | pipeline | append_admin_names > stdout
    _run_chain(chain)


def _process_admd(adm1_json_path, adm2_json_path, alt_names_path, countries_path,
                  stdin=sys.stdin, stdout=sys.stdout):
    awk = plumbum.local['awk']['-F', '\\t', '$8 ~ /ADMDH?/']
    pipeline = _create_pipeline(alt_names_path, countries_path)
    append_args = json.dumps([adm1_json_path, adm2_json_path])
    append_admin_names = plumbum.local['pygeons']['append_admin_names', '--args', append_args]
    chain = (awk < stdin) | pipeline | append_admin_names > stdout
    _run_chain(chain)


def _finalize_countries(alt_tsv_path, countries_json_path, stdin=sys.stdin, stdout=sys.stdout):
    append_args = json.dumps([alt_tsv_path, countries_json_path, _COUNTRY_INFO])
    append_flags = ['append_alt_names', '--args', append_args]
    append_alt_names = plumbum.local['pygeons'][append_flags]
    chain = (append_alt_names < stdin) > stdout
    _run_chain(chain)


def _process_postcodes(stdin=sys.stdin, stdout=sys.stdout):
    cut = plumbum.local['cut']['-s', '-f', '1,2,3,4']
    field_names = ('countryCode', 'postCode', 'placeName', 'adminName')
    field_types = ('str', 'str', 'str', 'str')
    tsv2json_kwargs = json.dumps({'field_names': field_names, 'field_types': field_types})
    tsv2json = plumbum.local['pygeons']['tsv2json', '--kwargs', tsv2json_kwargs]
    chain = (cut < stdin) | tsv2json > stdout
    _run_chain(chain)


def process(subdir, clobber=False):
    def ap(filename):
        return P.join(subdir, filename)

    countries_txt = ap('countryInfo.txt')
    countries_json = ap('countries.json')
    if clobber or not P.isfile(countries_json):
        with open(countries_txt, 'rb') as fin, open(countries_json, 'wb') as fout:
            _process_countries(stdin=fin, stdout=fout)

    #
    # TODO: this part here is a bit silly.
    # We're passing in countries.json as both stdin and command-line args.
    # This is all to shoehorn it into the append_alt_names function.
    # We should really just write a separate function to handle this for us.
    #
    countries_final_json = ap('countries-final.json')
    if clobber or not P.isfile(countries_final_json):
        with open(countries_json, 'rb') as fin, open(countries_final_json, 'wb') as fout:
            _finalize_countries(countries_json, stdin=fin, stdout=fout)

    alt_names_path = ap('alternateNames.tsv')
    all_countries_tsv = ap('allCountries.tsv')
    adm1_json = ap('adm1.json')
    if clobber or not P.isfile(adm1_json):
        with open(all_countries_tsv, 'rb') as fin, open(adm1_json, 'wb') as fout:
            _process_adm1(alt_names_path, countries_json, stdin=fin, stdout=fout)

    adm2_json = ap('adm2.json')
    if clobber or not P.isfile(adm2_json):
        with open(all_countries_tsv, 'rb') as fin, open(adm2_json, 'wb') as fout:
            _process_adm2(adm1_json, alt_names_path, countries_json, stdin=fin, stdout=fout)

    admd_json = ap('admd.json')
    if clobber or not P.isfile(admd_json):
        with open(all_countries_tsv, 'rb') as fin, open(admd_json, 'wb') as fout:
            _process_admd(adm1_json, adm2_json, alt_names_path, countries_json,
                          stdin=fin, stdout=fout)

    cities_json = ap('cities.json')
    if clobber or not P.isfile(cities_json):
        with open(all_countries_tsv, 'rb') as fin, open(cities_json, 'wb') as fout:
            _process_cities(adm1_json, adm2_json, alt_names_path, countries_json,
                            stdin=fin, stdout=fout)

    postcodes_txt = ap('allCountriesPostcodes.txt')
    postcodes_json = ap('postcodes.json')
    if clobber or not P.isfile(postcodes_json):
        with open(postcodes_txt, 'rb') as fin, open(postcodes_json, 'wb') as fout:
            _process_postcodes(stdin=fin, stdout=fout)
