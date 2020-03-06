$(function() {
    $("#database-url").click(function() {
        $("#database-pass").removeClass("hide");
    }).dblclick(function() {
        $(this).selectText();
    }).on("blur", function() {
        $("#database-pass").addClass("hide");
    });

    var site_ids = [];
    $(".site-dynamic.user-site").each(function() {
        site_ids.push($(this).data("site-id"));
    });

    var ws = new ReconnectingWebSocket(
        location.protocol.toString().replace(/^http/, "ws") + "//" + location.host + "/sites/multi-status/?site_ids=" + site_ids.join(","),
        null,
        {
            debug: DEBUG,
            automaticOpen: true,
            reconnectInterval: 3000,
            maxReconnectInterval: 10000,
            reconnectDecay: 3,
            maxReconnectAttempts: null,
            timeoutInterval: 2000,
        }
    );

    var delayedOperationId = null;
    ws.addEventListener("message", function(event) {
        var data = JSON.parse(event.data);

        var site_id = data.site_id;
        var addClasses = [];
        var removeClasses = [];
        if(data.status.starting) {
            addClasses = ["status-yellow"];
            removeClasses = ["status-red", "status-green"];
        }
        else if(data.status.running) {
            addClasses = ["status-green"];
            removeClasses = ["status-red", "status-yellow"];
        }
        else {
            addClasses = ["status-red"];
            removeClasses = ["status-green", "status-yellow"];
        }

        $("#site-" + site_id).find("span.site-status").addClass(addClasses.join(" "));
        $("#site-" + site_id).find("span.site-status").removeClass(removeClasses.join(" "));
    });
});
