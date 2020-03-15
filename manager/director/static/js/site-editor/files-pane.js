function FilesPane(container, uri, callbacks) {
    // Used in callbacks where "this" is overriden
    var self = this;

    container.addClass("files-pane");

    container.append($("<div>").addClass("children"));

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

        var fileEv = JSON.parse(e.data);

        switch(fileEv.event) {
            case "create":
                self.addItem(fileEv);
                break;
            case "delete":
                var elem = self.followPath(fileEv.fname);
                if(elem != null) {
                    elem.remove();
                }
                break;
            case "update":
                self.updateItem(fileEv);
                break
        }
    }

    function wsClosed() {
        container.addClass("disabled");

        isOpen = false;

        setTimeout(openWS, 3000);
    }

    function getOpenFolderNames() {
        return container.find(".type-folder.open").map((i, e) => self.getElemPath($(e))).get();
    }

    this.followPath = function(path) {
        var parts = path.split("/").filter((s) => s.length);
        var currentElem = container;

        while(parts.length) {
            if(parts[0] == ".") {
                parts.splice(0, 1);
            }

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

    this.getElemPath = function(elem) {
        // We get all the parent .type-folder elements up until the root .files-pane.
        // Then we find their .info-row direct children (the .info-rows hold the main information)
        // Then we find their .item-name direct children (the .item-names hold the actual name).
        // Then we get the text of each of those (which is the name).
        // This is a jQuery object, so we translate it to an array.
        // It's from the child going up to the parent, so we reverse it.
        // And then we add the final entry, the element itself, and join it all together.
        return [...elem.parentsUntil(".files-pane", ".type-folder").children(".info-row").children(".item-name").map((i, elem) => elem.innerText).get().reverse(), elem.children(".info-row").children(".item-name").text()].join("/");
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

        infoRow.dblclick(function(e) {
            var elem = $(e.target).closest(".info-row").parent();

            if(elem.hasClass("type-folder")) {
                self.toggleDir(elem);
            }
            else {
                openFileCallback(self.getElemPath(elem));
            }
        });

        if(info.filetype == "dir") {
            itemContainer.append($("<div>").addClass("children"));
        }

        return itemContainer;
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

    /*this.addItem({fname: "c", filetype: "dir"});
    this.addItem({fname: "c/d", filetype: "file"});

    this.addItem({fname: "c/e", filetype: "dir"});
    this.addItem({fname: "c/e/f", filetype: "file"});

    this.toggleDir("c");*/

    openWS();
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


function ItemInfo(info) {
    this.mode = info.mode;
    this.filetype = info.filetype;
    this.fname = info.fname;

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
            if(info.fname.match(/\.(jpeg|jpg|gif|png|ico)$/)) {
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
