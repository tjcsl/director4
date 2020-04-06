#!/usr/bin/env python3
import io
import os
import re
import shutil
import tarfile
import zipfile
from typing import Dict, List, Optional, Union

import requests

repo_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
vendor_dir = os.path.realpath(os.path.join(repo_dir, "director/static/vendor"))
template_dir = os.path.realpath(os.path.join(repo_dir, "director/templates"))


def match_single_item(items, match_func) -> bool:
    found_items = [item for item in items if match_func(item)]
    assert len(found_items) == 1
    return found_items[0]


def zipfile_url_load_mem(url: str) -> zipfile.ZipFile:
    req = requests.get(url)
    req.raise_for_status()

    return zipfile.ZipFile(io.BytesIO(req.content))


def tarfile_url_load_mem(url: str) -> tarfile.TarFile:
    req = requests.get(url)
    req.raise_for_status()

    return tarfile.open(fileobj=io.BytesIO(req.content))


def zipfile_extract(
    zf: zipfile.ZipFile,
    *,
    zipfile_base_path: str,
    extract_base_path: str,
    limit_files: Optional[List[str]],
) -> List[str]:
    zipfile_base_path = os.path.normpath(zipfile_base_path)
    extract_base_path = os.path.normpath(extract_base_path)

    extracted_files = []

    for member in zf.namelist():
        if member.endswith("/"):
            continue

        member = os.path.normpath(member)

        if os.path.commonpath([member, zipfile_base_path]) != zipfile_base_path:
            continue

        extract_fname = os.path.relpath(member, zipfile_base_path)

        if limit_files is not None:
            found = False
            for limit_fname in limit_files:
                limit_fname = os.path.normpath(limit_fname) + ("/" if limit_fname.endswith("/") else "")
                if limit_fname.endswith("/"):
                    if extract_fname.startswith(limit_fname):
                        found = True
                        continue
                elif limit_fname == extract_fname:
                    found = True
                    continue

            if not found:
                continue

        extract_path = os.path.join(extract_base_path, extract_fname)

        print("Extracting {} to {}".format(member, extract_path))

        with zf.open(member, "r") as f_obj:
            data = f_obj.read()

        os.makedirs(os.path.dirname(extract_path), mode=0o755, exist_ok=True)

        with open(extract_path, "wb") as f_obj:
            f_obj.write(data)

        extracted_files.append(member)

    return extracted_files


def tarfile_extract(
    tf: tarfile.TarFile,
    *,
    tarfile_base_path: str,
    extract_base_path: str,
    limit_files: Optional[List[str]],
) -> List[str]:
    tarfile_base_path = os.path.normpath(tarfile_base_path)
    extract_base_path = os.path.normpath(extract_base_path)

    extracted_files = []

    for member_info in tf.getmembers():
        if not member_info.isfile():
            continue

        member = member_info.name

        member = os.path.normpath(member)

        if os.path.commonpath([member, tarfile_base_path]) != tarfile_base_path:
            continue

        extract_fname = os.path.relpath(member, tarfile_base_path)

        if limit_files is not None:
            found = False
            for limit_fname in limit_files:
                limit_fname = os.path.normpath(limit_fname) + ("/" if limit_fname.endswith("/") else "")
                if limit_fname.endswith("/"):
                    if extract_fname.startswith(limit_fname):
                        found = True
                        continue
                elif limit_fname == extract_fname:
                    found = True
                    continue

            if not found:
                continue

        extract_path = os.path.join(extract_base_path, extract_fname)

        tarfile_extract_single_file(tf, member, extract_path)

        extracted_files.append(member)

    return extracted_files


def tarfile_extract_single_file(
    tf: tarfile.TarFile, member: str, extract_path: str
):
    print("Extracting {} to {}".format(member, extract_path))

    with tf.extractfile(member) as f_obj:
        data = f_obj.read()

    os.makedirs(os.path.dirname(extract_path), mode=0o755, exist_ok=True)

    with open(extract_path, "wb") as f_obj:
        f_obj.write(data)


def download_single_file(url: str, download_path: str):
    req = requests.get(url)
    req.raise_for_status()

    with open(download_path, "wb") as f_obj:
        f_obj.write(req.content)


class VendoredDependency:
    @property
    def name(self) -> str:
        raise NotImplementedError

    def get_latest_version(self) -> str:
        raise NotImplementedError

    def download_version(self, version: str, vendor_path: str) -> None:
        raise NotImplementedError


