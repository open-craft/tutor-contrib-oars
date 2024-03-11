import math
import os
import shutil
import yaml

class TranslatableAsset:
    translatable_attributes = []

    def __init__(self, asset: dict):
        self.asset = asset
        for key in ASSET_FOLDER_MAPPING:
            if key in asset:
                self.asset_type = ASSET_FOLDER_MAPPING[key]
                break

    def extract_text(self):
        """
        Extract text from an asset.
        """
        strings = []
        for var_path in self.translatable_attributes:
            strings.extend(self.translate_var(self.asset, var_path.split(".")))

        return strings

    def translate_var(self, content, var_path):
        """
        Helper method to remove content from the content dict.
        """
        if not content:
            return []
        if len(var_path) == 1:
            if isinstance(content, list):
                 strings = []
                 for item in content:
                     strings.append(item.get(var_path[0], ""))
                 return strings
            string = [content.get(var_path[0], "")]
            return string or []
        else:
            if isinstance(content, list):
                strings = []
                for item in content:
                    strings.extend(self.translate_var(item, var_path[1:]))
                return strings
            if isinstance(content, dict):
                if var_path[0] == "*":
                    strings = []
                    for key, value in content.items():
                        strings.extend(self.translate_var(value, var_path[1:]))
                    return strings
                return self.translate_var(content.get(var_path[0]), var_path[1:])
            else:
                print("Could not translate var_path: ", var_path, content)
                return []


class DashboardAsset(TranslatableAsset):
    translatable_attributes = [
        "dashboard_title",
        "description",
        "metadata.native_filter_configuration.name",
        "metadata.native_filter_configuration.description",
        "position.*.meta.text",
        "position.*.meta.code",
    ]

class ChartAsset(TranslatableAsset):
    translatable_attributes = [
        "slice_name",
        "description",
        "params.x_axis_label",
        "params.y_axis_label",
    ]

class DatasetAsset(TranslatableAsset):
    translatable_attributes = [
        "metrics.verbose_name",
        "columns.verbose_name",
    ]


ASSET_FOLDER_MAPPING = {
    "dashboard_title": ("dashboards", DashboardAsset),
    "slice_name": ("charts", ChartAsset),
    "table_name": ("datasets", DatasetAsset),
}

BASE_PATH = "tutoraspects/templates/aspects/build/aspects-superset/"

def get_text_for_translations(root_path):
    assets_path = (
        os.path.join(
            root_path,
            BASE_PATH,
            "openedx-assets/assets/"
        )
    )

    print(f"Assets path: {assets_path}")

    strings = []

    for root, dirs, files in os.walk(assets_path):
        for file in files:
            if not file.endswith(".yaml"):
                continue

            path = os.path.join(root, file)
            with open(path, 'r') as asset_file:
                asset_str = asset_file.read()

            asset = yaml.safe_load(asset_str)
            strings.extend(mark_text_for_translation(asset))

    with open(BASE_PATH + "localization/datasets_strings.yaml", 'r') as file:
        dataset_strings = yaml.safe_load(file.read())
        for key in dataset_strings:
            strings.extend(dataset_strings[key])
            print(f"Extracted {len(dataset_strings[key])} strings for dataset {key}")
    return strings


def mark_text_for_translation(asset):
    """
    For every asset extract the text and mark it for translation
    """

    for key, (asset_type, Asset) in ASSET_FOLDER_MAPPING.items():
        if key in asset:
            strings = Asset(asset).extract_text()
            print(
                f"Extracted {len(strings)} strings from {asset_type} {asset.get('uuid')}"
            )
            return strings

    # If we get here it's a type of asset that we don't translate, return nothing.
    return []


def compile_translations(root_path):
    """
    Combine translated files into the single file we use for translation.

    This should be called after we pull translations using Atlas, see the
    pull_translations make target.
    """
    translations_path = (
        os.path.join(
            root_path,
            "tutoraspects/templates/aspects/apps/superset/conf/locale"
        )
    )

    all_translations = {}
    for root, dirs, files in os.walk(translations_path):
        for file in files:
            if not file.endswith(".yaml"):
                continue

            lang = root.split(os.sep)[-1]
            path = os.path.join(root, file)
            with open(path, 'r') as asset_file:
                loc_str = asset_file.read()
            loaded_strings = yaml.safe_load(loc_str)

            # Sometimes translated files come back with "en" as the top level
            # key, but still translated correctly.
            try:
                all_translations[lang] = loaded_strings[lang]
            except KeyError:
                all_translations[lang] = loaded_strings["en"]

    out_path = (
        os.path.join(
            root_path,
            "tutoraspects/templates/aspects/build/aspects-superset/localization/locale.yaml"
        )
    )

    print(f"Writing all translations out to {out_path}")
    with open(out_path, 'w') as outfile:
        outfile.write("---\n")
        # If we don't use an extremely large width, the jinja in our translations
        # can be broken by newlines. So we use the largest number there is.
        yaml.dump(all_translations, outfile, width=math.inf, sort_keys=True)
        outfile.write("\n{{ patch('superset-extra-asset-translations')}}\n")

    # We remove these files to avoid confusion about where translations are coming
    # from, and because otherwise we will need to re-save them with the large
    # width as above to avoid Jinja parsing errors.
    print("Removing downloaded translations files... ")
    shutil.rmtree(translations_path)


def extract_translations(root_path):
    """
    This gathers all translatable text from the Superset assets.

    An English locale file is created, which openedx-translations will send to
    Transifex for translation.
    """
    # The expectation is that this will end up at the site root, which should
    # be cwd for make targets. This is a temporary file used only in the Github
    # action in openedx-translations.
    translation_file = "transifex_input.yaml"

    print("Gathering text for translations...")
    STRINGS = set(get_text_for_translations(root_path))
    print(f"Extracted {len(STRINGS)} strings for translation.")
    translations = {'en': {}}

    for string in STRINGS:
        translations['en'][string] = string

    print(f"Writing English strings to {translation_file}")
    with open(translation_file, "w") as file:
        file.write(yaml.dump(translations))

    print("Done compiling translations.")
