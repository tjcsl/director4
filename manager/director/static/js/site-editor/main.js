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
                    id: "files",
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

        filesPane = new FilesPane(
            container.getElement(),
            ws_endpoints.file_monitor,
            {
                openFile: function(fname) {
                    console.log(fname);
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
        );
    });

    layout.registerComponent("file", function(container, componentState) {
    });

    layout.registerComponent("log", function(container, componentState) {
        container.setTitle("<span class='fas fa-chart-line'></span> Process Log");

        new SiteLogsFollower(container.getElement(), ws_endpoints.site_logs);
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
