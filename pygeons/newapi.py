"""A more Pythonic interface for geonames.

Offers the following abstraction over the geonames data:

- The world is divided into countries (see the Country class)
- Each country is divided into states (see the State class)
- A state includes multiple cities (see the City class)

Countries are at the very top level.
You may access them via the constructor directly.

>>> Country('ivory coast')
Country('Ivory Coast')

Common alternative names also work:

>>> Country('côte d’ivoire')
Country('Ivory Coast')

ISO abbreviations (both two- and three-letter) also work:

>>> Country('civ')
Country('Ivory Coast')
>>> _.iso
'CI'

You can access the states of a country with the obvious syntax:

>>> Country('usa').states['idaho']
State.gid(5596512, 'ADM1', 'Idaho', 'US')
>>> 'idaho' in Country('usa').states
True

States are administrative divisions of a country.
They're called different things depending on the country (e.g. territory, province, region, prefecture, etc.), but most countries have such divisions for administrative purposes.

In geonames, there are multiple levels of administrative entities, such as:

    - ADM1
    - ADM2
    - ADMD

Pygeons groups all the administrative entities under the State class.

Common names and abbreviations work:

>>> Country('usa').states['id']
State.gid(5596512, 'ADM1', 'Idaho', 'US')

On the next level down, you have cities:

>>> Country('usa').states['idaho'].cities['moscow']
City.gid(5601538, 'Moscow', 'Idaho', 'US')
>>> 'moscow' in Country('usa').states['idaho']
True

You can shortcut the state level altogether.
This is particularly useful if you don't know the state.

>>> 'moscow' in Country('russia')
True
>>> Country('russia').cities['moscow']
City.gid(524901, 'Moscow', 'Moskva', 'RU')

You may be surprised that city names are not necessarily unique.
In such cases, use the find_cities function:

>>> find_cities("oslo")
[City.gid(3143244, 'Oslo', 'Oslo County', 'NO'), City.gid(5040425, 'Oslo', 'Minnesota', 'US'), City.gid(4167241, 'Oslo', 'Florida', 'US'), City.gid(5040424, 'Oslo', 'Minnesota', 'US'), City.gid(6674712, 'Oslo', 'Junín', 'PE')]

>>> oslo = find_cities("oslo", country='no')[0]

If your query is sufficiently narrow and yields only one result, you may find the find_city function more helpful than the above:

>>> oslo = find_city("oslo", country="no")

However, if there are multiple matches, the find_city function will fail.
Use find_cities instead, and then narrow down the results as necessary.

>>> oslo
City.gid(3143244, 'Oslo', 'Oslo County', 'NO')

The gid is the unique geonames ID for a place.
You can use it as a compact identifier to reconstruct place names:

>>> City.gid(3143244)
City.gid(3143244, 'Oslo', 'Oslo County', 'NO')

Each place is backed by a dict.  You can access its contents directly:

>>> for key in sorted(oslo.data.keys()):
...     print(key)
_id
abbr
admin1
admin1names
admin2
admin2names
asciiname
countryCode
featureClass
featureCode
latitude
longitude
name
names
names_lang
population

You can also access them more conveniently as attributes:

>>> oslo.latitude, oslo.longitude, oslo.population
(59.91273, 10.74609, 580000)

Calculating the distance between two cities::

>>> trondheim = find_city('trondheim')
>>> trondheim
City.gid(3133880, 'Trondheim', 'Trøndelag', 'NO')

>>> round(oslo.distance_to(trondheim))
392

Testing for valid city and country combinations:

>>> 'sapporo' in Country('jp').cities
True
>>> 'auckland' in Country('nz').cities
True
>>> 'auckland' in Country('au').cities
False

Testing for valid state and country combinations:

>>> 'hokkaido' in Country('jp').states
True
>>> 'nsw' in Country('au').states
True
>>> 'new mexico' in Country('ca').states
False

Expanding country-specific abbreviations:

>>> Country('au').expand('nsw')
'State of New South Wales'
>>> Country('usa').expand('co')
'Colorado'

Pygeons understands names in English and languages local to a particular country:

>>> find_city('札幌')
City.gid(2128295, 'Sapporo', 'Hokkaido', 'JP')

>>> find_city('москва', country='ru')
City.gid(524901, 'Moscow', 'Moskva', 'RU')

>>> Country('jp').normalize(language='ja')
'日本'

"""

from . import pygeons
from . import db

DEFAULT_LANGUAGE = 'en'


class Country:
    def __init__(self, name):
        self.data = pygeons.country_info(name)

        #
        # The collection to go through depends on the country.
        # e.g. for Australia, it makes sense to go through admin1.
        # For GB, it makes more sense to go through admin2, because the
        # top level contains country names like England, Scotland, etc.
        #
        self._state_collection = 'admin1'

    def __getattr__(self, name):
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError('no such attribute: %r in self.data' % name)

    def __repr__(self):
        return 'Country(%(name)r)' % self.data

    def __str__(self):
        return 'Country(%(name)r)' % self.data

    def __contains__(self, item):
        if isinstance(item, (City, State)):
            return item.countryCode == self.iso

        if isinstance(item, str):
            for fn in (pygeons.is_city, pygeons.is_ppc, pygeons.is_state):
                try:
                    if fn(self.iso, item):
                        return True
                except Exception:
                    #
                    # TODO:
                    #
                    pass

    def normalize(self, language=DEFAULT_LANGUAGE):
        if language == DEFAULT_LANGUAGE:
            return self.name.lower()
        return self.names_lang[language][0]

    def expand(self, abbreviation):
        for col in (pygeons.ADM1, pygeons.ADM2, pygeons.ADMD, pygeons.CITY):
            return pygeons.expand(col, self.iso, abbreviation)

    @property
    def states(self):
        return StateCollection({'countryCode': self.iso})

    @property
    def cities(self):
        return CityCollection({'countryCode': self.iso})

    @property
    def postcodes(self):
        def gen():
            query = {'countryCode': self.iso}
            for info in db.DB.postcodes.find(query):
                yield Postcode(info)

        return list(gen())


