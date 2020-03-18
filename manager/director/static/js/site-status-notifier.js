$(function() {
    var ws = new ReconnectingWebSocket(
        location.protocol.replace("http", "ws") + "//" + location.host + location.pathname.replace(/^(\/sites\/\d+)\b.*$/, "$1/"),
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


    var messenger = Messenger();
    var message = null;

    var is_first_message;
    var lastMsg = null;
    ws.addEventListener("open", function(event) {
        is_first_message = true;
    });

    ws.addEventListener("message", function(event) {
        var data = JSON.parse(event.data);

        if(data.site_status !== undefined) {
            var start_time = new Date(data.site_status.start_time);

            var msg = null;
            if(data.site_status.running) {
                if(data.site_status.starting) {
                    msg = {
                        message: "Site process shutting down...",
                        type: "info",
                        hideAfter: false,
                        showCloseButton: false,
                    };
                }
                else {
                    if(!is_first_message) {
                        msg = {
                            message: "Site process restarted!",
                            type: "success",
                            hideAfter: 5,
                            showCloseButton: true,
                        };
                    }
                }
            }
            else {
                if(data.site_status.starting) {
                    msg = {
                        message: "Site process starting...",
                        type: "info",
                        hideAfter: false,
                        showCloseButton: false,
                    };
                }
                else {
                    msg = {
                        message: "Site process stopped",
                        type: "error",
                        hideAfter: 5,
                        showCloseButton: true,
                    };
                }
            }

            if(msg != null && (!lastMsg || msg.message != lastMsg.message)) {
                lastMsg = msg;
                if(message == null) {
                    message = messenger.post(msg);
                }
                else {
                    message = message.update(msg);
                }
            }

            is_first_message = false;
        }
    });
});
