$(function() {
    console.log("a");
    var sock = new ReconnectingWebSocket(
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

    sock.addEventListener("message", function(event) {
        data = JSON.parse(event.data);

        console.log(data);
    });

    if(DEBUG) {
        window.sock = sock;
    }
});
