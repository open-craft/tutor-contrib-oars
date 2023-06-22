"""Implements OARS plugin via Tutor Plugin API v1."""
from __future__ import annotations

import os
import os.path
import random
import string
from glob import glob

import bcrypt
import click
import pkg_resources
from tutor import hooks

from .__about__ import __version__

########################################
# CONFIGURATION
########################################

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        # Add your new settings that have default values here.
        # Each new setting is a pair: (setting_name, default_value).
        # Prefix your setting names with 'OARS_'.
        ("OARS_VERSION", __version__),
        ("DOCKER_IMAGE_OARS", "python:3.8"),
        # ClickHouse xAPI settings
        ("OARS_XAPI_DATABASE", "xapi"),
        ("OARS_RAW_XAPI_TABLE", "xapi_events_all"),
        ("OARS_XAPI_TRANSFORM_MV", "xapi_events_all_parsed_mv"),
        ("OARS_XAPI_TABLE", "xapi_events_all_parsed"),
        # ClickHouse top-level materialized views
        ("OARS_ENROLLMENT_TRANSFORM_MV", "enrollment_events_mv"),
        ("OARS_ENROLLMENT_EVENTS_TABLE", "enrollment_events"),
        ("OARS_VIDEO_PLAYBACK_TRANSFORM_MV", "video_playback_events_mv"),
        ("OARS_VIDEO_PLAYBACK_EVENTS_TABLE", "video_playback_events"),
        ("OARS_PROBLEM_TRANSFORM_MV", "problem_events_mv"),
        ("OARS_PROBLEM_EVENTS_TABLE", "problem_events"),
        ("OARS_NAVIGATION_TRANSFORM_MV", "navigation_events_mv"),
        ("OARS_NAVIGATION_EVENTS_TABLE", "navigation_events"),
        # ClickHouse event sink settings
        ("OARS_EVENT_SINK_DATABASE", "event_sink"),
        ("OARS_EVENT_SINK_NODES_TABLE", "course_blocks"),
        ("OARS_EVENT_SINK_RELATIONSHIPS_TABLE", "course_relationships"),
        ("OARS_EVENT_SINK_OVERVIEWS_TABLE", "course_overviews"),
        ("OARS_EVENT_SINK_CLICKHOUSE_TIMEOUT_SECS", "5"),
        # MySQL dataset settings
        ("OARS_SUPERSET_ENROLLMENTS_TABLE", "Course Enrollments Overview"),
        # Make sure LMS / CMS have event-routing-backends installed
        (
            "OPENEDX_EXTRA_PIP_REQUIREMENTS",
            [
                "openedx-event-sink-clickhouse==0.1.0",
                "edx-event-routing-backends==5.3.1",
            ],
        ),
        ######################
        # ClickHouse Settings
        ("CLICKHOUSE_VERSION", __version__),
        ("CLICKHOUSE_HOST", "clickhouse"),
        ("CLICKHOUSE_PORT", "9000"),
        ("CLICKHOUSE_HTTP_PORT", "8123"),
        ("CLICKHOUSE_HTTPS_PORT", "8443"),
        ("DOCKER_IMAGE_CLICKHOUSE", "clickhouse/clickhouse-server:23.3"),
        # This can be used to override some configuration values in
        # via "docker_config.xml" file, which will be read from a
        # mount on /etc/clickhouse-server/config.d/ on startup.
        # See https://clickhouse.com/docs/en/operations/configuration-files
        #
        # This default allows connecting to Clickhouse when run as a
        # standalone docker container, instead of through docker-compose.
        (
            "CLICKHOUSE_EXTRA_XML_CONFIG",
            """
    <listen_host>::</listen_host>
    <listen_host>0.0.0.0</listen_host>
    <listen_try>1</listen_try>
        """,
        ),
        ######################
        # Ralph Settings
        ("RALPH_VERSION", __version__),
        ("DOCKER_IMAGE_RALPH", "docker.io/fundocker/ralph:3.6.0"),
        # Change to https:// if the public interface to it is secure
        ("RALPH_RUN_HTTPS", False),
        ("RALPH_HOST", "ralph"),
        ("RALPH_PORT", "8100"),
        ("RALPH_ENABLE_PUBLIC_URL", False),
        ("RALPH_SENTRY_DSN", ""),
        ("RALPH_EXECUTION_ENVIRONMENT", "development"),
        ("RALPH_SENTRY_CLI_TRACES_SAMPLE_RATE", 1.0),
        ("RALPH_SENTRY_LRS_TRACES_SAMPLE_RATE", 0.1),
        ("RALPH_SENTRY_IGNORE_HEALTH_CHECKS", True),
        ("RUN_RALPH", True),
        ######################
        # Superset Settings
        ("SUPERSET_VERSION", __version__),
        ("SUPERSET_TAG", "2.0.1"),
        ("SUPERSET_HOST", "superset.{{ LMS_HOST }}"),
        ("SUPERSET_PORT", "8088"),
        ("SUPERSET_DB_DIALECT", "mysql"),
        ("SUPERSET_DB_HOST", "{{ MYSQL_HOST }}"),
        ("SUPERSET_DB_PORT", "{{ MYSQL_PORT }}"),
        ("SUPERSET_DB_NAME", "superset"),
        ("SUPERSET_DB_USERNAME", "superset"),
        ("SUPERSET_OAUTH2_ACCESS_TOKEN_PATH", "/oauth2/access_token/"),
        ("SUPERSET_OAUTH2_AUTHORIZE_PATH", "/oauth2/authorize/"),
        (
            "SUPERSET_OPENEDX_COURSES_LIST_PATH",
            "/api/courses/v1/courses/?permissions={permission}&username={username}",
        ),
        ("SUPERSET_OPENEDX_ROLE_NAME", "Open edX"),
        ("SUPERSET_ADMIN_EMAIL", "admin@openedx.org"),
        # Set to 0 to have no row limit.
        ("SUPERSET_ROW_LIMIT", 100_000),
        ("SUPERSET_SENTRY_DSN", ""),
        # List of dicts
        # [{
        #    "path": "path-in-the-superset-pod",
        #    "name": "volume-name",
        #    "config_map_name": "config-map-name",
        #    "config_map_folder": "path-to-template-folder",
        # }]
        ("SUPERSET_EXTRA_VOLUMES", []),
        ("SUPERSET_EXTRA_DEV_VOLUMES", []),
        ("RUN_SUPERSET", True),
        (
            "SUPERSET_TALISMAN_CONFIG",
            {
                "content_security_policy": {
                    "default-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
                    "img-src": ["'self'", "data:"],
                    "worker-src": ["'self'", "blob:"],
                    "connect-src": [
                        "'self'",
                        "https://api.mapbox.com",
                        "https://events.mapbox.com",
                    ],
                    "object-src": "'none'",
                }
            },
        ),
        ("SUPERSET_TALISMAN_ENABLED", True),
        ("SUPERSET_DEFAULT_LOCALE", "en"),
        (
            "SUPERSET_SUPPORTED_LANGUAGES",
            {
                "en": {"flag": "us", "name": "English"},
                "es": {"flag": "es", "name": "Spanish"},
            },
        ),
        ######################
        # dbt Settings
        # For the most part you shouldn't have to touch these
        # DBT_PROFILE_* settings get passed into the dbt_profile.yml file.
        # For now we are pulling this from github, which should allow maximum
        # flexibility for forking, running branches, specific versions, etc.
        ("DBT_REPOSITORY", "https://github.com/openedx/oars-dbt"),
        # This is a pip compliant list of Python packages to install to run dbt
        # make sure packages with versions are enclosed in double quotes
        ("DBT_PACKAGES", '"dbt-core==1.4.0" "dbt-clickhouse==1.4.1"'),
        # If set, DDL/table operations will be executed with the `ON CLUSTER` clause
        # using this cluster. This has not been tested with OARS and is unlikely to
        # work.
        ("DBT_PROFILE_CLUSTER", ""),
        # Validate TLS certificate if using TLS/SSL
        ("DBT_PROFILE_VERIFY", "True"),
        # Use TLS (native protocol) or HTTPS (http protocol)
        ("DBT_PROFILE_SECURE", "False"),
        # Number of times to retry a "retryable" database exception (such as a 503
        # 'Service Unavailable' error)
        ("DBT_PROFILE_RETRIES", "3"),
        # Use gzip compression if truthy (http), or compression type for a native
        # connection
        ("DBT_PROFILE_COMPRESSION", "lz4"),
        # Timeout in seconds to establish a connection to ClickHouse
        ("DBT_PROFILE_CONNECT_TIMEOUT", "10"),
        # Timeout in seconds to receive data from the ClickHouse server
        ("DBT_PROFILE_SEND_RECEIVE_TIMEOUT", "300"),
        # Use specific settings designed to improve operation on replicated databases
        # (recommended for ClickHouse Cloud)
        ("DBT_PROFILE_CLUSTER_MODE", "False"),
        # Use the experimental `delete+insert` as the default incremental strategy.
        ("DBT_PROFILE_USE_LW_DELETES", "False"),
        # Validate that clickhouse support the atomic EXCHANGE TABLES command.  (Not
        # needed for most ClickHouse versions)
        ("DBT_PROFILE_CHECK_EXCHANGE", "False"),
        # A dictionary/mapping of custom ClickHouse settings for the connection -
        # default is empty.
        ("DBT_PROFILE_CUSTOM_SETTINGS", ""),
        # Allows the connection to understand the JSON type
        ("DBT_PROFILE_ALLOW_EXPERIMENTAL_OBJECT_TYPE", "True"),
        # Timeout for server ping
        ("DBT_PROFILE_SYNC_REQUEST_TIMEOUT", "5"),
        # Compression block size if compression is enabled, this is the default value
        ("DBT_PROFILE_COMPRESS_BLOCK_SIZE", "1048576"),
    ]
)