class NpmVendoredDependency(VendoredDependency):
    @property
    def package_name(self) -> str:
        return self.name

    def get_latest_version(self) -> str:
        if "/" in self.package_name:
            # https://github.com/npm/registry-issue-archive/issues/34
            req = requests.get("https://registry.npmjs.org/" + self.package_name)
            req.raise_for_status()

            return req.json()["dist-tags"]["latest"]
        else:
            req = requests.get("https://registry.npmjs.org/" + self.package_name + "/latest")
            req.raise_for_status()

            return req.json()["version"]

    def get_tarball_url(self, version: str) -> str:
        if "/" in self.package_name:
            req = requests.get("https://registry.npmjs.org/" + self.package_name)
            req.raise_for_status()

            return req.json()["versions"][version]["dist"]["tarball"]
        else:
            req = requests.get("https://registry.npmjs.org/" + self.package_name + "/" + version)
            req.raise_for_status()

            return req.json()["dist"]["tarball"]
    

def get_github_latest_release_name(repo: str) -> str:
    return requests.get("https://api.github.com/repos/" + repo + "/releases/latest").json()["tag_name"]


def get_github_latest_tag_name(repo: str) -> str:
    return requests.get("https://api.github.com/repos/" + repo + "/tags").json()[0]["name"]


def get_github_asset_download_url(repo: str, tag: str, name_match: Union[str, re.Pattern]) -> str:
    release_info = requests.get("https://api.github.com/repos/" + repo + "/releases/tags/" + tag).json()

    return match_single_item(
        release_info["assets"],
        lambda asset_info: (
            asset_info["name"] == name_match
            if isinstance(name_match, str) else
            name_match.search(asset_info["name"]) is not None
        ),
    )["browser_download_url"]


class BootstrapVendoredDependency(NpmVendoredDependency):
    name = "bootstrap"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/dist",
            extract_base_path=vendor_path,
            limit_files=[
                "css/bootstrap.min.css",
                "css/bootstrap.min.css.map",
                "js/bootstrap.bundle.min.js",
                "js/bootstrap.bundle.min.js.map",
            ],
        )


class FontAwesomeVendoredDependency(NpmVendoredDependency):
    name = "fontawesome-free"
    package_name = "@fortawesome/fontawesome-free"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE.txt", "css/all.min.css", "webfonts/"],
        )


class AceEditorVendoredDependency(NpmVendoredDependency):
    name = "ace"
    package_name = "ace-builds"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/src-min",
            extract_base_path=vendor_path,
            limit_files=None,
        )


class GoldenLayoutVendoredDependency(NpmVendoredDependency):
    name = "golden-layout"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/dist",
            extract_base_path=vendor_path,
            limit_files=["goldenlayout.min.js"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/src/css",
            extract_base_path=vendor_path,
            limit_files=[
                "goldenlayout-base.css",
                "goldenlayout-dark-theme.css",
                "goldenlayout-light-theme.css",
            ],
        )


class XtermVendoredDependency(NpmVendoredDependency):
    name = "xterm"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/css",
            extract_base_path=vendor_path,
            limit_files=["xterm.css"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/lib",
            extract_base_path=vendor_path,
            limit_files=["xterm.js"],
        )


class XtermAddonFitVendoredDependency(NpmVendoredDependency):
    name = "xterm-addon-fit"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/lib",
            extract_base_path=vendor_path,
            limit_files=["xterm-addon-fit.js", "xterm-addon-fit.js.map"],
        )


class HighlightJSVendoredDependency(NpmVendoredDependency):
    name = "highlight.js"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE", "styles/"],
        )

        download_single_file(
            "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/" + version + "/highlight.min.js",
            os.path.join(vendor_path, "highlight.min.js"),
        )


class JQueryVendoredDependency(NpmVendoredDependency):
    name = "jquery"

    def download_version(self, version: str, vendor_path: str) -> None:
        download_single_file(
            "https://code.jquery.com/jquery-" + version + ".min.js",
            vendor_path + ".min.js",
        )


class JQueryContextmenuVendoredDependency(NpmVendoredDependency):
    name = "jquery-contextmenu"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package/dist",
            extract_base_path=vendor_path,
            limit_files=[
                "jquery.contextMenu.min.css",
                "jquery.contextMenu.min.js",
                "jquery.ui.position.min.js",
                "font/",
            ],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE"],
        )


