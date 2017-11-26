#!/bin/bash

#
# If you use the premium geonames dump, run bin/geonames_login.sh first.
# If you change this, remove the data subdirectory to flush the cached data.
#
USE_PREMIUM_GEONAMES=0

#
# This is only relevant when using the premium geonames dump.
# The free dump is not versioned, and only the most recent dump is available.
#
DATASET=$1
if [ -z "$DATASET" ]; then
  DATASET=$(date +%Y%m)
fi

echo "Checking dependencies ..."

for prog in mongo pv jq unzip python
do
    if [ -z `which $prog` ]
    then
        echo "$prog not found. Please install it and run this script again."
        exit 1
    fi
done

echo "Configuring paths ..."
if [ -z "$ROOT_PATH" ]; then
  ROOT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
  ROOT_PATH=$(dirname $ROOT_PATH)
fi

MONGO_DB=geonames
CONFIG_DIR="$ROOT_PATH/conf"
DATA_DIR="$ROOT_PATH/data/$DATASET"
SCRIPT_DIR="$ROOT_PATH/bin"
export PYTHONPATH=$SCRIPT_DIR:$PYTHONPATH

python "$SCRIPT_DIR/check_imports.py"
if [ $? -ne 0 ];
then
  echo "Some Python dependencies are missing.  Please install and try again."
  exit 1
fi

GEONAMES_FREE_URL=http://download.geonames.org/export/dump
GEONAMES_PREMIUM_URL=http://www.geonames.org/premiumdump/$DATASET

if [ $USE_PREMIUM_GEONAMES -eq 1 ]
then
    GEONAMES_URL=$GEONAMES_PREMIUM_URL
else
    GEONAMES_URL=$GEONAMES_FREE_URL
fi

echo "  GEONAMES_URL: $GEONAMES_URL"
echo "  ROOT_PATH: $ROOT_PATH"
echo "  CONFIG_DIR: $CONFIG_DIR"
echo "  DATA_DIR: $DATA_DIR"
echo "  SCRIPT_DIR: $SCRIPT_DIR"

if [ ! -d $DATA_DIR ]; then
    mkdir -p $DATA_DIR || exit 3
fi

echo "Testing mongo connection ..."
mongo --eval "printjson(db.adminCommand('listDatabases'))" > /dev/null
if [ $? -eq 1 ]; then
    echo "Cannot connect to mongo ..."
    exit 1;
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

if [ ! -s allCountries.zip ];then
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

if [ ! -s countries.json ]
then
    echo "generating countries.json"
    pv countryInfo.txt | sort -n -k 17,18 -t$'\t' | sed "/^#/d" | \
        python $SCRIPT_DIR/tsv2json.py \
            --field-names iso iso3 iso-numeric fips name capital area \
                population continent tld currencycode currencyname phone \
                postalcodeformat postalcoderegex languages _id \
                neighbours equivalentfipscode \
            --field-types str str skip str str str skip int skip str skip \
                skip skip skip skip str int skip skip |
        jq --compact-output --unbuffered 'select(._id != null)' > countries.json
fi

if [ ! -s adm1.json ]
then
    echo "creating adm1.json"
    pv allCountries.tsv | awk -F"\t" '$8 ~ /ADM1H?/' | \
    bash $SCRIPT_DIR/pipeline.sh | \
    jq --compact-output \
        '. + {"admin1names": .names} | del(.names)' > adm1.json
fi

if [ ! -s adm2.json ]
then
    echo "creating adm2.json"
    pv allCountries.tsv | awk -F"\t" '$8 ~ /ADM2H?/' | \
    bash $SCRIPT_DIR/pipeline.sh | \
    python $SCRIPT_DIR/append_admin_names.py adm1.json --admin2 adm2.json | \
    jq --compact-output \
        '. + {"admin2names": .names} | del(.names)' > adm2.json
fi

if [ ! -s cities.json ]
then
    echo "creating cities.json"
    pv allCountries.tsv | awk -F"\t" '$7 == "P"' | \
    bash $SCRIPT_DIR/pipeline.sh | \
    python $SCRIPT_DIR/append_admin_names.py adm1.json --admin2 adm2.json > cities.json
fi

if [ ! -s admd.json ]
then
    echo "creating admd.json"
    pv allCountries.tsv | awk -F"\t" '$8 ~ /ADMDH?/' | \
    bash $SCRIPT_DIR/pipeline.sh | \
    python $SCRIPT_DIR/append_admin_names.py adm1.json --admin2 adm2.json > admd.json
fi

if [ ! -s countries-final.json ]
then
    echo "generating countries-final.json"
    pv countries.json | sed "/^#/d" | \
        python $SCRIPT_DIR/append_alternatenames.py \
            --format countryInfo \
            alternateNames.tsv countries.json > countries-final.json
fi

if [ ! -s postcodes.json ]
then
    echo "generating postcodes.json"
    pv allCountriesPostcodes.txt | cut --only-delimited --fields=1,2,3,4 | \
        $SCRIPT_DIR/tsv2json.py \
        --field-names countryCode postCode placeName adminName \
        --field-types str str str str > postcodes.json
fi

echo "Importing adm1.json"
mongoimport -d $MONGO_DB -c admin1 --drop --stopOnError adm1.json

echo "Importing adm2.json"
mongoimport -d $MONGO_DB -c admin2 --drop --stopOnError adm2.json

echo "Importing admd.json"
mongoimport -d $MONGO_DB -c admind --drop --stopOnError admd.json

echo "Importing cities.json"
mongoimport -d $MONGO_DB -c cities --drop --stopOnError cities.json

echo "Importing postcodes.json"
mongoimport -d $MONGO_DB -c postcodes --drop --stopOnError postcodes.json

echo "Importing countries-final.json"
mongoimport -d $MONGO_DB -c countries --drop --stopOnError countries-final.json


function runmongo() {
    #
    # Runs mongo with SCRIPT_DIR variable set. Enables reusing JS scripts.
    #
    mongo --eval "var SCRIPT_DIR='$SCRIPT_DIR'" $@
}

runmongo $MONGO_DB "$SCRIPT_DIR/gns_indices.js"
runmongo $MONGO_DB "$SCRIPT_DIR/alt_city_names.js"

echo "Running country-specific scripts"
runmongo $MONGO_DB "$SCRIPT_DIR/gns_gb.js"
runmongo $MONGO_DB "$SCRIPT_DIR/gns_ie.js"
runmongo $MONGO_DB "$SCRIPT_DIR/gns_ru.js"

#
# version may be used in filenames, so avoid using colon character in
# timestamp
#
version=$(date "+%Y.%m.%d-%H.%M.%S")
mongo $MONGO_DB --eval "db.util.drop(); db.util.insert({name: 'version', value: '$version'})"

echo "All done!"
