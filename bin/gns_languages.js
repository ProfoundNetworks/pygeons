load(SCRIPT_DIR + "/gns_common.js");


function index(cursor) {
    var result = {};
    cursor.forEach(function (p) { result[p._id] = p; });
    return result;
}


function processCountry(countryCode, languageCode) {
    var languageCountries = index(db.countries.find({"iso": countryCode}));
    var query = {"countryCode": countryCode};
    var languageAdmin1 = index(db.admin1.find(query));
    var languageAdmin2 = index(db.admin2.find(query));
    var languageAdminD = index(db.admind.find(query));
    var languageCities = index(db.cities.find(query));

    var lang = languageCode.toLowerCase();

    print("processCountry " + countryCode + " " + languageCode);

    db.alternativeNames.find({"lang": lang}).forEach(function (altName) {
        var gid = altName["geonameid"];
        var name = altName["name"].toLowerCase();
        var place;
        var collection;
        if (gid in languageCities) {
            place = languageCities[gid];
            collection = db.cities;
        } else if (gid in languageAdminD) {
            place = languageAdminD[gid];
            collection = db.admind;
        } else if (gid in languageAdmin2) {
            place = languageAdmin2[gid];
            collection = db.admin2;
        } else if (gid in languageAdmin1) {
            place = languageAdmin1[gid];
            collection = db.admin1;
        } else {
            place = languageCountries[gid];
            collection = db.countries;
        }
        if (place && collection) {
            if (!(languageCode in place.names_lang)) {
                place.names_lang[languageCode] = [];
            }
            if (place.names_lang[languageCode].indexOf(name) === -1) {
                place.names_lang[languageCode].push(name);
                collection.save(place);
            }
        }
    });
};

function processLanguage(lang) {
    print("adding indices for language: " +  lang);
    var key = "names_lang." + lang;
    var param = {};
    param[key] = 1;
    db.admin1.ensureIndex(param);
    db.admin2.ensureIndex(param);
    db.admind.ensureIndex(param);
    db.cities.ensureIndex(param);
    db.countries.ensureIndex(param);
}

processCountry(COUNTRY, LANGUAGE);
processLanguage(LANGUAGE);
