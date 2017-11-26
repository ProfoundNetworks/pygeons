//
// If the element is not part of the array, add it and return true.
// Returns false if the element is null or does not exist.
//
function addIfAbsent(array, newElt) {
    newElt = String(newElt);
    if (newElt == "null") {
        return false;
    }
    if (array.indexOf(newElt) === -1) {
        array.push(newElt);
        return true;
    }
    return false;
}


function uniquify(array) {
    return array.filter(function(elem, pos, self) {
        return self.indexOf(elem) == pos;
    });
}

module.exports = {
    uniquify: uniquify,
}
