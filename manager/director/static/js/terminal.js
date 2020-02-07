$(document).ready(function() {
    $(window).resize(function() {
        $(".console-wrapper").trigger("terminal:resize");
    });
});

function setupTerminal(uri, wrapper, callbacks) {
    callbacks = callbacks || {};
    var titleCallback = callbacks.onTitle || function(title) {
        document.title = title;
    };

    var heartbeat_interval = 45 * 1000;

    var ws = null;
    var connected = false;
    var dataReceived = false;

    wrapper.empty().addClass("console-wrapper");

    var container = $("<div>").addClass("console-container").appendTo(wrapper);
    $("<div>").addClass("console-disconnect").appendTo(wrapper).append(
        "Disconnected ",
        $("<a>").addClass("console-reconnect").attr("href", "#").text("Reconnect").click(openWS),
    );

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
        container.empty().text("Connecting...");
        wrapper.removeClass("disconnected");

        connected = false;
        dataReceived = false;

        ws = new WebSocket(uri);
        ws.onopen = onOpen;
        ws.onmessage = onMessage;
        ws.onclose = onClose;
    }

    function onOpen() {
        connected = true;

        container.empty().text("Launching terminal...");
        wrapper.removeClass("disconnected");
    }

    function onMessage(e) {
        if(!dataReceived) {
            container.empty();
            wrapper.removeClass("disconnected");

            term.setOption("disableStdin", false);
            term.setOption("cursorBlink", true);

            term.open(container.get(0), true);
            fitAddon.fit();

            updateSize(term.rows, term.cols);
            setTimeout(function() {
                updateSize(term.rows, term.cols);
            }, 0);

            dataReceived = true;
        }

        var data = e.data;

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
        if(!dataReceived) {
            container.empty();
        }

        connected = false;
        dataReceived = false;

        term.setOption("disableStdin", true);
        term.setOption("cursorBlink", false);

        wrapper.focus();
        wrapper.addClass("disconnected");

        titleCallback("Terminal");
    }

    openWS();
}
