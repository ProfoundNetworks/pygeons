#!/bin/bash
# Import the processed files into MongoDB.
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

MONGO_DB=geonames
SCRIPT_DIR="$ROOT_PATH/bin"
export PYTHONPATH=$SCRIPT_DIR:$PYTHONPATH

echo "  ROOT_PATH: $ROOT_PATH"
echo "  DATA_DIR: $DATA_DIR"
echo "  SCRIPT_DIR: $SCRIPT_DIR"

for prog in mongo pv
do
    if [ -z `which $prog` ]
    then
        echo "$prog not found. Please install it and run this script again."
        exit 1
    fi
done

echo "Testing mongo connection ..."
mongo --eval "printjson(db.adminCommand('listDatabases'))" > /dev/null
if [ $? -eq 1 ]
then
    echo "Cannot connect to mongo ..."
    exit 1;
fi

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
