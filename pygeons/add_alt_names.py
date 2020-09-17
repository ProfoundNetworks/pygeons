"""Add alternative names using some ad hoc business logic."""

import collections
import logging
import os.path as P
import re

from typing import (
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
)

import yaml

import pygeons.db

_LOGGER = logging.getLogger(__name__)
_BARENAME_REGEX = re.compile(r'(.*\S)[\s-](on|by)[\s-](the[\s-])?', re.IGNORECASE)
_BARENAME_BLACKLIST = {
    'lake',
    'lakes',
    'village',
    'pines',
    'reserve',
    'the park',
    'city',
    'come',
}
_ENGLISH_SPEAKING_COUNTRIES = ('US', 'GB', 'IE', 'AU', 'NZ', 'ZA')


def _load(name):
    """Load the data file with the specified name."""
    curr = P.dirname(P.abspath(__file__))
    with open(P.join(curr, "data", "%s.yml" % name)) as fin:
        return yaml.full_load(fin)


def _get_existing_names(
    feature_code: str,
    country_code: str,
) -> Dict[str, List[str]]:
    c = pygeons.db.CONN.cursor()

    existing = collections.defaultdict(set)
    command = (
        'SELECT G.geonameid, A.alternate_name '
        'FROM geoname G JOIN alternatename A on G.geonameid = A.geonameid '
        'WHERE feature_code = ? AND country_code = ?'
    )
    params = (feature_code, country_code)
    for geonameid, name in c.execute(command, params):
        existing[geonameid].add(name.lower())

    return dict(existing.items())


def _insert(record_generator: Iterator[Tuple[int, str, str]]) -> None:
    c = pygeons.db.CONN.cursor()
    insert = (
        'INSERT INTO alternatename(geonameid, alternate_name, isolanguage) '
        'VALUES (?, ?, ?)'
    )
    params = list(record_generator())
    _LOGGER.info('inserting %d new records', len(params))
    c.executemany(insert, params)

    #
    # FIXME: primary key isn't being autoincremented for some reason
    #


def add_gb_county_names() -> None:
    c = pygeons.db.CONN.cursor()
    data = _load('gb-counties')
    existing = _get_existing_names('ADM2', 'GB')
    command = (
        'SELECT geonameid, name FROM geoname '
        'WHERE feature_code = "ADM2" AND country_code = "GB"'
    )

    def record_generator():
        for geonameid, name in c.execute(command):
            try:
                new_names = data[name]
            except KeyError:
                continue

            for name in new_names:
                if name.lower() not in existing[geonameid]:
                    yield geonameid, name, 'en', True

    insert = (
        'INSERT INTO alternatename(geonameid, alternate_name, isolanguage, isShortName) '
        'VALUES (?, ?, ?, ?)'
    )

    params = list(record_generator())
    c.executemany(insert, params)
    pygeons.db.CONN.commit()


def add_ie_county_names() -> None:
    data = _load('ie-support')
    c = pygeons.db.CONN.cursor()

    existing = _get_existing_names('ADM2', 'IE')

    command = (
        'SELECT geonameid FROM geoname '
        'WHERE name = ? AND feature_code = "ADM2" AND country_code = "IE"'
    )

    def record_generator() -> Iterator[Tuple[int, str, str]]:
        for name, barename in sorted(data['adm2_barenames'].items()):
            c.execute(command, (name, ))
            try:
                geonameid = next(c)[0]
            except StopIteration:
                _LOGGER.error('unable to find IE.ADM2 %r', name)
                continue

            new_names = {
                barename,
                'County ' + barename,
                'Co ' + barename,
                barename + ' County',
            }
            for name in new_names:
                if name.lower() not in existing[geonameid]:
                    yield geonameid, name, 'en'

    _insert(record_generator)
    pygeons.db.CONN.commit()


