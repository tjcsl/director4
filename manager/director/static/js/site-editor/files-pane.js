function FilesPane(container, uri, callbacks) {
    // Used in callbacks where "this" is overriden
    var self = this;

    container.addClass("files-pane");

    container.append($("<div>").addClass("children"));

    var rootDropContainer = $("<div>").addClass("root-drop-container").css("height", "100vh").appendTo(container);

    var openFileCallback = callbacks.openFile || function(fname) {};

    var ws = null;
    var isOpen = false;
    var firstOpen = true;

    function openWS() {
        ws = new WebSocket(uri);
        ws.onopen = wsOpened;
        ws.onmessage = wsMessage;
        ws.onclose = wsClosed;
    }

    var prevOpenFolders = []
    function wsOpened() {
        ws.send(JSON.stringify({action: "add", path: ""}));
        ws.send(JSON.stringify({heartbeat: 1}));
    }

    function wsMessage(e) {
        if(!isOpen) {
            // We don't want to do this as soon as it's opened because
            // the connection may be immediately closed for various reasons
            // on the backend.

            prevOpenFolders = getOpenFolderNames();

            if(firstOpen) {
                firstOpen = false;
                prevOpenFolders = ["public"];
            }

            container.children(".children").empty();
            container.removeClass("disabled");

            isOpen = true;
        }

        var data = JSON.parse(e.data);

        if(data.heartbeat != null) {
            return;
        }

        switch(data.event) {
            case "create":
                self.addItem(data);
                break;
            case "delete":
                ws.send(JSON.stringify({action: "remove", path: data.fname}));

                var elem = self.followPath(data.fname);
                if(elem != null) {
                    elem.remove();
                }
                break;
            case "update":
                self.updateItem(data);
                break;
            case "error":
                self.handleError(data);
                break;
        }
    }

    function wsClosed() {
        container.addClass("disabled");

        isOpen = false;
        ws = null;

        setTimeout(openWS, 3000);
    }

    setInterval(function() {
        if(isOpen && ws != null) {
            ws.send(JSON.stringify({heartbeat: 1}));
        }
    }, 30 * 1000);

    function getOpenFolderNames(elem) {
        var items = (elem || container).find(".type-folder.open").map((i, e) => self.getElemPath($(e))).get();
        if(elem && elem.hasClass("type-folder") && elem.hasClass("open")) {
            items.push(self.getElemPath(elem));
        }
        return items;
    }

    // Given the /-separated "path" of a specific file/folder/special file, finds the container
    // element corresponding to that file.
    // This is the inverse of getElemPath().
    this.followPath = function(path) {
        var parts = path.split("/").filter((s) => s.length && s != ".");
        var currentElem = container;

        while(parts.length) {
            if(currentElem != container && !currentElem.hasClass("type-folder")) {
                return null;
            }

            var found = false;
            currentElem.children(".children").children().each(function() {
                if($(this).children(".info-row").children(".item-name").text() == parts[0]) {
                    currentElem = $(this);
                    parts.splice(0, 1);
                    found = true;
                    return false;
                }
            });

            if(!found) {
                return null;
            }
        }

        return currentElem;
    };

    this.handleError = function(data) {
        var elem = this.followPath(data.fname);
        if(elem == null) {
            return;
        }

        if(elem.hasClass("type-folder")) {
            elem.children(".children").text("<Error opening directory>");
        }
        Messenger().error({
            message: data.error || "Error opening directory",
            hideAfter: 2,
        });
    };

    // Given the container element for a specific file/directory/special file, returns the
    // /-separated "path" of that file.
    // This is the inverse of followPath().
    this.getElemPath = function(elem) {
        if(elem.parent(".info-row").length) {
            elem = elem.parent();
        }
        if(elem.hasClass("info-row")) {
            elem = elem.parent();
        }

        // We get all the parent .type-folder elements up until the root .files-pane.
        // Then we find their .info-row direct children (the .info-rows hold the main information)
        // Then we find their .item-name direct children (the .item-names hold the actual name).
        // Then we get the text of each of those (which is the name).
        // This is a jQuery object, so we translate it to an array.
        // It's from the child going up to the parent, so we reverse it.
        // And then we add the final entry, the element itself, and join it all together.
        return [
            ...elem.parentsUntil(".files-pane", ".type-folder").children(".info-row").children(".item-name").map((i, elem) => elem.innerText).get().reverse(),
            elem.children(".info-row").children(".item-name").text(),
        ].join("/");
    };

    this.addItem = function(info) {
        var prevItem = self.followPath(info.fname);
        if(prevItem != null) {
            prevItem.remove();
        }

        var newInfo = new ItemInfo(info);

        var parentElem = this.followPath(newInfo.parentPath);
        if(parentElem == null) {
            return;
        }

        var newItem = makeItem(info);
        var newItemSortOrder = getItemTypeSortOrder(newItem);

        var beforeItem = null;
        var afterItem = null;
        parentElem.children(".children").children().each(function() {
            var currentItemSortOrder = getItemTypeSortOrder($(this));

            if(currentItemSortOrder > newItemSortOrder) {
                beforeItem = $(this);
                return false;
            }
            else if(currentItemSortOrder == newItemSortOrder) {
                var name = $(this).children(".info-row").children(".item-name").text();
                if(name > newInfo.basename) {
                    beforeItem = $(this);
                    return false;
                }
            }
        });

        if(beforeItem != null) {
            newItem.insertBefore(beforeItem);
        }
        else if(afterItem != null) {
            newItem.insertAfter(afterItem);
        }
        else {
            parentElem.children(".children").append(newItem);
        }

        if(prevOpenFolders.includes(info.fname)) {
            self.toggleDir(info.fname);

            prevOpenFolders = prevOpenFolders.filter(x => (x != info.fname));
        }
    };

    function getItemTypeSortOrder(elem) {
        if(elem.hasClass("type-folder")) {
            return 0;
        }
        else {
            return 1;
        }
    }

    this.updateItem = function(info) {
        var newInfo = new ItemInfo(info);

        var elem = this.followPath(newInfo.fname);
        if(elem == null) {
            return;
        }

        if(newInfo.isExecutable) {
            elem.addClass("executable");
        }
        else {
            elem.removeClass("executable");
        }
    };

    function makeItem(info) {
        // Structure (* indicates "varies"):
        // <div class="type-* (optional classes: content-* executable)">
        //  <div class="info-row">
        //      <i class="far fa-*"></i>
        //      <span class="item-name">(name)</span>
        //  </div>
        //  (If a folder, then its children appear here:)
        //  <div class="children">
        //      ...
        //  </div>
        // </div>
        var newInfo = new ItemInfo(info);

        var itemContainer = $("<div>");

        itemContainer.addClass(newInfo.typeClass);
        itemContainer.addClass(newInfo.contentClass);

        itemContainer.addClass(newInfo.isExecutable ? "executable" : "");

        var infoRow = $("<div>");
        infoRow.addClass("info-row");
        itemContainer.append(infoRow);

        infoRow.append($("<i>").addClass(newInfo.faIcon));

        infoRow.append($("<span>").addClass("item-name").text(newInfo.basename));

        infoRow.prop("draggable", true);

        if(newInfo.filetype == "link") {
            infoRow.append($("<span>").addClass("item-dest").text(newInfo.dest || "?"));
        }

        addItemListeners(itemContainer);

        if(info.filetype == "dir") {
            itemContainer.append($("<div>").addClass("children"));
        }

        return itemContainer;
    }

    function addItemListeners(itemContainer) {
        var infoRow = itemContainer.children(".info-row");

        infoRow.dblclick(function(e) {
            var elem = $(e.target).closest(".info-row").parent();

            if(elem.hasClass("type-folder")) {
                self.toggleDir(elem);
            }
            else if(elem.hasClass("type-file")) {
                openFileCallback(self.getElemPath(elem));
            }
            else {
                Messenger().error({
                    message: "You can only edit files",
                    hideAfter: 2,
                });
            }
        });

        infoRow.on("dragstart", function(e) {
            var fname = self.getElemPath($(e.target));
            e.originalEvent.dataTransfer.setData("source-fname", fname);
            e.originalEvent.dataTransfer.setData("source-basename", splitPath(fname)[1]);
        });

        infoRow.on("drag", function(e) {
        });

        if(itemContainer.hasClass("type-folder")) {
            makeDropable(infoRow);
        }
    }

    function makeDropable(elem) {
        elem.on("dragover", function(e) {
            elem.addClass("dragover");
            // Signals that it's safe to drop onto this element
            e.preventDefault();
        });

        elem.on("dragleave", function(e) {
            elem.removeClass("dragover");
        });

        elem.on("drop", function(e) {
            // Get the path of the original element
            var elempath = self.getElemPath($(e.target));

            // Resolve the main container (more reliable than e.target for getting the main container)
            var elem = self.followPath(elempath);

            $(e.target).removeClass("dragover");
            elem.children(".info-row").removeClass("dragover");

            // Get the source path
            var oldpath = e.originalEvent.dataTransfer.getData("source-fname");
            // And derive the destination path
            var newpath;
            if(elempath) {
                newpath = elempath + "/" + e.originalEvent.dataTransfer.getData("source-basename");
            }
            else {
                newpath = e.originalEvent.dataTransfer.getData("source-basename");
            }

            var oldelem = self.followPath(oldpath);

            // Something went wrong; bail out.
            if(!oldpath || !newpath) {
                return;
            }

            // If this folder was open, or if any folders under it were open,
            // keep them open.
            if(oldelem.hasClass("type-folder") || oldelem.is(rootDropContainer)) {
                prevOpenFolders.push(
                    ...getOpenFolderNames(oldelem).map(
                        (name) => newpath + name.slice(oldpath.length)
                    )
                );
            }

            $.post({
                url: file_endpoints.rename + "?" + $.param({
                    oldpath: oldpath,
                    newpath: newpath,
                }),
            }).done(function() {
                // Open directories we moved files into;
                if(!elem.hasClass("open")) {
                    self.toggleDir(elem);
                }
            }).fail(function(data) {
                Messenger().error({
                    message: data.responseText || "Error moving file",
                    hideAfter: 3,
                });
            });
        });
    }

    $.contextMenu({
        selector: ".files-pane .root-drop-container",
        build: function(triggerElem, e) {
            var elem = container;

            return {
                callback: function(key, options) {
                    switch(key) {
                        case "newfile":
                            newFile(elem);
                            break;
                        case "newfolder":
                            newFolder(elem);
                            break;
                    }
                },
                items: {
                    "show-log": {name: "Show Log", icon: "fas fa-chart-line"},
                    "sep1": "---------",
                    "newfile": {name: "New file", icon: "fas fa-file"},
                    "newfolder": {name: "New folder", icon: "fas fa-folder"},
                },
            };
        },
    });

    $.contextMenu({
        selector: ".files-pane .type-folder",
        build: function(triggerElem, e) {
            var elem = self.followPath(self.getElemPath(triggerElem));
            if(elem == null) {
                return;
            }

            return {
                callback: function(key, options) {
                    switch(key) {
                        case "rename":
                            renameItem(elem);
                            break;
                        case "delete":
                            deleteFolderRecursively(elem);
                            break;
                        case "newfile":
                            newFile(elem);
                            break;
                        case "newfolder":
                            newFolder(elem);
                            break;
                    }
                },
                items: {
                    "rename": {name: "Rename", icon: "fas fa-pencil-alt"},
                    "delete": {name: "Delete", icon: "far fa-trash-alt"},
                    "sep2": "---------",
                    "newfile": {name: "New file", icon: "fas fa-file"},
                    "newfolder": {name: "New folder", icon: "fas fa-folder"},
                },
            };
        },
    });

    $.contextMenu({
        selector: ".files-pane .type-file",
        build: function(triggerElem, e) {
            var elem = self.followPath(self.getElemPath(triggerElem));
            if(elem == null) {
                return;
            }

            return {
                callback: function(key, options) {
                    switch(key) {
                        case "rename":
                            renameItem(elem);
                            break;
                        case "delete":
                            deleteFile(elem);
                            break;
                    }
                },
                items: {
                    "show-log": {name: "Show as Log", icon: "fas fa-chart-line"},
                    "sep1": "---------",
                    "rename": {name: "Rename", icon: "fas fa-pencil-alt"},
                    "delete": {name: "Delete", icon: "far fa-trash-alt"},
                },
            };
        },
    });

    $.contextMenu({
        selector: ".files-pane .type-link, .files-pane .type-special",
        build: function(triggerElem, e) {
            var elem = self.followPath(self.getElemPath(triggerElem));
            if(elem == null) {
                return;
            }

            return {
                callback: function(key, options) {
                    switch(key) {
                        case "rename":
                            renameItem(elem);
                            break;
                        case "delete":
                            deleteFile(elem);
                            break;
                    }
                },
                items: {
                    "rename": {name: "Rename", icon: "fas fa-pencil-alt"},
                    "delete": {name: "Delete", icon: "far fa-trash-alt"},
                },
            };
        },
    });

    function renameItem(elem) {
        var oldpath = self.getElemPath(elem);
        var oldname = elem.children(".info-row").children(".item-name").text();

        makeEntryModalDialog(
            "Rename " + (elem.hasClass("type-folder") ? "Folder" : "File"),
            $("<div>").append(
                "Please enter the new name for " + oldname + ":",
                "<br>",
            ),
            oldname,
            function(newname) {
                if(!newname) {
                    return;
                }

                var newpath = joinPaths([splitPath(oldpath)[0], newname]);

                $.post({
                    url: file_endpoints.rename + "?" + $.param({
                        oldpath: oldpath,
                        newpath: newpath,
                    }),
                }).fail(function(data) {
                    Messenger().error({
                        message: data.responseText || "Error renaming file",
                        hideAfter: 3,
                    });
                });
            }
        );
    }

    function newFile(elem) {
        makeEntryModalDialog(
            "New File",
            $("<div>").append(
                "Please enter the name for your new file:",
                "<br>",
            ),
            "",
            function(name) {
                if(!name) {
                    return;
                }

                var path = joinPaths([self.getElemPath(elem), name]);

                $.post({
                    url: file_endpoints.write + "?" + $.param({path: path}),
                    data: {contents: ""},
                }).done(function() {
                    // Open directories we created files in:
                    if(elem.hasClass("type-folder") && !elem.hasClass("open")) {
                        self.toggleDir(elem);
                    }
                }).fail(function(data) {
                    Messenger().error({
                        message: data.responseText || "Error creating file",
                        hideAfter: 3,
                    });
                });
            },
        );
    }

    function newFolder(elem) {
        makeEntryModalDialog(
            "New Folder",
            $("<div>").append(
                "Please enter the name for your new folder:",
                "<br>",
            ),
            "",
            function(name) {
                if(!name) {
                    return;
                }

                var path = joinPaths([self.getElemPath(elem), name]);

                $.post({
                    url: file_endpoints.mkdir + "?" + $.param({path: path}),
                }).done(function() {
                    // Open directories we created subdirectories in:
                    if(elem.hasClass("type-folder") && !elem.hasClass("open")) {
                        self.toggleDir(elem);
                    }
                }).fail(function(data) {
                    Messenger().error({
                        message: data.responseText || "Error creating folder",
                        hideAfter: 3,
                    });
                });
            },
        );
    }

    function deleteFile(elem) {
        var path = self.getElemPath(elem);

        makeYesNoModalDialog(
            "Are you sure you want to delete this file?",
            [
                "Are you sure you want to delete ",
                $("<code>").append(path),
                "?",
            ],
            function(result) {
                if(!result) {
                    return;
                }

                $.post({
                    url: file_endpoints.remove + "?" + $.param({path: path}),
                }).fail(function(data) {
                    Messenger().error({
                        message: data.responseText || "Error removing file",
                        hideAfter: 3,
                    });
                });
            }
        );
    }

    function deleteFolderRecursively(elem) {
        if(!elem.hasClass("open")) {
            self.toggleDir(elem);
        }

        var path = self.getElemPath(elem);

        makeEntryModalDialog(
            "Are you sure you want to delete this folder and ALL of its contents?",
            [
                "Are you sure you want to delete ",
                $("<code>").append(path),
                " and all of its contents? This action is PERMANENT and cannot be undone.",
                "<br>",
                "To confirm, please enter the name of the folder (",
                $("<code>").append(splitPath(path)[1]),
                ") below:",
            ],
            "",
            function(text) {
                if(!text || text != splitPath(path)[1]) {
                    return;
                }

                $.post({
                    url: file_endpoints.rmdir_recur + "?" + $.param({path: path}),
                }).fail(function(data) {
                    Messenger().error({
                        message: data.responseText || "Error removing folder",
                        hideAfter: 3,
                    });
                });
            }
        );
    }

    this.toggleDir = function(dirspec) {
        var elem;
        if(typeof dirspec == "string") {
            elem = this.followPath(dirspec);
        }
        else {
            elem = dirspec;
        }

        var path = this.getElemPath(elem);

        if(!elem.hasClass("type-folder")) {
            return;
        }

        var iconElem = elem.children(".info-row").children("i");

        if(elem.hasClass("open")) {
            elem.removeClass("open");
            iconElem.removeClass("far fa-folder-open");
            iconElem.addClass("far fa-folder");
            elem.children(".children").empty();

            ws.send(JSON.stringify({action: "remove", path: path}));
        }
        else {
            elem.addClass("open");
            iconElem.removeClass("far fa-folder");
            iconElem.addClass("far fa-folder-open");

            elem.children(".children").empty();

            ws.send(JSON.stringify({action: "add", path: path}));
        }
    }

    openWS();

    makeDropable(rootDropContainer);
}


