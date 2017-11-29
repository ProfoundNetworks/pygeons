#!/bin/bash
#
# Prepare the downloaded files for import into MongoDB.
#
if [ -z "$1" ]
then
    echo "usage: bash $0 data_dir"
    exit 1
fi
DATA_DIR=$1


echo "Configuring paths ..."
if [ -z "$ROOT_PATH" ]; then
  ROOT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
  ROOT_PATH=$(dirname $ROOT_PATH)
fi

SCRIPT_DIR="$ROOT_PATH/bin"
export PYTHONPATH=$SCRIPT_DIR:$PYTHONPATH

echo "  ROOT_PATH: $ROOT_PATH"
echo "  DATA_DIR: $DATA_DIR"
echo "  SCRIPT_DIR: $SCRIPT_DIR"

for prog in pv jq python
do
    if [ -z `which $prog` ]
    then
        echo "$prog not found. Please install it and run this script again."
        exit 1
    fi
done

python "$SCRIPT_DIR/check_imports.py"
if [ $? -ne 0 ];
then
  echo "Some Python dependencies are missing.  Please install and try again."
  exit 1
fi

#
# Any errors encountered from now on will cause this script to terminate.
# http://stackoverflow.com/questions/4381618/exit-a-script-on-error
#
set -e
set -o pipefail
cd $DATA_DIR

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
    python $SCRIPT_DIR/split_by_cc.py adm1.json split/
fi

if [ ! -s adm2.json ]
then
    echo "creating adm2.json"
    pv allCountries.tsv | awk -F"\t" '$8 ~ /ADM2H?/' | \
    bash $SCRIPT_DIR/pipeline.sh | \
    python $SCRIPT_DIR/append_admin_names.py adm1.json --admin2 adm2.json | \
    jq --compact-output \
        '. + {"admin2names": .names} | del(.names)' > adm2.json
    python $SCRIPT_DIR/split_by_cc.py adm2.json split/
fi

if [ ! -s cities.json ]
then
    echo "creating cities.json"
    pv allCountries.tsv | awk -F"\t" '$7 == "P"' | \
    bash $SCRIPT_DIR/pipeline.sh | \
    python $SCRIPT_DIR/append_admin_names.py adm1.json --admin2 adm2.json > cities.json
    python $SCRIPT_DIR/split_by_cc.py cities.json split/
fi

if [ ! -s admd.json ]
then
    echo "creating admd.json"
    pv allCountries.tsv | awk -F"\t" '$8 ~ /ADMDH?/' | \
    bash $SCRIPT_DIR/pipeline.sh | \
    python $SCRIPT_DIR/append_admin_names.py adm1.json --admin2 adm2.json > admd.json
    python $SCRIPT_DIR/split_by_cc.py admd.json split/
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
    pv allCountriesPostcodes.txt | cut -s -f 1,2,3,4 | \
        $SCRIPT_DIR/tsv2json.py \
        --field-names countryCode postCode placeName adminName \
        --field-types str str str str > postcodes.json
    python $SCRIPT_DIR/split_by_cc.py postcodes.json split/
fi
