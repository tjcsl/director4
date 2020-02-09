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

    var ws = new ReconnectingWebSocket(
        location.toString().replace(/^http(s?):/, "ws$1:"),
        null,
        {
            debug: DEBUG,
            automaticOpen: true,
            reconnectInterval: 1000,
            maxReconnectInterval: 5000,
            reconnectDecay: 1.5,
            maxReconnectAttempts: null,
            timeoutInterval: 2000,
        }
    );

    ws.addEventListener("message", function(event) {
        var data = JSON.parse(event.data);

        if(data.site_info != null) {
            var info_elems = $(".site-info");
            info_elems.each(function() {
                var elem = $(this);

                var key = elem.data("key");

                var value = data.site_info;

                key.split(".").forEach(function(part) {
                    if(value != undefined) {
                        value = value[part];
                    }
                });

                if(value == undefined) {
                    return;
                }

                if(value instanceof Array) {
                    if(value.length) {
                        value = value.join(", ");
                    }
                    else {
                        value = null;
                    }
                }

                switch(elem.data("type")) {
                    case "link_blank":
                        elem.empty();

                        if(value == null) {
                            elem.text("None");
                        }
                        else {
                            $("<a>").attr({href: value, target: "_blank"}).text(value).appendTo(elem);
                        }
                        break;
                    default:
                        if(value == null) {
                            value = "None";
                        }
                        elem.empty().text(value);
                }
            });

            // Special cases
            if(data.site_info.database != null) {
                console.log("Exists")
                $("#database-url").attr("title", data.site_info.database.db_url);
                $("#database-info").css("display", "block");
                $("#no-database-info").css("display", "none");
            }
            else {
                console.log("Does not exist")
                $("#database-info").css("display", "none");
                $("#no-database-info").css("display", "block");
            }
        }
    });

    if(DEBUG) {
        window.ws = ws;
    }
});
