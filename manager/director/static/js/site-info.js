jQuery.fn.selectText = function() {
    var doc = document;
    var element = this[0];
    var range;
    if (doc.body.createTextRange) {
        range = document.body.createTextRange();
        range.moveToElementText(element);
        range.select();
    } else if (window.getSelection) {
        var selection = window.getSelection();
        range = document.createRange();
        range.selectNodeContents(element);
        selection.removeAllRanges();
        selection.addRange(range);
    }
};

$(function() {
    $("#database-url").click(function() {
        $("#database-pass").removeClass("hide");
    }).dblclick(function() {
        $(this).selectText();
    }).on("blur", function() {
        $("#database-pass").addClass("hide");
    });
});
