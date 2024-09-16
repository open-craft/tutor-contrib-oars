"""
Helpers for importing superset assets
"""

import glob
import os
import re
import json
from zipfile import ZipFile
from sqlfmt.api import format_string
from sqlfmt.mode import Mode

import click
import yaml

FILE_NAME_ATTRIBUTE = "_file_name"

PLUGIN_PATH = os.path.dirname(os.path.abspath(__file__))
ASSETS_PATH = os.path.join(
    PLUGIN_PATH,
    "templates",
    "aspects",
    "build",
    "aspects-superset",
    "openedx-assets",
    "assets",
)


def str_presenter(dumper, data):
    """
    Configures yaml for dumping multiline strings
    """
    if len(data.splitlines()) > 1 or "'" in data:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)


class SupersetCommandError(Exception):
    """
    An error we can use for these methods.
    """


class Asset:
    """
    Base class for asset types used in import.
    """

    path = None
    assets_path = None
    templated_vars = None
    required_vars = None
    omitted_vars = None
    raw_vars = None

    def __init__(self):
        if not self.path:
            raise NotImplementedError("Asset is an abstract class.")

    def get_path(self, all_assets_path):
        """
        Returns the full path to the asset file type.
        """
        self.assets_path = os.path.join(all_assets_path, self.path)

        if self.assets_path:
            return self.assets_path
        raise NotImplementedError

    def get_templated_vars(self):
        """
        Returns a list of variables which should have templated variables.

        This allows us to alert users when they might be submitting hard coded
        values instead of something like {{ TABLE_NAME }}.
        """
        return self.templated_vars or []

    def get_required_vars(self):
        """
        Returns a list of variables which must exist for the asset.

        This allows us to make sure users remember to add `_roles` to dashboards.
        Since those do not export.
        """
        return self.required_vars or []

    def get_omitted_vars(self):
        """
        Returns a list of variables which should be omitted from the content.
        """
        return self.omitted_vars or []

    def get_raw_vars(self):
        """
        Returns a list of variables which should be omitted from the content.
        """
        return self.raw_vars or []

    def remove_content(self, content: dict):
        """
        Remove any variables from the content which should be omitted.
        """
        for var_path in self.get_omitted_vars():
            self._remove_content(content, var_path.split("."))

    def _remove_content(self, content: dict, var_path: list):
        """
        Helper method to remove content from the content dict.
        """
        if content is None:
            return
        if len(var_path) == 1:
            content.pop(var_path[0], None)
            return
        if var_path[0] in content:
            self._remove_content(content[var_path[0]], var_path[1:])

    def omit_templated_vars(self, content: dict, existing: dict):
        """
        Omit templated variables from the content if they are not present in
        the existing file content.
        """
        if not isinstance(content, dict) or not isinstance(existing, dict):
            return

        for key in content.keys():
            if key not in existing.keys():
                continue
            if isinstance(existing[key], str):
                if "{{" in existing.get(key, "") or "{%" in existing.get(key, ""):
                    if key in self.get_raw_vars():
                        raw_expression = "{% raw %}" + content[key] + "{% endraw %}"
                        content[key] = raw_expression
                    else:
                        content[key] = existing[key]

            if isinstance(content[key], dict):
                self.omit_templated_vars(content[key], existing[key])

            if isinstance(content[key], list):
                for i, item in enumerate(content[key]):
                    if isinstance(item, dict):
                        try:
                            tmp = existing[key][i]
                            self.omit_templated_vars(item, tmp or None)
                        except IndexError:
                            pass

    def process(self, content: dict, existing: dict):
        """
        Process the asset content before writing it to a file.
        """


class ChartAsset(Asset):
    """
    Chart assets.
    """

    path = "charts"
    omitted_vars = [
        "params.dashboards",
        "params.datasource",
        "params.slice_id",
    ]
    raw_vars = ["sqlExpression", "query_context", "translate_column"]

    def process(self, content: dict, existing: dict):
        if not content.get("query_context") and existing:
            content["query_context"] = existing.get("query_context")
        query_context = content["query_context"]
        if query_context is not None and isinstance(query_context, str):
            content["query_context"] = json.loads(query_context)
        # run templated vars again to update query_context
        if existing:
            self.omit_templated_vars(
                content["query_context"], existing.get("query_context")
            )


class DashboardAsset(Asset):
    """
    Dashboard assets.
    """

    path = "dashboards"
    required_vars = ["_roles"]


