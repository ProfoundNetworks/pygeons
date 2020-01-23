#
# -*- coding: utf-8 -*-
# (C) Copyright: Profound Networks, LLC 2016
#
"""Downloads resources from GeoNames.org."""
import os.path as P
import subprocess

_FREE = 'http://download.geonames.org/export/dump/'
_PREMIUM = 'http://www.geonames.org/premiumdump/%(year)s%(month)s/'


def _wget(url, cwd, cookies_path=None, filename=None):
    """Downloads the specified URL to the current directory."""
    command = ['wget', url]
    if cookies_path:
        command += ['--load-cookies', cookies_path]
    if filename:
        command += ['-O', filename]
    subprocess.check_call(command, cwd=cwd)


def _unzip(path, cwd):
    """Unzips the specified file into the current directory."""
    subprocess.check_call(['unzip', path], cwd=cwd)


def _sort(subdir, infile, outfile, *args):
    infile = P.join(subdir, infile)
    outfile = P.join(subdir, outfile)
    command = ['sort', infile] + list(args)
    with open(outfile, 'wb') as stdout:
        subprocess.check_call(command, stdout=stdout)


def _download(base_url, subdir):
    if not P.isfile(P.join(subdir, 'countryInfo.txt')):
        _wget(base_url + 'countryInfo.txt', subdir)

    if not P.isfile(P.join(subdir, 'allCountries.tsv')):
        _wget(base_url + 'allCountries.zip', subdir)
        _unzip('allCountries.zip', subdir)
        _sort(subdir, 'allCountries.txt', 'allCountries.tsv', '-n', '-k', '2,3')

    if not P.isfile(P.join(subdir, 'allCountriesPostcodes.txt')):
        _wget(base_url + '../zip/allCountries.zip', subdir, filename='allCountriesPostcodes.zip')
        command = ['unzip', '-o', '-p', P.join(subdir, 'allCountriesPostcodes.zip')]
        with open(P.join(subdir, 'allCountriesPostcodes.txt'), 'wb') as fout:
            subprocess.check_call(command, stdout=fout)

    if not P.isfile(P.join(subdir, 'alternateNames.tsv')):
        _wget(base_url + 'alternateNames.zip', subdir)
        _unzip('alternateNames.zip', subdir)
        _sort(subdir, 'alternateNames.txt', 'alternateNames.tsv', '-n', '-k', '2,3')


def download(subdir):
    """Download all resources to the specified subdirectory and unpack them."""
    _download(_FREE, subdir)


def download_premium(subdir, year, month):
    raise NotImplementedError('downloads from the premium dump not implemented yet')
