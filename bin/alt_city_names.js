// Alternate city name derivation
// Run as a separate pass because we need all cities to exist for our checking

load(SCRIPT_DIR + "/gns_common.js");

// Setup a barename blacklist (i.e. we don't save these barenames)
var barename_blacklist = {
    'lake': true,
    'lakes': true,
    'village': true,
    'pines': true,
    'reserve': true,
    'the park': true,
    'city': true,
    'come': true,
};

// Setup processNames function
var processNames = function(city) {

    var names_length = city.names.length;
    var match, barename, query, count;

    // X on|by (the) Y names should include the bare variants unless there's a clash
    if (city.countryCode.match(/^(US|GB|IE|AU|NZ|ZA)$/)) {
        if (match = city.name.match(/^(.*\S)[\s-](on|by)[\s-](the[\s-])?/i)) {
            barename = match[1].toLowerCase();

            // Ignore generic barenames
            if (! (barename in barename_blacklist) && ! city.name.match(/\bPark$/)) {
                print("+ " + city.name + " => " + barename);

                // Check whether a city with this barename already exists
                query = { 'names': barename, 'countryCode': city.countryCode };
                if (city.admin1) {
                    query['admin1'] = city.admin1;
                }
                count = db.cities.find(query).count();

                // If barename doesn't exist, add as an alternate name
                if (count == 0) {
                    print("+ " + barename + " not found in " + city.admin1 + ", " + city.countryCode + " - adding");
                    city.names.push(barename);
                }
            }
        }

        if (city.names.length > names_length) {
            city.names = uniquify(city.names);
            db.cities.save(city);
        }
    }
};

// Run processNames on all rows in cities
var cur = db.cities.find()
cur.immortal = true;
var j = 0;
cur.forEach(function(city) {
    processNames(city);
    if (j % 100000 === 0) {
        print(j + " cities processed");
    }
    j++;
});
print("Completed: " + j + " cities processed");
