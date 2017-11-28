#!/bin/bash
#
# Download and unpack the required packages from geonames.org
#
# If you use the premium geonames dump, run bin/geonames_login.sh first.
# If you change this, remove the data subdirectory to flush the cached data.
#
if [ -z "$1" ]
then
    echo "usage: bash $0 data_dir"
    exit 1
fi
DATA_DIR=$1

USE_PREMIUM_GEONAMES=0

#
# This is only relevant when using the premium geonames dump.
# The free dump is not versioned, and only the most recent dump is available.
#
DATASET=$1
if [ -z "$DATASET" ]; then
  DATASET=$(date +%Y%m)
fi

GEONAMES_FREE_URL=http://download.geonames.org/export/dump
GEONAMES_PREMIUM_URL=http://www.geonames.org/premiumdump/$DATASET

if [ $USE_PREMIUM_GEONAMES -eq 1 ]
then
    GEONAMES_URL=$GEONAMES_PREMIUM_URL
else
    GEONAMES_URL=$GEONAMES_FREE_URL
fi

echo "  DATA_DIR: $DATA_DIR"
echo "  GEONAMES_URL: $GEONAMES_URL"

echo "Checking dependencies ..."

for prog in get unzip
do
    if [ -z `which $prog` ]
    then
        echo "$prog not found. Please install it and run this script again."
        exit 1
    fi
done

if [ ! -d $DATA_DIR ]; then
    mkdir -p $DATA_DIR || exit 3
fi

echo "Start fetching Geonames resources ..."
cd $DATA_DIR || exit 1

function safe_wget() {
    #
    # Calls wget.
    # If downloading premium data, checks that the cookie file is there first.
    # This is required because wget returns 0 even if it doesn't find the
    # cookies. Then, authenticates the wget requests with cookies if
    # downloading premium data.
    #
    echo "safe_wget: downloading $@"
    if [[ $USE_PREMIUM_GEONAMES -eq 1 && ! -f "$ROOT_PATH/cookies.txt" ]]
    then
        echo "$ROOT_PATH/cookies.txt not found, run bin/geonames_login.sh "
        exit 1
    elif [ $USE_PREMIUM_GEONAMES -eq 1 ]
    then
        wget --load-cookies "$ROOT_PATH/cookies.txt" $@
    else
        wget $@
    fi
}

if [ ! -s allCountries.zip ]
then
    safe_wget $GEONAMES_URL/allCountries.zip
    #
    # If our login token expires, the wget "succeeds" but fetches a HTML page
    # saying "please log in" instead. Check that we've actually downloaded a
    # zip, and bail if we haven't.
    #
    unzip -l allCountries.zip 2> /dev/null
    if [ $? -ne 0 ]
    then
        echo "stale cookies, run bin/geonames_login.sh"
        rm allCountries.zip
        exit 1
    fi
fi

#
# Any errors encountered from now on will cause this script to terminate.
# http://stackoverflow.com/questions/4381618/exit-a-script-on-error
#
set -e
set -o pipefail

if [ ! -s countryInfo.txt ]
then
    safe_wget $GEONAMES_URL/countryInfo.txt
fi

if [ ! -s allCountriesPostcodes.zip ]
then
    #
    # Postcode data is only available from the free dump.
    #
    echo "Downloading allCountriesPostcodes.zip"
    wget $GEONAMES_FREE_URL/../zip/allCountries.zip -O allCountriesPostcodes.zip
fi

if [ ! -s alternateNames.zip ]
then
    safe_wget $GEONAMES_URL/alternateNames.zip
fi

if [ ! -s countryInfo.txt ];then
    wget $GEONAMES_URL/countryInfo.txt
fi


echo "Start unpacking Geonames resources ..."

if [ ! -s allCountries.tsv ];then
    echo "Extracting allCountries.zip"
    unzip -o allCountries.zip
    #
    # append_alternate_names.py depends on this being sorted by geoid.
    #
    pv allCountries.txt | sort -n -k 1,2 > allCountries.tsv
fi

if [ ! -s alternateNames.tsv ]
then
    echo "Extracting alternateNames.zip"
    unzip -o alternateNames.zip
    #
    # append_alternate_names.py depends on this being sorted by geoid.
    #
    pv alternateNames.txt | sort -n -k 2,3 > alternateNames.tsv
fi

if [ ! -s allCountriesPostcodes.txt ]
then
    echo "Extracting allCountriesPostcodes.zip"
    unzip -o -p allCountriesPostcodes.zip > allCountriesPostcodes.txt
fi
