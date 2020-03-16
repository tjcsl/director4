var filesPane;

$(function() {
    var layout_config = {
        content: [{
            type: "row",
            content: [{
                type: "component",
                componentName: "files",
                width: 25,
                isClosable: false,
            }, {
                type: "column",
                content: [{
                    type: "stack",
                    isClosable: false,
                    content: [],
                }, {
                    type: "stack",
                    id: "terminals",
                    height: 30,
                    isClosable: false,
                    content: [{
                        type: "component",
                        componentName: "terminal",
                        isClosable: false,
                    }],
                }],
            }],
        }],
    };

    var layout = new GoldenLayout(layout_config, $("#editor-container"));


    layout.registerComponent("files", function(container, componentState) {
        filesPane = new FilesPane(
            container.getElement(),
            ws_endpoints.file_monitor,
            {
                openFile: function(fname) {
                    console.log(fname);
                },
            },
        );
    });

    layout.registerComponent("file", function(container, componentState) {
    });

    layout.registerComponent("terminal", function(container, componentState) {
        container.setTitle("<span class='fas fa-terminal'></span> Terminal");

        setupTerminal(
            ws_endpoints.terminal,
            container.getElement(),
            {
                autoFocus: false,
                onTitle: function(title) {
                    container.setTitle("<span class='fas fa-terminal'></span> " + escapeHTML(title));
                },
            },
        );
    });


    layout.init();
    $(window).resize(function() {
        layout.updateSize();
    });
});


// Utility functions that may be used by multiple parts

function escapeHTML(text) {
    return $("<div>").text(text).html();
}

function splitPath(path) {
    var lastSlashIndex = path.lastIndexOf("/");
    if(lastSlashIndex == -1) {
        return ["", path];
    }
    else {
        return [path.slice(0, lastSlashIndex), path.slice(lastSlashIndex + 1)];
    }
}

// These path functions are specifically intended for this use case.
// They are not at all generalizable.

function joinPaths(paths) {
    return paths.map((p) => rTrimChars(p, "/")).filter((s) => s).join("/");
}

function rTrimChars(s, chars) {
    while(s.length && chars.includes(s.slice(-1))) {
        s = s.slice(0, -1);
    }
    return s;
}

function makeModalDialog(options, callback) {
    var modal_div = $("<div>").addClass("modal").attr("role", "dialog");

    var modal_dialog = $("<div>").addClass("modal-dialog").appendTo(modal_div);
    var modal_content = $("<div>").addClass("modal-content").appendTo(modal_dialog);

    var modal_header = $("<div>").addClass("modal-header").appendTo(modal_content);

    $("<h5>").addClass("modal-title").css("line-height", 1.2).append(options.title || "").appendTo(modal_header);
    if(options.closebtn) {
        $("<button>")
            .attr({"type": "button"})
            .append($("<i>").addClass("fa fa-times"))
            .addClass("close")
            .appendTo(modal_header)
            .click(function() {
                modal_div.modal("hide");
                callback(null);
            });
    }

    if(options.body) {
        $("<div>").addClass("modal-body").append(options.body).appendTo(modal_content);
    }

    var modal_footer = $("<div>").addClass("modal-footer").appendTo(modal_content);
    options.buttons.forEach(function(btnSpec) {
        var btnClasses;
        if(btnSpec.btnType === undefined || btnSpec.btnType === true) {
            btnClasses = "btn btn-primary";
        }
        else if(btnSpec.btnType) {
            btnClasses = "btn btn-" + btnSpec.btnType;
        }

        $("<button>")
            .attr({"type": "button"})
            .text(btnSpec.label)
            .addClass(btnClasses)
            .addClass(btnSpec.classes || "")
            .css(btnSpec.styles || {})
            .appendTo(modal_footer)
            .click(function() {
                modal_div.modal("hide");
                callback(btnSpec.value);
            });
    });

    modal_div.modal({
        backdrop: true,
        keyboard: true,
        show: true,
    });

    modal_div.on("hidden.bs.modal", function() {
        modal_div.remove();
    });

    return modal_div;
}

function makeYesNoModalDialog(title, body, callback) {
    return makeModalDialog({
        closebtn: true,
        title: title,
        body: body,
        buttons: [
            {label: "No", value: false, btnType: "secondary"},
            {label: "Yes", value: true, btnType: "primary"},
        ],
    }, callback);
}

function makeOkCancelModalDialog(title, body, callback) {
    return makeModalDialog({
        closebtn: true,
        title: title,
        body: body,
        buttons: [
            {label: "Cancel", value: false, btnType: "secondary"},
            {label: "Ok", value: true, btnType: "primary"},
        ],
    }, callback);
}

function makeEntryModalDialog(title, body, initialVal, callback) {
    var text_input = $("<input>").attr("type", "text").addClass("modal-prompt form-control").val(initialVal);

    text_input.on("keypress", function(e) {
        if (e.which == 13) {
            modal_div.modal("hide");
            callback(text_input.val());
        }
    });

    var modal_div = makeOkCancelModalDialog(
        title,
        [...body, text_input],
        function(btnRes) {
            callback(btnRes ? text_input.val() : null);
        },
    );

    text_input.focus();

    return modal_div;
}
