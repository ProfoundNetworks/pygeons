#
# ported from bin/alt_city_names.js
#
import logging
import re
import sqlite3

from typing import Optional

_REGEX = re.compile(r'(.*\S)[\s-](on|by)[\s-](the[\s-])?', re.IGNORECASE)
_BLACKLIST = {
    'lake',
    'lakes',
    'village',
    'pines',
    'reserve',
    'the park',
    'city',
    'come',
}

_LOGGER = logging.getLogger(__name__)


def derive(name: str) -> Optional[str]:
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
    match = _REGEX.match(name)
    if not match:
        return None

    barename = match.group(1)
    if barename.lower() in _BLACKLIST or name.endswith('Park'):
        return None

    return barename


def derive_barenames(dbpath: str) -> None:
    conn = sqlite3.connect(dbpath)
    c = conn.cursor()

    for country in ('US', 'GB', 'IE', 'AU', 'NZ', 'ZA'):
        command = (
            'SELECT geonameid, name, admin1_code FROM geoname '
            'WHERE country_code = ? '
        )
        cities = {
            (name, admin1_code)
            for (unused_geonameid, name, admin1_code) in c.execute(command, (country, ))
        }
        for geonameid, name, admin1_code in c.execute(command, (country, )):
            #
            # If there's already a city with this derived name, do not add it.
            #
            derived_name = derive(name)
            if derived_name and (derived_name, admin1_code) not in cities:
                _LOGGER.info('%d %r -> %r', geonameid, name, derived_name)
                #
                # TODO: INSERT INTO alternatename
                #


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    derive_barenames('/home/misha/.pygeons/db.sqlite3')