def add_ru_oblast_and_krai():
    #
    # Using this here is sub-optimal, because it requires that the trie be
    # populated.  This is a bit wasteful, because we'll have to repopulate
    # the trie once we insert additional records into the DB.
    #
    # On the other hand, using the SQL directly is a bit of a PITA.
    #
    import pygeons.api

    data = _load('ru-support')

    #
    # Most oblast names in geonames are "bare",
    # e.g. "Murmansk Oblast" instead of "Murmanskaya Oblast".
    # There are some exceptions, e.g. Tverskaya Oblast.
    # Make sure both bare and non-bare names are present.
    #
    # The same thing goes for krai names, with inconsistencies about
    # how the "short i" is handled at the end of the word.
    # e.g. Perm Krai vs Altaiskiy Kray.
    #
    # Some oblast/krai names have annoying apostrophes.
    # Ensure that non-apostrophe variants are also present
    #
    oblast_regex = re.compile(r" oblast['’]?$", re.IGNORECASE)
    krai_regex = re.compile(r" kra[iy]$", re.IGNORECASE)

    def generate_names(geoname):
        if oblast_regex.search(geoname.name):
            barename = oblast_regex.sub('', geoname.name)
            assert barename != geoname.name

            if barename.endswith('aya'):
                try:
                    barename = data['oblast_barenames'][barename]
                except KeyError:
                    _LOGGER.error('unable to unconjugate: %r', barename)
                    return

            for b in (barename, barename.replace('’', '')):
                yield 'en', b
                yield 'en', b + ' Oblast'
                yield 'en', b + ' Region'

            yield 'ru', re.sub('область', 'обл', geoname.normalize('ru'), re.I)
        elif krai_regex.search(geoname.name):
            barename = krai_regex.sub('', geoname.name)
            assert barename != geoname.name

            if barename.endswith('skiy'):
                try:
                    barename = data['krai_barenames'][barename]
                except KeyError:
                    _LOGGER.error('unable to unconjugate: %r', barename)
                    return

            for b in (barename, barename.replace('’', '')):
                yield 'en', b
                yield 'en', b + ' Krai'
                yield 'en', b + ' Kray'
                yield 'en', b + ' Region'

    def generate_records():
        russia = pygeons.api.Country('russia')
        for place in russia.admin1:
            existing = set(place.names)
            for (lang, name) in set(generate_names(place)):
                if (lang, name) not in existing:
                    yield place.geonameid, name, lang

    _insert(generate_records)
    pygeons.db.CONN.commit()


def add_ru_names():
    existing = _get_existing_names('ADM1', 'RU')
    data = _load('ru-support')

    def generate_names(canonical_name):
        if oblast_regex.search(canonical_name):
            bare = oblast_regex.sub("", canonical_name)
            assert bare != canonical_name

            try:
                bare = data['unconjugation'][bare.lower()]
            except KeyError:
                _LOGGER.error("unable to unconjugate bare name: %s", bare)

            yield 'en', bare
            yield 'en', bare + ' Oblast'
            yield 'en', bare + ' Region'
            yield 'en', bare + ' Reg'
        elif krai_regex.search(canonical_name):
            bare = krai_regex.sub("", canonical_name)
            assert bare != canonical_name

            try:
                bare = data['unconjugation'][bare.lower()].title()
            except KeyError:
                _LOGGER.error("unable to unconjugate bare name: %s", bare)

            yield 'en', bare
            yield 'en', bare + ' Krai'
            yield 'en', bare + ' Kray'
            yield 'en', bare + ' Region'
            yield 'en', bare + ' Reg'

        try:
            names_by_lang = data['ADM1'][canonical_name.lower()]
        except KeyError:
            pass
        else:
            for lang, names in names_by_lang.items():
                for name in names:
                    yield lang, name

    c = pygeons.db.CONN.cursor()
    command = (
        'SELECT geonameid, name FROM geoname '
        'WHERE name = ? AND feature_code = "ADM1" AND country_code = "RU"'
    )

    def generate_records():
        for name in data['ADM1']:
            c.execute(command, (name, ))
            try:
                geonameid = next(c)[0]
            except StopIteration:
                _LOGGER.error('not found in RU/ADM1: %r', name)
                continue

        for lang, lang_names in data['ADM1'][name].items():
            for new_name in lang_names:
                if new_name.lower() not in existing[geonameid]:
                    yield geonameid, new_name, lang

    _insert(generate_records)
    pygeons.db.CONN.commit()


def _strip_ken_suffix(name):
    """
    >>> _strip_ken_suffix('Akita ken')
    'Akita'
    >>> _strip_ken_suffix('Akita-ken')
    'Akita'
    >>> _strip_ken_suffix('Akita Prefecture')
    'Akita'
    """
    return re.sub(r'[- ](ken|prefecture)', '', name, flags=re.IGNORECASE)


def add_jp_prefecture_names():
    existing = _get_existing_names('ADM1', 'JP')

    command = (
        'SELECT geonameid, name FROM geoname '
        'WHERE feature_code = "ADM1" AND country_code = "JP"'
    )
    c = pygeons.db.CONN.cursor()

    def generate_names(name) -> Iterator[str]:
        barename = _strip_ken_suffix(name)
        yield barename

        if barename == 'Hokkaido':
            pass
        elif barename in ('Ōsaka', 'Tokyo'):
            yield barename + ' Prefecture'
        else:
            yield barename + '-ken'
            yield barename + ' Prefecture'

    def generate_records() -> Iterator[Tuple[int, str, str]]:
        for geonameid, name in c.execute(command):
            for new_name in sorted(set(generate_names(name))):
                if new_name.lower() not in existing[geonameid]:
                    yield geonameid, name, 'en'

    _insert(generate_records)
    pygeons.db.CONN.commit()


