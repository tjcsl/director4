function setupSQLConsole(uri, wrapper) {
    var output_pre = wrapper.find(".output");
    var input_container_div = wrapper.find(".input-container");
    var prompt_div = wrapper.find(".prompt");
    var sql_input = wrapper.find(".input");

    var history = [];
    // A value < 0 indicates that the "current"
    var historyIndex = -1;
    // The line the user was editing before they began scrolling back through the history.
    var prevLine = "";

    function moveInputCursorToEnd() {
        var length = sql_input.val().length;

        // This is one of those weird JS things that doesn't work unless you do it in a timeout
        setTimeout(function() {
            sql_input[0].setSelectionRange(length, length);
        }, 0);
    }

    sql_input.keydown(function(e) {
        if(e.keyCode == 13) {  // Return
            e.preventDefault();

            var sql = sql_input.val();

            if(history[history.length - 1] != sql) {
                history.push(sql);
            }
            historyIndex = -1;
            prevLine = "";

            output_pre.append($("<div>").text(prompt_div.text() + sql));
            sql_input.val("");

            input_container_div.hide();

            $.post(
                uri,
                {"sql": sql},
            ).done(function(data) {
                output_pre.append($("<div>").text(data));
            }).fail(function() {
                output_pre.append($("<div>").css("color", "#cc0000").text("Server Error"),);
            }).always(function() {
                input_container_div.show();
                sql_input.focus();
            });
        }
        else if(e.keyCode == 38) {  // Up Arrow
            if(historyIndex < 0) {
                // Only try to scroll up if there's some history
                if(history.length) {
                    prevLine = sql_input.val();
                    historyIndex = history.length - 1;
                    sql_input.val(history[historyIndex]);
                    moveInputCursorToEnd();
                }
            }
            else if(historyIndex == 0) {
                // Start of history; nothing to show
            }
            else {
                sql_input.val(history[--historyIndex]);
                moveInputCursorToEnd();
            }
        }
        else if(e.keyCode == 40) {  // Down Arrow
            // If historyIndex < 0, we're at the end and we can't scroll down anymore
            if(historyIndex >= 0) {
                var newLine;
                if(historyIndex == history.length - 1) {
                    // End of history; restore the previous line
                    newLine = prevLine;
                    historyIndex = -1;
                }
                else {
                    newLine = history[++historyIndex];
                }

                sql_input.val(newLine);
                moveInputCursorToEnd();
            }
        }
    });
}
