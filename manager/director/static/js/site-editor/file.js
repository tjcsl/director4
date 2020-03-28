function FileEditor(layoutContainer, load_endpoint, save_endpoint, fname) {
    var self = this;

    var modelist = ace.require("ace/ext/modelist");

    var containerElem = layoutContainer.getElement();

    var currentStatus;
    function updateTitle(fileStatus) {
        var prefixClasses;
        if(fileStatus == "loading" || fileStatus == "saving") {
            // These icons have some CSS animations that make them spin.
            // Let's change the icon to a circle with a notch to aid
            // the visual cue.
            prefixClasses = "file-title-icon fas fa-circle-notch file-" + fileStatus;
        }
        else {
            prefixClasses = "file-title-icon far fa-circle file-" + fileStatus;
        }

        currentStatus = fileStatus;
        layoutContainer.setTitle("<span class='" + prefixClasses + "'></span> " + escapeHTML(splitPath(fname)[1]));
    }

    function saveFile() {
        updateTitle("saving");

        $.post({
            url: save_endpoint + "?" + $.param({
                path: fname,
            }),
            data: {
                contents: editor.getSession().getValue().replace(/\r/g, ""),
            },
            processData: true,
            contentType: "application/x-www-form-urlencoded",
        }).then(function(data) {
            updateTitle("saved");
        }).fail(function(data) {
            updateTitle("unsaved");
            Messenger().error({
                message: "Error saving file: " + (data.responseText || "Unknown error"),
            });
        });
    }

    updateTitle("loading");

    var editor = null;
    var session = null;

    $.get({
        url: load_endpoint + "?" + $.param({path: fname}),
        dataType: "text",
    }).then(function(data) {
        // We have to insert a new element. If we try to run ace.edit() on the container itself, the styles
        // conflict and it breaks Ace's themes.
        editor = ace.edit($("<div>").css({"width": "100%", "height": "100%"}).appendTo(containerElem).get(0));

        session = ace.createEditSession(data);
        session.setMode(modelist.getModeForPath(fname).mode);
        session.getUndoManager().markClean();
        session.on("change", function() {
            updateTitle("unsaved");
        });

        editor.setSession(session);

        // Apply now that we're loaded
        // Also sets the options
        self.updateSettings(settings);

        updateTitle("saved");

        layoutContainer.on("resize", function() {
            editor.resize();
        });

        // Events triggered by the Vim keybindings
        containerElem.on("director:save", saveFile);

        containerElem.on("director:close", function() {
            layoutContainer.close();
        });

        containerElem.keydown(function(e) {
            // Ctrl+S, Ctrl+F4, Meta+S, Meta+F4, Pause
            if(((e.which == 115 || e.which == 83) && (e.ctrlKey || e.metaKey)) || e.which == 19) {
                saveFile();
                return false;
            }
        });
    }).fail(function(data) {
        Messenger().error({
            message: "Error opening file: " + (data.responseText || "Unknown error"),
            hideAfter: 5,
        });

        layoutContainer.close();
    });

    containerElem.keydown(function(e) {
        if(e.ctrlKey) {
            switch(e.keyCode) {
                case 189: // Ctrl + Minus
                    settings["editor-font-size"] = parseInt(settings["editor-font-size"]);
                    if(settings["editor-font-size"] > 8) {
                        settings["editor-font-size"] -= 4;
                        self.triggerSettingsUpdate();
                    }
                    e.preventDefault();
                    break;
                case 187: // Ctrl + Plus
                    settings["editor-font-size"] = parseInt(settings["editor-font-size"]);
                    if(settings["editor-font-size"] < 80) {
                        settings["editor-font-size"] += 4;
                        self.triggerSettingsUpdate();
                    }
                    e.preventDefault();
                    break;
            }
        }
    });

    this.focus = function() {
        if(editor != null) {
            editor.focus();
        }
    };

    var settings = {};

    this.updateSettings = function(newSettings) {
        settings = newSettings;

        if(editor == null) {
            if(settings["layout-theme"] == "light") {
                containerElem.css("background-color", "white");
            }
            else {
                containerElem.css("background-color", "black");
            }
        }
        else {
            editor.setOptions({
                "fontSize": settings["editor-font-size"] + "px",
                "showPrintMargin": false,
                "enableBasicAutocompletion": true,
                "enableLiveAutocompletion": settings["editor-live-autocompletion"],
                "theme": settings["editor-theme"],
            });

            editor.setKeyboardHandler(settings["editor-keybinding"]);
        }
    };
}

ace.config.loadModule("ace/keybinding/vim", function() {
    var VimApi = ace.require("ace/keyboard/vim").CodeMirror.Vim;
    VimApi.defineEx("write", "w", function(cm) {
        // save on :write
        $(cm.ace.container).trigger("director:save");
    });

    VimApi.defineEx("quit", "q", function(cm) {
        // close on :quit
        $(cm.ace.container).trigger("director:close");
    });

    VimApi.defineEx("wq", "wq", function(cm) {
        // Save and close on :wq
        $(cm.ace.container).trigger("director:save");
        $(cm.ace.container).trigger("director:close");
    });
});
