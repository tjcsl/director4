function FilesPane(container, uri, callbacks) {
    // Used in callbacks where "this" is overriden
    var self = this;

    container.addClass("files-pane");

    var itemsContainer = $("<div>").addClass("items").appendTo(container);

    itemsContainer.append($("<div>").addClass("children"));

    // This takes up a lot of space at the bottom of the pane. If people drop a file here, it will end up in the site's root directory.
    var rootDropContainer = $("<div>").addClass("root-drop-container").appendTo(itemsContainer);

    var fileUploaderInput = $("<input>").attr("type", "file").prop("multiple", true).css("display", "none");

    var openFileCallback = callbacks.openFile || function(fname) {};

    var ws = null;
    var isOpen = false;
    var firstOpen = true;

    var customStylesheet = $("<style>").appendTo("head");

    function openWS() {
        ws = new WebSocket(uri);
        ws.onopen = wsOpened;
        ws.onmessage = wsMessage;
        ws.onclose = wsClosed;
    }

    var prevOpenFolders = [];
    function wsOpened() {
        // Immediately request that we start watching the root directory (obviously)
        ws.send(JSON.stringify({action: "add", path: ""}));
        // And send a heartbeat
        // Even if the root directory has nothing in it, this should give us a response.
        // Then wsMessage() will know we've really got a connection
        ws.send(JSON.stringify({heartbeat: 1}));
    }

    function wsMessage(e) {
        if(!isOpen) {
            // We don't want to do this as soon as it's opened because
            // the connection may be immediately closed for various reasons
            // on the backend.
            // So we wait until we first get a message to set everything up.

            prevOpenFolders = getOpenFolderNames();

            if(firstOpen) {
                firstOpen = false;
                prevOpenFolders = ["public"];
            }

            itemsContainer.children(".children").empty();
            itemsContainer.removeClass("disabled");

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

        // Try to reopen
        setTimeout(openWS, 3000);
    }

    // Send heartbeats every 30 seconds to keep the connection alive
    setInterval(function() {
        if(isOpen && ws != null) {
            ws.send(JSON.stringify({heartbeat: 1}));
        }
    }, 30 * 1000);

    // Finds the full paths of all expanded folders, either in the given element or in the entire pane
    function getOpenFolderNames(elem) {
        var items = (elem || itemsContainer).find(".type-folder.open").map((i, e) => self.getElemPath($(e))).get();
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
        var currentElem = itemsContainer;

        while(parts.length) {
            if(currentElem != itemsContainer && !currentElem.hasClass("type-folder")) {
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

    // Given the "information" specification for a file/folder/symlink/special file,
    // creates the item and adds it to the correct place in the tree
    this.addItem = function(info) {
        // Is there something with the same name? If so, remove it.
        // Events may be duplicated or delayed, so we need this.
        var prevItem = self.followPath(info.fname);
        if(prevItem != null) {
            prevItem.remove();
        }

        // ItemInfo computes extra useful information
        var newInfo = new ItemInfo(info);

        // Get the parent element. If it doesn't exist, abort.
        var parentElem = this.followPath(newInfo.parentPath);
        if(parentElem == null) {
            return;
        }

        // Invoke makeItem() to make the actual item container
        var newItem = makeItem(info);

        // Now try to figure out where we should put it.
        var newItemSortOrder = getItemTypeSortOrder(newItem);

        var beforeItem = null;
        parentElem.children(".children").children().each(function() {
            var currentItemSortOrder = getItemTypeSortOrder($(this));

            if(currentItemSortOrder > newItemSortOrder) {
                // The current item comes later in the sort order than the item
                // we're adding, so we should insert it before this.
                beforeItem = $(this);
                return false;
            }
            else if(currentItemSortOrder == newItemSortOrder) {
                // The current item and the item we're adding are at the same point in
                // the sort order. Let's compare the names.
                var name = $(this).children(".info-row").children(".item-name").text();

                if(name > newInfo.basename) {
                    // The current item's name should be sorted after the item we're
                    // adding. So we insert the new item before the current item.
                    beforeItem = $(this);
                    return false;
                }
            }
        });

        // Add it to the proper place
        if(beforeItem != null) {
            newItem.insertBefore(beforeItem);
        }
        else {
            parentElem.children(".children").append(newItem);
        }

        // prevOpenFolders is a mechanism by which various parts of the application can indicate
        // that a folder "used to be" open and it should be reopened as soon as it's seen.
        // So we check that.
        if(prevOpenFolders.includes(info.fname)) {
            self.toggleDir(info.fname);

            // And now remove it so it doesn't mess things up later.
            prevOpenFolders = prevOpenFolders.filter(x => (x != info.fname));
        }
    };

    // The value this function returns is used to sort items.
    // It is checked before the names are compared, so this can be used to group
    // different types of items (files, folders, etc.)
    function getItemTypeSortOrder(elem) {
        if(elem.hasClass("type-folder")) {
            return 0;
        }
        else {
            return 1;
        }
    }

    // Information about an item has changed.
    // This only really happens when file attributes change, so we just check the mode.
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

        if(newInfo.basename.startsWith(".")) {
            itemContainer.addClass("hidden");
        }

        infoRow.append($("<i>").addClass(newInfo.faIcon));

        infoRow.append($("<span>").addClass("item-name").text(newInfo.basename));

        infoRow.prop("draggable", true);

        // For symlinks, show the destination
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
                // Expand directories on double-click
                self.toggleDir(elem);
            }
            else if(elem.hasClass("type-file")) {
                // Open files on double-click
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

        // Allow dropping things on directories
        if(itemContainer.hasClass("type-folder")) {
            makeDropable(infoRow);
        }
    }

    function makeDropable(elem) {
        var dragOpenTimeoutId = null;
        elem.on("dragover", function(e) {
            elem.parent().addClass("dragover");
            // Signals that it's safe to drop onto this element
            e.preventDefault();

            if(elem.parent().hasClass("type-folder") &&dragOpenTimeoutId == null) {
                dragOpenTimeoutId = setTimeout(function() {
                    self.openDir(elem.parent());
                }, 1500);
            }
        });

        elem.on("dragleave", function(e) {
            elem.parent().removeClass("dragover");

            if(dragOpenTimeoutId != null) {
                clearTimeout(dragOpenTimeoutId);
                dragOpenTimeoutId = null;
            }
        });

        elem.on("drop", function(e) {
            // Get the path of the original element
            var elempath = self.getElemPath($(e.target));

            // Resolve the main container (more reliable than e.target for getting the main container)
            var elem = self.followPath(elempath);

            elem.removeClass("dragover");

            if(dragOpenTimeoutId != null) {
                clearTimeout(dragOpenTimeoutId);
                dragOpenTimeoutId = null;
            }

            var dataTransfer = e.originalEvent.dataTransfer;
            if(dataTransfer && dataTransfer.files.length) {
                e.preventDefault();
                uploadFiles(elempath, dataTransfer.files);
            }
            else {
                // Get the source path
                var oldpath = dataTransfer.getData("source-fname");
                // And derive the destination path
                var newpath;
                if(elempath) {
                    newpath = elempath + "/" + dataTransfer.getData("source-basename");
                }
                else {
                    newpath = dataTransfer.getData("source-basename");
                }

                var oldelem = self.followPath(oldpath);

                // Something went wrong; bail out.
                if(!oldpath || !newpath) {
                    return;
                }

                // If we'd be moving to the same directory, or moving to ourselves, or to a subdirectory of ourselves, bail out.
                if((newpath + "/").startsWith(oldpath + "/")) {
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

                // Rename the file
                $.post({
                    url: file_endpoints.rename + "?" + $.param({
                        oldpath: oldpath,
                        newpath: newpath,
                    }),
                }).done(function() {
                    // Open directories we moved files into;
                    self.openDir(elem);
                }).fail(function(data) {
                    Messenger().error({
                        message: data.responseText || "Error moving file",
                        hideAfter: 3,
                    });
                });
            }
        });
    }

    $.contextMenu({
        selector: ".files-pane .root-drop-container",
        build: function(triggerElem, e) {
            var elem = itemsContainer;

            return {
                callback: function(key, options) {
                    switch(key) {
                        case "upload":
                            fileUploaderInput.data("parent_fname", "");
                            fileUploaderInput.trigger("click");
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
                    "show-log": {name: "Show Log", icon: "fas fa-chart-line"},
                    "sep1": "---------",
                    "upload": {name: "Upload", icon: "fas fa-upload"},
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
                        case "upload":
                            fileUploaderInput.data("parent_fname", self.getElemPath(elem));
                            fileUploaderInput.trigger("click");
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
                    "upload": {name: "Upload", icon: "fas fa-upload"},
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
                        case "download":
                            downloadFile(elem);
                            break;
                        case "rename":
                            renameItem(elem);
                            break;
                        case "delete":
                            deleteFile(elem);
                            break;
                        case "toggle-exec":
                            toggleFileExecutable(elem);
                            break;
                    }
                },
                items: {
                    "download": {name: "Download", icon: "fas fa-download"},
                    "toggle-exec": {name: (elem.hasClass("executable") ? "Unset executable" : "Set executable"), icon: "fas fa-chart-line"},
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

    function downloadFile(elem) {
        var path = self.getElemPath(elem);

        var frame = $("<iframe>");
        frame.css("display", "none");
        frame.on("load", function() {
            $(this).remove();
        });

        frame.attr("src", file_endpoints.get + "?" + $.param({path: path}));

        frame.appendTo($("body"));
    }

    // Given an item, shows the rename dialog and renames the file
    function renameItem(elem) {
        var oldpath = self.getElemPath(elem);
        var oldname = elem.children(".info-row").children(".item-name").text();

        makeEntryModalDialog(
            "Rename " + (elem.hasClass("type-folder") ? "Folder" : "File"),
            $("<div>").append(
                "Please enter the new name for ",
                $("<code>").text(oldname),
                ":",
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

    fileUploaderInput.change(function() {
        var files = fileUploaderInput.get(0).files;
        if(!files.length) {
            return;
        }

        var basepath = fileUploaderInput.data("parent_fname");

        uploadFiles(basepath, files);

        fileUploaderInput.val("");
    });

    function uploadFiles(basepath, files) {
        var formData = new FormData();
        for(var i = 0; i < files.length; i++) {
            formData.append("files[]", files[i], files[i].name);
        }

        var msg_obj = Messenger().info({
            message: (files.length == 1 ? "Uploading 1 file..." : "Uploading " + files.length + " files..."),
            hideAfter: false,
        });

        var numFiles = files.length;

        $.post({
            url: file_endpoints.write + "?" + $.param({basepath: basepath}),
            data: formData,
            processData: false,
            contentType: false,
        }).then(function(data) {
            if(basepath != "") {
                self.openDir(basepath);
            }

            msg_obj.update({
                type: "success",
                message: (numFiles == 1 ? "Uploaded 1 file successfully" : "Uploaded " + numFiles + " files successfully"),
                hideAfter: 5,
            });
        }).fail(function(data) {
            msg_obj.update({
                type: "error",
                message: "Error uploading file: " + (data.responseText || "Unknown error"),
                hideAfter: 5,
            });
        });
    }

    // Shows the "new file" dialog and creates the file in the given element
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
                    url: file_endpoints.create + "?" + $.param({path: path}),
                }).done(function() {
                    // Open directories we created files in:
                    if(elem.hasClass("type-folder")) {
                        self.openDir(elem);
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

    // Shows the "new file" dialog and creates the file in the given element
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
                    if(elem.hasClass("type-folder")) {
                        self.openDir(elem);
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

    // Shows the "delete file" dialog and deletes the given file
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

    // Shows the "delete folder" dialog and deletes the given folder and all contents
    function deleteFolderRecursively(elem) {
        self.openDir(elem);

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

    // Toggles a file's executable bits
    function toggleFileExecutable(elem) {
        var path = self.getElemPath(elem);
        var mode = (elem.hasClass("executable") ? "-x" : "+x");

        $.post({
            url: file_endpoints.chmod + "?" + $.param({path: path, mode:mode}),
        }).fail(function(data) {
            Messenger().error({
                message: data.responseText || "Error setting executable bits",
                hideAfter: 3,
            });
        });
    }

    // Given either a path or an element, gets the corresponding element
    function dirspecToElem(dirspec) {
        if(typeof dirspec == "string") {
            return self.followPath(dirspec);
        }
        else {
            return dirspec;
        }
    }

    // Expands (opens) the given directory
    this.openDir = function(dirspec) {
        var elem = dirspecToElem(dirspec);
        if(!elem.hasClass("open")) {
            this.toggleDir(elem);
        }
    };

    // Collapses (closes) the given directory
    this.closeDir = function(dirspec) {
        var elem = dirspecToElem(dirspec);
        if(elem.hasClass("open")) {
            this.toggleDir(elem);
        }
    };

    // Toggles the directory's "open" status
    this.toggleDir = function(dirspec) {
        var elem = dirspecToElem(dirspec);

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
    };

    // Hide all hidden files
    this.hideHiddenFiles = function() {
        customStylesheet.append(".files-pane .hidden{display: none;}");
    };

    // Show all hidden files
    this.showHiddenFiles = function() {
        customStylesheet.append(".files-pane .hidden{display: initial;}");
    };

    openWS();

    makeDropable(rootDropContainer);

    // If the user is trying to drag a file onto the pane to upload it
    // and they miss the folder, intercept the event and stop the browser
    // from automatically opening the file.
    $(itemsContainer).on("dragover drop", function(e) {
        return false;
    });

    this.hideHiddenFiles();
}


function ItemInfo(info) {
    // Copy parameters
    this.mode = info.mode;
    this.filetype = info.filetype;
    this.fname = info.fname;
    this.dest = info.dest;

    // Split the path and get the parts
    var parts = splitPath(info.fname);
    this.parentPath = parts[0];
    this.basename = parts[1];

    // Are any of the executable bits set?
    this.isExecutable = info.mode != null && (info.mode & 0o111) != 0;

    // Classes
    this.typeClass = {
        "dir": "type-folder",
        "file": "type-file",
        "link": "type-link",
        "other": "type-special",
    }[info.filetype];

    if(info.fname.match(/\.(jpe?g|gif|png|ico)$/) != null) {
        this.contentClass = "content-image";
    }
    else if(info.fname.match(/\.(mp[34]|pdf|swf)$/) != null) {
        this.contentClass = "content-video";
    }
    else {
        this.contentClass = "";
    }

    // Find the best icon
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
            else {
                this.faIcon = "far fa-file";
            }

            break;

        default:
            this.faIcon = "far fa-file";
    }
}
