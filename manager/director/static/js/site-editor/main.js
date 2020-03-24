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
                    id: "files",
                    content: [{
                        type: "component",
                        componentName: "settings",
                        isClosable: false,
                    }],
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

    if(site_info.has_database) {
        layout_config.content[0].content[1].content[1].content.push({
            type: "component",
            componentName: "database-shell",
            isClosable: false,
        });
    }

    var components = [];
    function addComponent(container, obj) {
        obj.triggerSettingsUpdate = updateSettings;

        components.push(obj);
        obj.updateSettings(settings);

        container.on("destroy", function() {
            var i = components.indexOf(obj);
            if(i != -1) {
                components.splice(i, 1);
            }
        });
    }

    function updateSettings() {
        components.forEach(function(obj) {
            obj.updateSettings(settings);
        });

        var light_theme = (settings["layout-theme"] == "light");
        $("#goldenlayout-light-theme").prop("disabled", !light_theme);
        $("#goldenlayout-dark-theme").prop("disabled", light_theme);
        if(light_theme) {
            $("body").removeClass("dark");
        }
        else {
            $("body").addClass("dark");
        }

        localStorage.setItem("editor-settings-" + site_id, JSON.stringify(settings));
    }

    function resetLayout() {
        localStorage.removeItem("editor-layout-" + site_id);
        location.reload();
    }

    function saveLayout() {
        localStorage.setItem("editor-layout-" + site_id, JSON.stringify(layout.toConfig()));
    }

    var settings = {
        "show-hidden": false,
        "layout-theme": "light",
        "editor-theme": "ace/theme/chrome",
        "editor-keybinding": "",
        "editor-font-size": 16,
        "editor-live-autocompletion": true,
        "terminal-font-size": 16,
    };

    if(localStorage != null) {
        var settingsData = localStorage.getItem("editor-settings-" + site_id);
        if(settingsData) {
            // Use the values from LocalStorage to override the defaults
            $.extend(settings, JSON.parse(settingsData));
        }

        var layoutData = localStorage.getItem("editor-layout-" + site_id);
        if(layoutData) {
            layout_config = JSON.parse(layoutData);

            Messenger().info({
                message: "Your editor layout has been restored from your last session.",
                actions: {
                    "reset": {
                        "label": "Reset Layout",
                        "action": resetLayout,
                    }
                },
                showCloseButton: true,
                hideAfter: 5,
            });
        }
    }

    var layout = new GoldenLayout(layout_config, $("#editor-container"));

    layout.on("stateChanged", function() {
        saveLayout();
    });

    layout.registerComponent("files", function(container, componentState) {
        container.setTitle("<span class='fas fa-folder-open'></span> Files");

        addComponent(container, new FilesPane(
            container.getElement(),
            ws_endpoints.file_monitor,
            {
                openFile: function(fname) {
                    var filesContainer = layout.root.getItemsById("files")[0];
                    if(fname) {
                        filesContainer.addChild({
                            type: "component",
                            componentName: "editfile",
                            componentState: {
                                fname: fname,
                            },
                        });
                    }
                },
                openLogs: function(fname) {
                    var filesContainer = layout.root.getItemsById("files")[0];
                    if(!fname) {
                        filesContainer.addChild({
                            type: "component",
                            componentName: "log",
                        });
                    }
                },
            },
        ));
    });

    layout.registerComponent("editfile", function(container, componentState) {
        addComponent(container, new FileEditor(container, file_endpoints.get, file_endpoints.write, componentState.fname));
    });

    layout.registerComponent("media", function(container, componentState) {
    });

    layout.registerComponent("log", function(container, componentState) {
        container.setTitle("<span class='fas fa-chart-line'></span> Process Log");

        addComponent(container, new SiteLogsFollower(container.getElement(), ws_endpoints.site_logs));
    });

    layout.registerComponent("settings", function(container, componentState) {
        container.setTitle("<span class='fas fa-wrench'></span> Settings");

        addComponent(container, new SettingsPane(container.getElement(), settings, updateSettings, resetLayout));
    });

    layout.registerComponent("terminal", function(container, componentState) {
        container.setTitle("<span class='fas fa-terminal'></span> Terminal");

        addComponent(container, setupTerminal(
            ws_endpoints.terminal,
            container.getElement(),
            {
                autoFocus: false,
                onTitle: function(title) {
                    container.setTitle("<span class='fas fa-terminal'></span> " + escapeHTML(title));
                },
            },
        ));

        "open resize show".split(" ").forEach(function(event_name) {
            container.on(event_name, function() {
                // If we trigger the event immediately, the resize changes haven't propagated yet.
                // So we schedule it to run very soon.
                setTimeout(function() {
                    container.getElement().trigger("terminal:resize");
                }, 0);
            });
        });
    });

    layout.registerComponent("database-shell", function(container, componentState) {
        container.setTitle("<span class='fas fa-database'></span> SQL");

        container.getElement().html($("#database-shell-template").html());
        setupSQLConsole(db_shell_endpoint, container.getElement().children(".sql-console-wrapper"));
    });


    $(window).keydown(function(e) {
        if(e.altKey) {
            switch(e.keyCode) {
                case 13:  // Alt + Enter
                    // Restart process
                    restartProcess();
                    break;
                case 84:  // Alt + T
                    // Open terminal
                    var terminalsContainer = layout.root.getItemsById("terminals")[0];
                    terminalsContainer.addChild({
                        type: "component",
                        componentName: "terminal",
                    });
                    break;
                case 67:  // Alt + C
                    // Open SQL console
                    var terminalsContainer = layout.root.getItemsById("terminals")[0];
                    terminalsContainer.addChild({
                        type: "component",
                        componentName: "database-shell",
                    });
                    break;
            }
        }
    });


    layout.init();
    $(window).resize(function() {
        layout.updateSize();
    });


    updateSettings();
});

function restartProcess() {
    $.post({
        url: restart_endpoint,
    }).fail(function(data) {
        Messenger().error({
            message: "Error restarting process: " + (data.responseText || "Unknown error"),
            hideAfter: 3,
        });
    });
}