def derive_english_names():
    #
    # In this particular case, it's far easier to use pygeons.api than deal
    # with pygeons.db directly, even though it may be slightly slower.
    #
    import pygeons.api

    saint_regex = re.compile(r"\bsaint\b", re.IGNORECASE)
    mount_regex = re.compile(r"\bmount\b", re.IGNORECASE)
    xoy_regex = re.compile(r"\s+o[’']\s+", re.IGNORECASE)
    o_regex = re.compile(r"^o[’']\s+", re.IGNORECASE)

    def generate_names(geoname) -> Iterator[str]:
        #
        # Hyphenated names should always have space-separated variants
        #
        yield geoname.name.replace("-", " ")
        yield geoname.asciiname.replace("-", " ")

        derived = []
        derive_from = [name for (lang, name) in geoname.names if lang in ('', 'en')]

        #
        # Saint X names should always have St X variants
        #
        if saint_regex.search(geoname.name):
            derived.extend([saint_regex.sub("St", n) for n in derive_from])

        #
        # Mount X names should always have Mt X variants
        #
        if mount_regex.search(geoname.name):
            derived.extend([mount_regex.sub("Mt", n) for n in derive_from])

        #
        # X O' Y names should always have 'of' and 'o' variants
        #
        if xoy_regex.search(geoname.name):
            derived.extend([xoy_regex.sub(" o' ", n) for n in derive_from])
            derived.extend([xoy_regex.sub(" o’ ", n) for n in derive_from])
            derived.extend([xoy_regex.sub(" of ", n) for n in derive_from])
            derived.extend([xoy_regex.sub(" o ", n) for n in derive_from])

        #
        # O' XYZ names should have variants with that space removed
        #
        if o_regex.search(geoname.name):
            derived.extend([o_regex.sub("o'", n) for n in derive_from])
            derived.extend([o_regex.sub("o’", n) for n in derive_from])

        for d in derived:
            yield d

    def generate_records() -> Iterator[Tuple[int, str, str]]:
        for country_code in _ENGLISH_SPEAKING_COUNTRIES:
            country = pygeons.api.Country(country_code)
            children = pygeons.api.Collection(country)
            for geoname in children:
                existing_names = {name.lower() for (lang, name) in geoname.names}
                for new_name in sorted(set(generate_names(geoname))):
                    if new_name.lower() not in existing_names:
                        yield geoname.geonameid, new_name, 'en'

    _insert(generate_records)
    pygeons.db.CONN.commit()


def derive_city_name(name: str) -> Optional[str]:
    """
    >>> derive('Sydney')
    >>> derive('Sydney on Vaal')
    'Sydney'
    >>> derive('Sunrise-on-Sea')
    'Sunrise'
    >>> derive('Saint Michael’s on Sea')
    'Saint Michael’s'
    >>> derive('Kenton on Sea')
    'Kenton'
    >>> derive('Henley on Klip')
    'Henley'
    """
    match = _BARENAME_REGEX.match(name)
    if not match:
        return None

    barename = match.group(1)
    if barename.lower() in _BARENAME_BLACKLIST or name.endswith('Park'):
        return None

    return barename


def derive_english_city_names() -> None:
    c = pygeons.db.CONN.cursor()

    def generate_records() -> Iterator[Tuple[int, str, str]]:
        for country in _ENGLISH_SPEAKING_COUNTRIES:
            command = (
                'SELECT geonameid, name, admin1_code FROM geoname '
                'WHERE country_code = ? '
            )
            cities = {
                (name.lower(), admin1_code)
                for (unused_geonameid, name, admin1_code) in c.execute(command, (country, ))
            }
            for geonameid, name, admin1_code in c.execute(command, (country, )):
                #
                # If there's already a city with this derived name, do not add it.
                #
                derived_name = derive_city_name(name)
                if derived_name and (derived_name.lower(), admin1_code) not in cities:
                    yield geonameid, derived_name, 'en'

    _insert(generate_records)
    pygeons.db.CONN.commit()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(funcName)s: %(message)s')
    pygeons.db.connect()
    # add_gb_county_names()
    # add_ie_county_names()
    add_ru_oblast_and_krai()
    # add_ru_names()
    # add_jp_prefecture_names()
    # derive_english_names()
    # derive_english_city_names()