class SelectizeVendoredDependency(NpmVendoredDependency):
    name = "selectize"

    def download_version(self, version: str, vendor_path: str) -> None:
        tf = tarfile_url_load_mem(self.get_tarball_url(version))

        tarfile_extract(
            tf,
            tarfile_base_path="package",
            extract_base_path=vendor_path,
            limit_files=["LICENSE"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/dist/css",
            extract_base_path=vendor_path,
            limit_files=["selectize.default.css"],
        )

        tarfile_extract(
            tf,
            tarfile_base_path="package/dist/js/standalone",
            extract_base_path=vendor_path,
            limit_files=["selectize.min.js"],
        )


class MessengerVendoredDependency(VendoredDependency):
    name = "messenger"

    def get_latest_version(self) -> str:
        return get_github_latest_tag_name("HubSpot/messenger")[1:]

    def download_version(self, version: str, vendor_path: str) -> None:
        zf = zipfile_url_load_mem(
            "https://github.com/HubSpot/messenger/archive/v" + version + ".zip",
        )

        zipfile_extract(
            zf,
            zipfile_base_path="messenger-" + version,
            extract_base_path=vendor_path,
            limit_files=["LICENSE"],
        )

        zipfile_extract(
            zf,
            zipfile_base_path="messenger-" + version + "/build/css",
            extract_base_path=os.path.join(vendor_path, "css"),
            limit_files=["messenger.css", "messenger-theme-flat.css"],
        )

        zipfile_extract(
            zf,
            zipfile_base_path="messenger-" + version + "/build/js",
            extract_base_path=os.path.join(vendor_path, "js"),
            limit_files=["messenger.min.js", "messenger-theme-flat.js"],
        )
    

class ReconnectingWebsocketVendoredDependency(VendoredDependency):
    name = "reconnecting-websocket"

    def get_latest_version(self) -> str:
        req = requests.get("https://api.github.com/repos/joewalnes/reconnecting-websocket/commits/master")
        req.raise_for_status()

        return req.json()["sha"][:7]

    def download_version(self, version: str, vendor_path: str) -> None:
        download_single_file(
            "https://raw.githubusercontent.com/joewalnes/reconnecting-websocket/" + version + "/reconnecting-websocket.js",
            vendor_path + ".js",
        )


def list_existing_vendored_dependencies() -> Dict[str, str]:
    dependencies: Dict[str, str] = {}

    for fname in os.listdir(vendor_dir):
        if fname.startswith("."):
            continue

        if fname.endswith((".css", ".js")):
            fname = os.path.splitext(fname)[0]

            if fname.endswith((".min")):
                fname = os.path.splitext(fname)[0]

        name, version = fname.rsplit("-", 1)
        dependencies[name] = version

    return dependencies


print("\n*** WARNING: This script is experimental. Please inspect the changes and test the site if it upgrades anything! ***\n")

VENDORED_DEPENDENCIES = [
    BootstrapVendoredDependency(),
    FontAwesomeVendoredDependency(),
    AceEditorVendoredDependency(),
    GoldenLayoutVendoredDependency(),
    XtermVendoredDependency(),
    XtermAddonFitVendoredDependency(),
    HighlightJSVendoredDependency(),
    JQueryVendoredDependency(),
    JQueryContextmenuVendoredDependency(),
    SelectizeVendoredDependency(),
    MessengerVendoredDependency(),
    ReconnectingWebsocketVendoredDependency(),
]

old_dependencies = list_existing_vendored_dependencies()

for dependency in VENDORED_DEPENDENCIES:
    latest_version = dependency.get_latest_version()

    download = False

    if dependency.name not in old_dependencies:
        print("* {} not found; downloading version {}".format(dependency.name, latest_version))
        download = True
    elif old_dependencies[dependency.name] != latest_version:
        print("* {} is out of date (currently version {}); downloading version {}".format(dependency.name, old_dependencies[dependency.name], latest_version))
        download = True
    else:
        print("* {} is up to date".format(dependency.name))

    if download:
        dependency.download_version(latest_version, os.path.join(vendor_dir, dependency.name + "-" + latest_version))

        # Remove old version
        if dependency.name in old_dependencies:
            print("Removing version " + old_dependencies[dependency.name])
            shutil.rmtree(os.path.join(vendor_dir, dependency.name + "-" + old_dependencies[dependency.name]))

        prefix = "{% static 'vendor/" + dependency.name + "-"

        for root, dirs, files in os.walk(template_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                with open(fpath) as f_obj:
                    text = f_obj.read()

                text, count = re.subn(re.escape(prefix) + r"([0-9.]+|[0-9a-f]+)(?=[./'])", prefix + latest_version, text)

                if count:
                    print("Replaced {} references in {}".format(count, os.path.relpath(fpath, repo_dir)))
                    with open(fpath, "w") as f_obj:
                        f_obj.write(text)