# Ralph requires us to write out a file with pre-encrypted values, so we encrypt
# them here per: https://openfun.github.io/ralph/api/#creating_a_credentials_file
#
# They will remain unchanged between config saves as usual and the unencryted
# passwords will still be able to be printed.
RALPH_ADMIN_PASSWORD = "".join(random.choice(string.ascii_lowercase) for i in range(36))
RALPH_LMS_PASSWORD = "".join(random.choice(string.ascii_lowercase) for i in range(36))
RALPH_ADMIN_HASHED_PASSWORD = bcrypt.hashpw(
    RALPH_ADMIN_PASSWORD.encode(), bcrypt.gensalt()
).decode("ascii")
RALPH_LMS_HASHED_PASSWORD = bcrypt.hashpw(
    RALPH_LMS_PASSWORD.encode(), bcrypt.gensalt()
).decode("ascii")

hooks.Filters.CONFIG_UNIQUE.add_items(
    [
        ("OARS_CLICKHOUSE_LRS_USER", "ch_lrs"),
        ("OARS_CLICKHOUSE_LRS_PASSWORD", "{{ 24|random_string }}"),
        # Report user is used by Superset to read from ClickHouse tables
        ("OARS_CLICKHOUSE_REPORT_USER", "ch_report"),
        ("OARS_CLICKHOUSE_REPORT_PASSWORD", "{{ 24|random_string }}"),
        # CMS user is used by CMS to insert into event sink tables
        ("OARS_CLICKHOUSE_CMS_USER", "ch_cms"),
        ("OARS_CLICKHOUSE_CMS_PASSWORD", "{{ 24|random_string }}"),
        ######################
        # ClickHouse Settings
        ("CLICKHOUSE_ADMIN_USER", "ch_admin"),
        ("CLICKHOUSE_ADMIN_PASSWORD", "{{ 24|random_string }}"),
        ("CLICKHOUSE_SECURE_CONNECTION", False),
        ("RUN_CLICKHOUSE", True),
        ######################
        # Ralph Settings
        ("RALPH_ADMIN_USERNAME", "ralph"),
        ("RALPH_ADMIN_PASSWORD", RALPH_ADMIN_PASSWORD),
        ("RALPH_ADMIN_HASHED_PASSWORD", RALPH_ADMIN_HASHED_PASSWORD),
        ("RALPH_LMS_USERNAME", "lms"),
        ("RALPH_LMS_PASSWORD", RALPH_LMS_PASSWORD),
        ("RALPH_LMS_HASHED_PASSWORD", RALPH_LMS_HASHED_PASSWORD),
        ######################
        # Superset Settings
        ("SUPERSET_SECRET_KEY", "{{ 24|random_string }}"),
        ("SUPERSET_DB_PASSWORD", "{{ 24|random_string }}"),
        ("SUPERSET_OAUTH2_CLIENT_ID", "{{ 16|random_string }}"),
        ("SUPERSET_OAUTH2_CLIENT_SECRET", "{{ 16|random_string }}"),
        ("SUPERSET_ADMIN_USERNAME", "{{ 12|random_string }}"),
        ("SUPERSET_ADMIN_PASSWORD", "{{ 24|random_string }}"),
    ]
)

hooks.Filters.CONFIG_OVERRIDES.add_items(
    [
        # Danger zone!
        # Add values to override settings from Tutor core or other plugins here.
        # Each override is a pair: (setting_name, new_value). For example:
        ### ("PLATFORM_NAME", "My platform"),
        # Superset overrides
        ("SUPERSET_XAPI_DASHBOARD_SLUG", "openedx-xapi"),
        ("SUPERSET_ROW_LEVEL_SECURITY_XAPI_GROUP_KEY", "xapi_course_id"),
        ("SUPERSET_ROW_LEVEL_SECURITY_ENROLLMENTS_GROUP_KEY", "enrollments_course_id"),
        (
            "SUPERSET_EXTRA_VOLUMES",
            [
                {
                    "path": "/app/oars/data/superset/databases",
                    "name": "databases",
                    "config_map_name": "databases-oars",
                    "config_map_folder": "oars/apps/data/superset/databases",
                },
                {
                    "path": "/app/oars/data/superset/dashboards",
                    "name": "dashboards",
                    "config_map_name": "dashboards-oars",
                    "config_map_folder": "oars/apps/data/superset/dashboards",
                },
                {
                    "path": "/app/oars/data/superset/datasets/OpenedX_MySQL",
                    "name": "datasets-mysql",
                    "config_map_name": "datasets-mysql-oars",
                    "config_map_folder": "oars/apps/data/superset/datasets/OpenedX_MySQL",
                },
                {
                    "path": "/app/oars/data/superset/datasets/OpenedX_Clickhouse",
                    "name": "datasets-clickhouse",
                    "config_map_name": "datasets-clickhouse-oars",
                    "config_map_folder": "oars/apps/data/superset/datasets/OpenedX_Clickhouse",
                },
                {
                    "path": "/app/oars/data/superset/charts",
                    "name": "charts",
                    "config_map_name": "charts-oars",
                    "config_map_folder": "oars/apps/data/superset/charts",
                },
                {
                    "path": "/app/oars/data/superset/",
                    "name": "metadata",
                    "config_map_name": "metadata-oars",
                    "config_map_folder": "oars/apps/data/superset/",
                },
            ],
        ),
        (
            "SUPERSET_EXTRA_DEV_VOLUMES",
            ["../../env/plugins/oars/apps/data/superset/:/app/oars/data/superset/"],
        ),
    ]
)


########################################
# INITIALIZATION TASKS
########################################

# To add a custom initialization task, create a bash script template under:
# tutoroars/templates/oars/jobs/init/
# and then add it to the MY_INIT_TASKS list. Each task is in the format:
# ("<service>", ("<path>", "<to>", "<script>", "<template>"))
MY_INIT_TASKS: list[tuple[str, tuple[str, ...], int]] = [
    ("mysql", ("oars", "jobs", "init", "superset", "init-mysql.sh"), 92),
    ("superset", ("oars", "jobs", "init", "superset", "init-superset.sh"), 93),
    ("lms", ("oars", "jobs", "init", "superset", "init-openedx.sh"), 94),
    ("clickhouse", ("oars", "jobs", "init", "clickhouse", "init-clickhouse.sh"), 95),
    (
        "clickhouse",
        ("oars", "jobs", "init", "clickhouse", "oars_init_schemas_tables_users.sh"),
        96,
    ),
    ("oars", ("oars", "jobs", "init", "dbt", "init-dbt.sh"), 97),
    ("superset", ("oars", "jobs", "init", "superset", "superset-init-security.sh"), 99),
    ("lms", ("oars", "jobs", "init", "lms", "configure-oars-lms.sh"), 100),
    (
        "superset",
        ("oars", "jobs", "init", "superset", "superset-api-dashboard.sh"),
        101,
    ),
]


# For each task added to MY_INIT_TASKS, we load the task template
# and add it to the CLI_DO_INIT_TASKS filter, which tells Tutor to
# run it as part of the `init` job.
for service, template_path, priority in MY_INIT_TASKS:
    full_path: str = pkg_resources.resource_filename(
        "tutoroars", os.path.join("templates", *template_path)
    )
    with open(full_path, encoding="utf-8") as init_task_file:
        init_task: str = init_task_file.read()
    hooks.Filters.CLI_DO_INIT_TASKS.add_item((service, init_task), priority=priority)


########################################
# DOCKER IMAGE MANAGEMENT
########################################


# Images to be built by `tutor images build`.
# Each item is a quadruple in the form:
#     ("<tutor_image_name>", ("path", "to", "build", "dir"), "<docker_image_tag>", "<build_args>")
hooks.Filters.IMAGES_BUILD.add_items(
    [
        # To build `myimage` with `tutor images build myimage`,
        # you would add a Dockerfile to templates/oars/build/myimage,
        # and then write:
        ### (
        ###     "myimage",
        ###     ("plugins", "oars", "build", "myimage"),
        ###     "docker.io/myimage:{{ OARS_VERSION }}",
        ###     (),
        ### ),
    ]
)


# Images to be pulled as part of `tutor images pull`.
# Each item is a pair in the form:
#     ("<tutor_image_name>", "<docker_image_tag>")
hooks.Filters.IMAGES_PULL.add_items(
    [
        # To pull `myimage` with `tutor images pull myimage`, you would write:
        ### (
        ###     "myimage",
        ###     "docker.io/myimage:{{ OARS_VERSION }}",
        ### ),
    ]
)


# Images to be pushed as part of `tutor images push`.
# Each item is a pair in the form:
#     ("<tutor_image_name>", "<docker_image_tag>")
hooks.Filters.IMAGES_PUSH.add_items(
    [
        # To push `myimage` with `tutor images push myimage`, you would write:
        ### (
        ###     "myimage",
        ###     "docker.io/myimage:{{ OARS_VERSION }}",
        ### ),
    ]
)


########################################
# TEMPLATE RENDERING
# (It is safe & recommended to leave
#  this section as-is :)
########################################

hooks.Filters.ENV_TEMPLATE_ROOTS.add_items(
    # Root paths for template files, relative to the project root.
    [
        pkg_resources.resource_filename("tutoroars", "templates"),
    ]
)

hooks.Filters.ENV_TEMPLATE_TARGETS.add_items(
    # For each pair (source_path, destination_path):
    # templates at ``source_path`` (relative to your ENV_TEMPLATE_ROOTS) will be
    # rendered to ``source_path/destination_path`` (relative to your Tutor environment).
    # For example, ``tutoroars/templates/oars/build``
    # will be rendered to ``$(tutor config printroot)/env/plugins/oars/build``.
    [
        ("oars/build", "plugins"),
        ("oars/apps", "plugins"),
    ],
)


########################################
# PATCH LOADING
# (It is safe & recommended to leave
#  this section as-is :)
########################################

# For each file in tutoroars/patches,
# apply a patch based on the file's name and contents.
for path in glob(
    os.path.join(
        pkg_resources.resource_filename("tutoroars", "patches"),
        "*",
    )
):
    with open(path, encoding="utf-8") as patch_file:
        hooks.Filters.ENV_PATCHES.add_item((os.path.basename(path), patch_file.read()))


########################################
# CUSTOM JOBS (a.k.a. "do-commands")
########################################
# Ex: "tutor local do load-xapi-test-data"
@click.command()
@click.option("-n", "--num_batches", default=100)
@click.option("-s", "--batch_size", default=100)
def load_xapi_test_data(num_batches: int, batch_size: int) -> list[tuple[str, str]]:
    """
    Job that loads bogus test xAPI data to ClickHouse via Ralph.
    """
    return [
        (
            "oars",
            "echo 'Making demo xapi script executable...' && "
            "chmod +x /app/oars/scripts/oars/clickhouse-demo-xapi-data.sh && "
            "echo 'Done. Running script...' && "
            f"bash /app/oars/scripts/oars/clickhouse-demo-xapi-data.sh {num_batches}"
            f" {batch_size} && "
            "echo 'Done!';",
        ),
    ]


# Ex: "tutor local do dbt "
@click.command(context_settings={"ignore_unknown_options": True})
@click.option(
    "-c",
    "--command",
    default="run",
    type=click.UNPROCESSED,
    help="""The full dbt command to run configured ClickHouse database, wrapped in
         double quotes. The list of commands can be found in the CLI section here:
         https://docs.getdbt.com/reference/dbt-commands
         
         Examples: 
         
         tutor local do dbt -c "test"
         
         tutor local do dbt -c "run -m enrollments_by_day --threads 4"
         """,
)
def dbt(command: string) -> list[tuple[str, str]]:
    """
    Job that proxies dbt commands to a container which runs them against ClickHouse.
    """
    return [
        (
            "oars",
            "echo 'Making dbt script executable...' && "
            "chmod +x /app/oars/scripts/oars/dbt.sh && "
            f"echo 'Running dbt {command}' && "
            f"bash /app/oars/scripts/oars/dbt.sh {command} && "
            "echo 'Done!';",
        ),
    ]


# Add the command function to CLI_DO_COMMANDS:
hooks.Filters.CLI_DO_COMMANDS.add_item(load_xapi_test_data)
hooks.Filters.CLI_DO_COMMANDS.add_item(dbt)


#######################################
# CUSTOM CLI COMMANDS
#######################################

# Your plugin can also add custom commands directly to the Tutor CLI.
# These commands are run directly on the user's host computer
# (unlike jobs, which are run in containers).

# To define a command group for your plugin, you would define a Click
# group and then add it to CLI_COMMANDS:


### @click.group()
### def oars() -> None:
###     pass


### hooks.Filters.CLI_COMMANDS.add_item(oars)


# Then, you would add subcommands directly to the Click group, for example:


### @oars.command()
### def example_command() -> None:
###     """
###     This is helptext for an example command.
###     """
###     print("You've run an example command.")


# This would allow you to run:
#   $ tutor oars example-command
