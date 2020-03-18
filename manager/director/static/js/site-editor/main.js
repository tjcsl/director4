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

    var components = [];
    function addComponent(container, obj) {
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

        localStorage.setItem("editor-settings-" + site_id, JSON.stringify(settings));
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
            $.extend(settings, JSON.parse(settingsData));
        }
    }

    if(site_info.has_database) {
        layout_config.content[0].content[1].content[1].content.push({
            type: "component",
            componentName: "database-shell",
            isClosable: false,
        });
    }

    var layout = new GoldenLayout(layout_config, $("#editor-container"));


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

        addComponent(container, new SettingsPane(container.getElement(), settings, updateSettings));
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


    layout.init();
    $(window).resize(function() {
        layout.updateSize();
    });
});
