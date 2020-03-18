function FileEditor(layoutContainer, load_endpoint, save_endpoint, fname) {
    var self = this;

    var containerElem = layoutContainer.getElement();

    var currentStatus;
    function updateTitle(fileStatus) {
        var prefixClasses;
        if(fileStatus == "loading" || fileStatus == "saving") {
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
                contents: editor.getSession().getValue(),
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

        containerElem.on("director:save", saveFile);

        containerElem.keydown(function(e) {
            if(((e.which == 115 || e.which == 83) && (e.ctrlKey || e.metaKey)) || e.which == 19) {
                saveFile();
                return false;
            }
        });
    }).fail(function(data) {
        layoutContainer.close();
    });

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
