.. highlight:: shell

============
Installation
============


Stable release
--------------

To install pygeons, run this command in your terminal:

.. code-block:: console

    $ pip install pygeons

This is the preferred method to install pygeons, as it will always install the most recent stable release. 

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for pygeons can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/mpenkov/pygeons

Or download the `tarball`_:

.. code-block:: console

    $ curl  -OL https://github.com/mpenkov/pygeons/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ python setup.py install


.. _Github repo: https://github.com/mpenkov/pygeons
.. _tarball: https://github.com/mpenkov/pygeons/tarball/master

Populating the Database
-----------------------

Pygeons requires data from GeoNames.org_.
This data is free for sharing and adaptations as long as you abide by the `GeoNames license`_.

Pygeons includes scripts that download and import the data into a local MongoDB.
To download the data, run::

    bash bin/download.sh /tmp/pygeons

You may select any subdirectory to download the files into.
The data takes several GB, so make sure you have enough space.

To preprocess the data, run::

    bash bin/preprocess.sh /tmp/pygeons

This prepares the data for import into the DB.
Finally, to import the data, run::

    bash bin/import.sh /tmp/pygeons

The above step will import the entire GeoNames database into a local MongoDB.
This will require tens of GB of storage space.
If you don't have that space, you may import countries individually by specifying their ISO codes::

    bash bin/import.sh /tmp/pygeons RU AU JP

Once the import is complete, you are ready to use pygeons!

.. _GeoNames.org: http://www.geonames.org
.. _GeoNames license: https://creativecommons.org/licenses/by/4.0/
