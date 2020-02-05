$(document).ready(function() {
    $(window).resize(function() {
        $(".console-wrapper").trigger("terminal:resize");
    });
});

function setupTerminal(uri, wrapper, callbacks) {
    callbacks = callbacks || callbacks;
    var titleCallback = callbacks.onTitle || function(title) {
        document.title = title;
    };

    var heartbeat_interval = 2 * 60 * 60 * 1000;

    var ws = null;
    var connected = false;
    var dataReceived = false;

    var container = wrapper.find(".console-container");
    var message_div = wrapper.find(".console-messages");

    var term = new Terminal({ cursorBlink: true });
    var fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    fitAddon.fit();

    term.onData(function(data) {
        if(ws != null && connected && dataReceived) {
            ws.send(new Blob([data]));
        }
    });
    term.onResize(function(size) {
        updateSize(size.rows, size.cols);
    });

    wrapper.on("terminal:resize", function(e) {
        e.preventDefault();
        e.stopPropagation();
        if(connected && dataReceived) {
            fitAddon.fit();
        }
    });

    function updateSize(rows, cols) {
        if(ws != null && connected && dataReceived) {
            ws.send(JSON.stringify({"size": [rows, cols]}));
        }
    }

    function openWS() {
        container.empty().css("display", "none");
        message_div.text("Connecting...");

        connected = false;
        dataReceived = false;

        ws = new WebSocket(uri);
        ws.onopen = onOpen;
        ws.onmessage = onMessage;
        ws.onclose = onClose;
    }

    function onOpen() {
        connected = true;

        container.empty().css("display", "none");
        message_div.text("Launching terminal...");
    }

    function onMessage(e) {
        if(!dataReceived) {
            container.css("display", "");
            container.removeClass("disconnected");
            message_div.empty();
            container.empty();

            term.setOption("disableStdin", false);
            term.setOption("cursorBlink", true);

            term.open(container.get(0), true);
            fitAddon.fit();
            updateSize(term.rows, term.cols);

            dataReceived = true;
        }

        var data = e.data;

        console.log(data);

        if(data instanceof Blob) {
            data.text().then((text) => {
                term.write(text);
            });
        }
        else if(data instanceof ArrayBuffer) {
            term.write(new Uint8Array(data));
        }
        else {
            var data = JSON.parse(data);
            if(data.heartbeat != null) {
                // A reply to our heartbeat message; ignore
            }
        }
    }

    setInterval(function() {
        if(ws != null && connected && dataReceived) {
            ws.send(JSON.stringify({"heartbeat": 1}));
        }
    }, heartbeat_interval);

    function onClose() {
        connected = false;
        dataReceived = false;

        term.setOption("disableStdin", true);
        term.setOption("cursorBlink", false);

        wrapper.focus();
        container.addClass("disconnected");
        $("<div>").css({position: "absolute", color: "red", bottom: "10px", right: "10px", backgroundColor: "rgba(0, 0, 0, 0.8)"}).text("Disconnected").appendTo(message_div);

        titleCallback("Terminal");
    }

    openWS();
}