class DatasetAsset(Asset):
    """
    Dataset assets.
    """

    path = "datasets"
    templated_vars = ["schema", "table_name", "sql"]
    omitted_vars = ["extra.certification"]

    def process(self, content: dict, existing: dict):
        """
        Process the content of the chart asset.
        """
        for column in content.get("columns", []):
            if not column.get("verbose_name"):
                column["verbose_name"] = column["column_name"].replace("_", " ").title()

        for metric in content.get("metrics", []):
            if not metric.get("verbose_name"):
                metric["verbose_name"] = metric["metric_name"].replace("_", " ").title()

        content["sql"] = format_string(
            content["sql"], mode=Mode(dialect_name="clickhouse")
        )


class DatabaseAsset(Asset):
    """
    Database assets.
    """

    path = "databases"
    templated_vars = ["sqlalchemy_uri"]


ASSET_TYPE_MAP = {
    "slice_name": ChartAsset(),
    "dashboard_title": DashboardAsset(),
    "table_name": DatasetAsset(),
    "database_name": DatabaseAsset(),
}


def _validate_asset_file(
    asset_path, content, echo, all_assets_path
):  # pylint: disable=too-many-branches
    """
    Check various aspects of the asset file based on its type.

    Returns the destination path for the file to import to.
    Append last 6 characters of uuid for charts
    """
    orig_filename = os.path.basename(asset_path)

    # make sure to not change the dashboard filename if we happen
    # to have a chart with the same name
    if not content.get("dashboard_title"):
        out_filename_uuid = re.sub(
            r"(_\d*)\.yaml", f"_{content['uuid'][:6]}.yaml", orig_filename
        )
    else:
        out_filename_uuid = re.sub(r"(_\d*)\.yaml", ".yaml", orig_filename)
    content[FILE_NAME_ATTRIBUTE] = out_filename_uuid

    out_path = None
    needs_review = False
    for key, cls in ASSET_TYPE_MAP.items():
        if key in content:
            out_path = cls.get_path(all_assets_path)

            existing = None

            if os.path.exists(os.path.join(out_path, out_filename_uuid)):
                with open(
                    os.path.join(out_path, out_filename_uuid), encoding="utf-8"
                ) as stream:
                    existing = yaml.safe_load(stream)

            for var in cls.get_templated_vars():
                # If this is a variable we expect to be templated,
                # check that it is.
                if (
                    content[var]
                    and not content[var].startswith("{{")
                    and not content[var].startswith("{%")
                ):
                    if existing:
                        content[var] = existing[var]
                        needs_review = False
                    else:
                        echo(
                            click.style(
                                f"WARN: {orig_filename} has "
                                f"{var} set to {content[var]} instead of a "
                                f"setting.",
                                fg="yellow",
                            )
                        )
                        needs_review = True

            for var in cls.get_required_vars():
                # If this variable is required and doesn't exist, warn.
                if var not in content:
                    if existing:
                        content[var] = existing[var]
                        needs_review = False
                    else:
                        echo(
                            click.style(
                                f"WARN: {orig_filename} is missing required "
                                f"item '{var}'!",
                                fg="red",
                            )
                        )
                        needs_review = True

            cls.remove_content(content)
            cls.omit_templated_vars(content, existing)
            cls.process(content, existing)
            # We found the correct class, we can stop looking.
            break

    return out_path, needs_review


def import_superset_assets(
    file, echo, assets_path=ASSETS_PATH
):  # pylint: disable=too-many-locals
    """
    Import assets from a Superset export zip file to the openedx-assets directory.
    """
    written_assets = []
    review_files = set()
    err = 0
    dataset_warn = False

    with ZipFile(file.name) as zip_file:
        for asset_path in zip_file.namelist():
            if "metadata.yaml" in asset_path:
                continue
            with zip_file.open(asset_path) as asset_file:
                content = yaml.safe_load(asset_file)
                out_path, needs_review = _validate_asset_file(
                    asset_path, content, echo, assets_path
                )

                # This can happen if it's an unknown asset type
                if not out_path:
                    continue

                if "dataset" in out_path:
                    dataset_warn = True

                if needs_review:
                    review_files.add(content[FILE_NAME_ATTRIBUTE])

                out_path = os.path.join(out_path, content[FILE_NAME_ATTRIBUTE])
                written_assets.append(out_path)

                # Make sure the various asset subdirectories exist before writing
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as out_f:
                    yaml.dump(content, out_f, encoding="utf-8")

    if review_files:
        echo()
        echo(
            click.style(
                f"{len(review_files)} files had warnings and need review:", fg="red"
            )
        )
        for filename in review_files:
            echo(f"    - {filename}")

        raise SupersetCommandError(
            "Warnings found, please review then run "
            "'tutor aspects check_superset_assets'"
        )

    echo()
    echo(f"Serialized {len(written_assets)} assets")
    if dataset_warn:
        echo()
        echo(
            "WARNING: Datasets were changed, please check if SQL queries need to be updated"
        )

    return err