function ItemInfo(info) {
    this.mode = info.mode;
    this.filetype = info.filetype;
    this.fname = info.fname;
    this.dest = info.dest;

    var parts = splitPath(info.fname);
    this.parentPath = parts[0];
    this.basename = parts[1];

    this.isExecutable = info.mode != null && (info.mode & 0o111) != 0;

    this.typeClass = {
        "dir": "type-folder",
        "file": "type-file",
        "link": "type-link",
        "other": "type-special",
    }[info.filetype];

    this.contentClass = "";
    if(info.fname.match(/\.(jpe?g|gif|png|ico)$/) != null) {
        this.contentClass = "content-image";
    }
    else if(info.fname.match(/\.(mp[34]|pdf|swf)$/) != null) {
        this.contentClass = "content-video";
    }

    switch(info.filetype) {
        case "dir":
            this.faIcon = "far fa-folder";
            break;

        case "file":
            if(info.fname.match(/\.(jpe?g|gif|png|ico)$/)) {
                this.faIcon = "far fa-file-image";
            }
            else if(info.fname.match(/\.(mp[34]|swf)$/) != null) {
                this.faIcon = "far fa-file-video";
            }
            else if(info.fname.match(/\.pdf$/) != null) {
                this.faIcon = "far fa-file-pdf";
            }
            else if(info.fname.match(/\.(docx?|odt)$/) != null) {
                this.faIcon = "far fa-file-word";
            }
            else if(info.fname.match(/\.(pyw?|php|js|html|css)$/) != null) {
                this.faIcon = "far fa-file-code";
            }
            else if(info.fname.match(/\.(txt|log)$/) != null) {
                this.faIcon = "far fa-file-text";
            }
            else if(info.fname.match(/\.(zip|rar|gz|tar|7z|bz2|xz|tgz)$/) != null) {
                this.faIcon = "far fa-file-archive";
            }

            this.faIcon = "far fa-file";
            break;

        default:
            this.faIcon = "far fa-file";
    }
}
