print("Building indices on admin1 collection");
db.admin1.ensureIndex({admin1id: 1});
db.admin1.ensureIndex({admin1names: 1});
db.admin1.ensureIndex({abbr: 1});
db.admin1.ensureIndex({names_lang: 1});

print("Building indices on admin2 collection");
db.admin2.ensureIndex({admin2id: 1});
db.admin2.ensureIndex({admin2names: 1});
db.admin2.ensureIndex({abbr: 1});
db.admin2.ensureIndex({names_lang: 1});

print("Building indices on postcodes collection");
db.postcodes.ensureIndex({postCode: 1});
db.postcodes.ensureIndex({placeName: 1});

function processCollection(coll) {
    print("Building indices on " + coll);
    coll.ensureIndex({countryCode: 1, names: 1});
    coll.ensureIndex({names: 1});
    coll.ensureIndex({countryCode: 1, admin1names: 1});
    coll.ensureIndex({admin1names: 1});
    coll.ensureIndex({countryCode: 1, admin2names : 1});
    coll.ensureIndex({admin2names: 1});
    coll.ensureIndex({abbr: 1});
    coll.ensureIndex({names_lang: 1});
}

//
// These two collections are in the same format so we may as well handle
// them together.
//
processCollection(db.cities);
processCollection(db.admind);

db.countries.ensureIndex({names: 1});
