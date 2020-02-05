$(document).ready(function() {
    $(window).resize(function() {
        $(".console-wrapper").trigger("terminal:resize");
    });
});
var registerTerminal = function (uri, wrapper, auth, options) {
    options = options || {};
    var titleCallback = options.onTitle || function(title) {
        document.title = title;
    };
    var disconnectCallback = options.onClose || function() { };
    var loadCallback = options.onStart || function() { };

    var tconsole = wrapper.find(".console");
    var disconnect = wrapper.find(".disconnect");
    var started = false;
    var ws = new WebSocket(uri);
    ws.onopen = function() {
        tconsole.empty().removeClass("disconnected");
        disconnect.hide();

        var term = new Terminal({ cursorBlink: true });
        fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);
        fitAddon.fit();

        function updateSize(rows, cols) {
            ws.send(JSON.stringify({"size": [rows, cols]}));
        }

        term.onData(function(data) {
            if (started) {
                ws.send(new Blob([data]));
            }
        });
        term.onResize(function(size) {
            updateSize(size.rows, size.cols);
        });
        term.onTitleChange(function(title) {
            titleCallback(title);
        });
        ws.send(JSON.stringify(auth));
        ws.onmessage = function(e) {
            if(!started) {
                started = true;
                term.open(tconsole[0], true);
                
                loadCallback(term);

                fitAddon.fit();
                updateSize(term.rows, term.cols);
            }

            if (e.data instanceof Blob) {
                e.data.text().then((text) => {
                    term.write(text);
                });
            }
            else if (e.data instanceof ArrayBuffer) {
                term.write(new Uint8Array(e.data));
            }
            else {
                var data = JSON.parse(e.data);
                if (data.error) {
                    tconsole.append("<div style='color:red'>Error: " + $("<div />").text(data.error).html() + "</div>");
                }
            }
        };
        ws.onclose = function() {
            var cache = tconsole.html();
            try {
                term.destroy();
            }
            catch (e) {
                // Fail silently
            }
            finally {
                wrapper.off("resize");
                tconsole.html(cache).addClass("disconnected");
                started = false;
                wrapper.focus();
                disconnect.show();
                titleCallback("Terminal");
                disconnectCallback();
            }
        };
        wrapper.find(".terminal .xterm-viewport, .terminal .xterm-rows").css("line-height", "19px");
        wrapper.on("terminal:resize", function(e) {
            e.preventDefault();
            e.stopPropagation();
            if (started) {
                fitAddon.fit();
            }
        });
    };
};
