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
            maxReconnectInterval: 10000,
            reconnectDecay: 3,
            maxReconnectAttempts: null,
            timeoutInterval: 2000,
        }
    );

    var delayedOperationId = null;
    ws.addEventListener("message", function(event) {
        var data = JSON.parse(event.data);

        if(data.site_info !== undefined) {
            if(delayedOperationId != null) {
                clearTimeout(delayedOperationId);
                delayedOperationId = null;
            }

            if(data.site_info === null) {
                if($("#site-deleted-modal").length) {
                    return;
                }

                var modal_div = $("<div>").addClass("modal").attr("role", "dialog").attr("id", "site-deleted-modal");

                var modal_dialog = $("<div>").addClass("modal-dialog").appendTo(modal_div);
                var modal_content = $("<div>").addClass("modal-content").appendTo(modal_dialog);

                var modal_header = $("<div>").addClass("modal-header").appendTo(modal_content);

                $("<h5>").addClass("modal-title").text("Site deleted").appendTo(modal_header);
                $("<button>").attr(
                    {"type": "button", "class": "close", "data-dismiss": "modal"}
                ).append(
                    $("<i>").addClass("fa fa-times")
                ).appendTo(modal_header);

                $("<div>").addClass("modal-body").append(
                    "This site has been deleted. Please return to the ",
                    $("<a>").attr({href: "/"}).text("home page"),
                    "."
                ).appendTo(modal_content);

                modal_div.modal({
                    backdrop: true,
                    keyboard: false,
                    show: true,
                });

                ws.close();

                return;
            }

            var info_elems = $(".site-info");
            info_elems.each(function() {
                var elem = $(this);

                var key = elem.data("key");

                var value = data.site_info;

                key.split(".").forEach(function(part) {
                    if(value === null || value === undefined) {
                        // Trying to take an attribute of null; abort when we exit this loop
                        value = undefined;
                    }
                    else {
                        value = value[part];
                    }
                });

                if(value === undefined) {
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
                $("#database-url").attr("title", data.site_info.database.db_url);
                $("#database-info").css("display", "block");
                $("#no-database-info").css("display", "none");
            }
            else {
                $("#database-info").css("display", "none");
                $("#no-database-info").css("display", "block");
            }

            $(".nav-site-name").text(data.site_info.name);
            $("title").text(DIRECTOR_APPLICATION_NAME + " - " + data.site_info.name);

            if(data.site_info.type == "static") {
                $(".site-status-container").hide();
            }
            else {
                $(".site-status-container").show();
            }

            if(data.site_info.is_being_served) {
                $("#not-served-notify").css("display", "none");
            }
            else {
                $("#not-served-notify").css("display", "block");
            }

            var operation_div = $("#operation-info");
            if(data.site_info.operation != null) {
                operation_div.empty();

                $("<h6>").text("Ongoing operation").appendTo(operation_div);

                if(data.site_info.operation.started_time != null) {
                    var actions_container = $("<ul>").addClass("actions").appendTo(operation_div);

                    data.site_info.operation.actions.forEach(function(action) {
                        var action_elem = $("<li>").addClass("action").text(action.name).appendTo(actions_container);
                        if(action.result == true) {
                            action_elem.addClass("succeeded")
                        }
                        else if(action.result == false) {
                            action_elem.addClass("failed")
                        }
                        else if(action.started_time != null) {
                            action_elem.addClass("started")
                        }
                        else {
                            action_elem.addClass("pending")
                        }
                    });
                }
                else {
                    $("<p>").css({fontStyle: "italic", fontSize: "80%", marginLeft: "2em"}).text("Pending").appendTo(operation_div);
                }
            }
            else {
                if(operation_div.children().length) {
                    operation_div.find(".actions, p").empty();
                    $("<p>").css({fontStyle: "italic", fontSize: "80%", marginLeft: "2em"}).text("Completed").appendTo(operation_div);

                    delayedOperationId = setTimeout(function() {
                        operation_div.empty();
                        delayedOperationId = null;
                    }, 1000);
                }
                else {
                    operation_div.empty();
                }
            }
        }
        else if(data.site_status !== undefined) {
            var start_time = new Date(data.site_status.start_time);

            var status_text;
            if(data.site_status.running) {
                if(data.site_status.starting) {
                    status_text = "Shutting down";
                }
                else {
                    status_text = "Running since "
                        + (start_time.getHours() % 12 == 0 ? 12 : start_time.getHours() % 12) + ":" + start_time.getMinutes().toString().padStart(2, "0") + ":" + start_time.getSeconds().toString().padStart(2, "0") + " " + (start_time.getHours() < 12 ? "AM" : "PM")
                        + " on " + (start_time.getMonth() + 1) + "/" + start_time.getDate() + "/" + start_time.getFullYear();
                }
            }
            else {
                if(data.site_status.starting) {
                    status_text = "Starting";
                }
                else {
                    status_text = "Stopped";
                }
            }

            $(".site-status").text(status_text);
        }
        else if(data.failed_operation_recoverable !== undefined) {
            if($("#site-failed-operation-modal.show").length) {
                return;
            }

            var operation_type = data.failed_operation_recoverable;
            var msg;

            switch(operation_type) {
                case "update_docker_image":
                    msg = [
                        "The Docker image has failed to build. This is usually due to incorrect package names (though there may be other causes).",
                        $("<br>"),
                        "Please go to ",
                        $("<a>").attr("href", "image/select").text("the image selection page"),
                        " and try again.",
                    ];
                    break;
                default:
                    msg = "An operation on your site has failed, but you can recover from it. Try navigating back to the last page you were on and repeating what you were trying to do.";
            }

            var modal_div = $("<div>").addClass("modal").attr("role", "dialog").attr("id", "site-failed-operation-modal");

            var modal_dialog = $("<div>").addClass("modal-dialog").appendTo(modal_div);
            var modal_content = $("<div>").addClass("modal-content").appendTo(modal_dialog);

            var modal_header = $("<div>").addClass("modal-header").appendTo(modal_content);

            $("<h5>").addClass("modal-title").text("Recovering from failed operation").appendTo(modal_header);
            $("<button>").attr(
                {"type": "button", "class": "close", "data-dismiss": "modal"}
            ).append(
                $("<i>").addClass("fa fa-times")
            ).appendTo(modal_header);

            $("<div>").addClass("modal-body").append(msg).appendTo(modal_content);

            modal_div.modal({
                backdrop: true,
                keyboard: false,
                show: true,
            });
        }
    });

    $(window).on("beforeunload", function() {
        // We don't want to update the page live if we're navigating away
        // This does weird stuff with the operation info div especially
        ws.close();
    });

    if(DEBUG) {
        window.ws = ws;
    }
});