class StateCollection:
    def __init__(self, query, collection='admin1'):
        self._query = query
        self._collection = collection

    def __iter__(self):
        self._cursor = db.DB[self._collection].find(self._query)
        return self

    def __next__(self):
        info = next(self._cursor)
        return State(info)

    def __getitem__(self, key):
        country = self._query.get('countryCode', None)
        return find_state(key, country=country)

    def __contains__(self, key):
        country = self._query.get('countryCode', None)
        return pygeons.is_state(key, country)

    def __str__(self):
        return 'StateCollection(%r)' % self._query

    def __repr__(self):
        return 'StateCollection(%r)' % self._query

    def __len__(self):
        return db.DB[self._collection].find(self._query).count()


class State:
    def __init__(self, data):
        self.data = data
        for key, value in self.data.items():
            setattr(self, key, value)

    def __repr__(self):
        return 'State.gid(%(_id)r, %(featureCode)r, %(name)r, %(countryCode)r)' % self.data

    def __str__(self):
        return 'State(%(featureCode)r, %(name)r, %(countryCode)r)' % self.data

    def __contains__(self, item):
        if isinstance(item, str):
            #
            # FIXME: abusing the indexed admin1names field here
            #
            query = {'names': item, 'admin1names': self.data['admin1names'][0]}
            results = db.DB.cities.find(query)
            return bool(results.count())

    def normalize(self, language=DEFAULT_LANGUAGE):
        return self.names_lang[language][0]

    @property
    def country(self):
        return Country(self.countryCode)

    @staticmethod
    def gid(geonames_id, *args, **kwargs):
        db.test_connection()
        #
        # Maybe try admin2?
        #
        info = db.DB.admin1.find_one({'_id': geonames_id})
        return State(info)

    @property
    def cities(self):
        #
        # FIXME:
        #
        return CityCollection({'countryCode': self.countryCode, 'admin1names': self.name})


class CityCollection:
    def __init__(self, query):
        self._query = query

    def __iter__(self):
        self._cursor = db.DB.cities.find(self._query)
        return self

    def __next__(self):
        info = next(self._cursor)
        return City(info)

    def __getitem__(self, key):
        #
        # FIXME: What about admin2, admind?
        #
        state = self._query.get('admin1names', None)
        country = self._query.get('countryCode', None)
        return find_city(key, state=state, country=country)

    def __contains__(self, key):
        country = self._query.get('countryCode', None)
        return pygeons.is_city(country, key)

    def __str__(self):
        return 'CityCollection(%r)' % self._query

    def __repr__(self):
        return 'CityCollection(%r)' % self._query

    def __len__(self):
        return db.DB.cities.find(self._query).count()


class City:
    def __init__(self, info):
        self.data = info

    def __getattr__(self, name):
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError('no such attribute: %r in self.data' % name)

    def __repr__(self):
        return 'City.gid(%(_id)r, %(name)r, %(admin1)r, %(countryCode)r)' % self.data

    def __str__(self):
        return 'City(%(name)r, %(admin1)r, %(countryCode)r)' % self.data

    @property
    def state(self):
        pass

    @property
    def country(self):
        return Country(self.countryCode)

    @staticmethod
    def gid(geonames_id, *args, **kwargs):
        db.test_connection()
        info = db.DB.cities.find_one({'_id': geonames_id})
        return City(info)

    def distance_to(self, other):
        return pygeons._haversine_dist(
            self.latitude, self.longitude,
            other.latitude, other.longitude,
        )


class Postcode:
    def __init__(self, info):
        self.data = info

    def __repr__(self):
        return 'Postcode(%(postCode)r, %(placeName)r)' % self.data

    def __str__(self):
        return 'Postcode(%(postCode)r, %(placeName)r)' % self.data

    def normalize(self, language=DEFAULT_LANGUAGE):
        #
        # FIXME
        #
        return self.data['placeName']


def find_cities(name, state=None, country=None):
    return [City(data) for data in pygeons.csc_list(name, state, country)]


def find_city(name, state=None, country=None):
    cities = find_cities(name, state=state, country=country)
    if len(cities) == 1:
        return cities[0]

    raise ValueError(
        'Ambiguous query (%d unique results).  Call '
        'find_cities(%r, %r, %r) to see them all.' % (
            len(cities), name, state, country
        )
    )


def find_states(name, country=None):
    return [State(data) for data in pygeons.sc_list(name, country)]


def find_state(name, country=None):
    states = find_states(name, country=country)
    if len(states) == 1:
        return states[0]

    admin1 = [s for s in states if s.featureCode == 'ADM1']
    if len(admin1) == 1:
        return admin1[0]

    raise ValueError('ambiguous query (%d unique results)' % len(states))
