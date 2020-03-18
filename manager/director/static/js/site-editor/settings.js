function SettingsPane(container, settings, updateCallback, resetLayout) {
    var settingsSpec = {
        "layout-theme": {
            label: "Layout Theme",
            type: "select",
            choices: {
                light: "Light",
                dark: "Dark",
            },
            callback: function() {
                if(settings["layout-theme"] == "dark") {
                    if(settings["editor-theme"] == "ace/theme/chrome") {
                        settings["editor-theme"] = "ace/theme/monokai";
                    }
                }
                else {
                    if(settings["editor-theme"] == "ace/theme/monokai") {
                        settings["editor-theme"] = "ace/theme/chrome";
                    }
                }
            },
        },
        "editor-theme": {
            label: "Editor Theme",
            type: "select",
            choices: {
                "ace/theme/chrome": "Default",
                "ace/theme/clouds": "Clouds",
                "ace/theme/monokai": "Monokai",
                "ace/theme/solarized_light": "Solarized Light",
                "ace/theme/solarized_dark": "Solarized Dark",
            },
        },
        "editor-keybinding": {
            label: "Editor Keybindings",
            type: "select",
            choices: {
                "": "Default",
                "ace/keyboard/vim": "Vim",
                "ace/keyboard/emacs": "Emacs",
            },
        },
        "editor-font-size": {
            label: "Editor Font Size",
            type: "select",
            choices: {
                8: "8px",
                12: "12px",
                16: "16px",
                20: "20px",
                24: "24px",
                28: "28px",
                32: "32px",
                36: "36px",
                40: "40px",
                44: "44px",
                52: "52px",
                56: "56px",
                60: "60px",
                64: "64px",
                68: "68px",
                72: "72px",
                76: "76px",
                80: "80px",
            },
        },
        "terminal-font-size": {
            label: "Terminal Font Size",
            type: "select",
            choices: {
                8: "8px",
                12: "12px",
                16: "16px",
                20: "20px",
                24: "24px",
            },
        },
        "editor-live-autocompletion": {
            label: "Enable code autocompletion",
            type: "checkbox",
        },
        "show-hidden": {
            label: "Show hidden files",
            type: "checkbox",
        },
    };

    function setInputValues() {
        for(var settingName in settingsSpec) {
            switch(settingsSpec[settingName].type) {
                case "select":
                    settingsInputs[settingName].val(settings[settingName]);
                    break;
                case "checkbox":
                    settingsInputs[settingName].prop("checked", settings[settingName]);
                    break;
            }
        }
    }

    function settingChanged(e) {
        var settingName = $(e.target).data("setting");
        var settingsOpts = settingsSpec[settingName];

        switch(settingsOpts.type) {
            case "select":
                settings[settingName] = $(e.target).val();
                break;
            case "checkbox":
                settings[settingName] = $(e.target).prop("checked");
                break;
        }

        // We call the callback AFTER changing the value.
        // Some of the callbacks may assume this.
        if(settingsOpts.callback != null) {
            settingsOpts.callback();
        }

        updateCallback();
    }

    var interior = $("<div>").addClass("settings-pane").css({
        "padding": 15,
        "height": "100%",
        "width": "100%",
    }).appendTo(container);

    $("<h3>").append(
        $("<i>").addClass("fas fa-wrench").css("margin-bottom", 15),
        " Settings",
    ).appendTo(interior);

    var settingsInputs = {};

    var settingsTable = $("<div>").addClass("tbl").appendTo(interior);

    for(var settingName in settingsSpec) {
        var settingsOpts = settingsSpec[settingName];

        var settingRow = $("<div>").addClass("tbl-row").appendTo(settingsTable);

        $("<label>").addClass("tbl-cell").css({
            "padding-right": 5,
        }).text(settingsOpts.label).appendTo(settingRow);

        var input;
        switch(settingsOpts.type) {
            case "select":
                input = $("<select>").addClass("form-control");
                for(var choiceName in settingsOpts.choices) {
                    $("<option>").attr("value", choiceName).text(settingsOpts.choices[choiceName]).appendTo(input);
                }
                break;
            case "checkbox":
                input = $("<input>").attr("type", "checkbox");
                break;
        }

        input.data("setting", settingName).addClass("tbl-cell").css({
            "margin-bottom": 10,
        }).appendTo(settingRow);

        input.on("input change", settingChanged);

        settingsInputs[settingName] = input;
    }

    $("<button>").attr("type", "button").addClass("btn btn-ion").append(
        $("<i>").addClass("fas fa-undo"),
        " Reset layout",
    ).click(resetLayout).appendTo(interior);

    this.updateSettings = function() {
        setInputValues();
    };

    setInputValues();
}
