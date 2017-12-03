=======
pygeons
=======


.. image:: https://img.shields.io/pypi/v/pygeons.svg
        :target: https://pypi.python.org/pypi/pygeons

.. image:: https://img.shields.io/travis/mpenkov/pygeons.svg
        :target: https://travis-ci.org/mpenkov/pygeons

.. image:: https://readthedocs.org/projects/pygeons/badge/?version=latest
        :target: https://pygeons.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/mpenkov/pygeons/shield.svg
     :target: https://pyup.io/repos/github/mpenkov/pygeons/
     :alt: Updates


Geographical queries made simple.

* Free software: MIT license
* Documentation: https://pygeons.readthedocs.io.

>>> # Scrub a (city, state, country) combination
>>> pprint(pygeons.csc_scrub('sydney', 'nsw', 'au'))
{'cc_status': 'O',
 'count': 1,
 'result': {'_id': 2147714,
            'abbr': [],
            'admin1': 'State of New South Wales',
            'admin1names': ['new south wales',
                            'nsw',
                            'state of new south wales'],
            'admin2': '17200',
            'admin2names': [],
            'asciiname': 'Sydney',
            'countryCode': 'AU',
            'featureClass': 'P',
            'featureCode': 'PPLA',
            'latitude': -33.86785,
            'longitude': 151.20732,
            'name': 'Sydney',
            'names': ['syd', 'sydney', 'sydney city'],
            'names_lang': {'en': ['syd', 'sydney', 'sydney city']},
            'population': 4627345},
 'score': 0.9,
 'st_status': 'O'}
>>> # Another scrub example, with the country name missing
>>> pprint(pygeons.csc_scrub('sydney', 'nsw', None))
{'cc_status': 'D',
 'count': 1,
 'result': {'_id': 2147714,
            'abbr': [],
            'admin1': 'State of New South Wales',
            'admin1names': ['new south wales',
                            'nsw',
                            'state of new south wales'],
            'admin2': '17200',
            'admin2names': [],
            'asciiname': 'Sydney',
            'countryCode': 'AU',
            'featureClass': 'P',
            'featureCode': 'PPLA',
            'latitude': -33.86785,
            'longitude': 151.20732,
            'name': 'Sydney',
            'names': ['syd', 'sydney', 'sydney city'],
            'names_lang': {'en': ['syd', 'sydney', 'sydney city']},
            'population': 4627345},
 'score': 0.8,
 'st_status': 'O'}
>>> # Normalize a state abbreviation
>>> pygeons.norm('admin1', 'AU', 'nsw')
'State of New South Wales'
>>> # Translate a country name in the native language into English
>>> pygeons.country_info('россия')['names_lang']['en']
['ru', 'rus', 'russia', 'russian federation', 'russian socialist federative soviet republic', 'russian soviet federated socialist republic', 'russian soviet federative socialist republic']

Features
--------

* Determine if a (city, state and country) combination corresponds to an existing place name
* Scrub (city, state, country) combinations
* Normalize city, state and country names to their canonical representations
* Frame queries in English as well as languages native to each particular country

Credits
---------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage

