#!/usr/bin/env bash
set -e

#
# Always install local overrides first
#
/usr/bin/env bash /app/docker/docker-bootstrap.sh

# Set up a Row-Level Security filter to enforce course-based access restrictions.
# Note: there are no cli commands or REST API endpoints to help us with this,
# so we have to pipe python code directly into the superset shell. Yuck!
superset shell <<EOF
from superset.connectors.sqla.models import (
    RowLevelSecurityFilter,
    RLSFilterRoles,
    SqlaTable,
)
from superset.utils.core import RowLevelSecurityFilterType
from superset.extensions import security_manager
from superset.migrations.shared.security_converge import Role

session = security_manager.get_session()

# Fetch the Open edX role
role_name = "{{SUPERSET_OPENEDX_ROLE_NAME}}"
openedx_role = session.query(Role).filter(Role.name == role_name).first()
assert openedx_role, "{{SUPERSET_OPENEDX_ROLE_NAME}} role doesn't exist yet?"

for (schema, table_name, group_key, clause, filter_type) in (
    (
        "{{OARS_XAPI_DATABASE}}",
        "{{OARS_XAPI_TABLE}}",
        "{{SUPERSET_ROW_LEVEL_SECURITY_XAPI_GROUP_KEY}}",
        {% raw %}
        '{{can_view_courses(current_username(), "splitByChar(\'/\', course_id)[-1]")}}',
        {% endraw %}
        RowLevelSecurityFilterType.REGULAR,
    ),
    (
        "{{OPENEDX_MYSQL_DATABASE}}",
        "{{OARS_SUPERSET_ENROLLMENTS_TABLE}}",
        "{{SUPERSET_ROW_LEVEL_SECURITY_ENROLLMENTS_GROUP_KEY}}",
        {% raw %}
        '{{can_view_courses(current_username(), "course_key")}}',
        {% endraw %}
        RowLevelSecurityFilterType.REGULAR,
    ),
):
    # Fetch the table we want to restrict access to
    table = session.query(SqlaTable).filter(
        SqlaTable.schema == schema
    ).filter(
        SqlaTable.table_name == table_name
    ).first()
    assert table, f"{schema}.{table_name} table doesn't exist yet?"
    # See if the Row Level Security Filter already exists
    rlsf = (
        session.query(
            RowLevelSecurityFilter
        ).filter(
            RLSFilterRoles.c.role_id.in_((openedx_role.id,))
        ).filter(
            RowLevelSecurityFilter.group_key == group_key
        )
    ).first()
    # If it doesn't already exist, create one
    if rlsf:
        create = False
    else:
        create = True
        rlsf = RowLevelSecurityFilter()
    # Sync the fields to our expectations
    rlsf.filter_type = filter_type
    rlsf.group_key = group_key
    rlsf.tables = [table]
    rlsf.clause = clause
    # Create if needed
    if create:
        session.add(rlsf)
        # ...and commit, so we are sure to have an rlsf.id
        session.commit()
    # Add the filter role if needed
    rls_filter_roles = (
        session.query(
            RLSFilterRoles
        ).filter(
            RLSFilterRoles.c.role_id == openedx_role.id
        ).filter(
            RLSFilterRoles.c.rls_filter_id == rlsf.id
        )
    )
    if not rls_filter_roles.count():
        session.execute(RLSFilterRoles.insert(), [
            dict(
                role_id=openedx_role.id,
                rls_filter_id=rlsf.id
            )
        ])
        session.commit()

print("Successfully create row-level security filters.")

EOF
# The blank line above EOF is critical -- don't remove it.
# And we can't have any indented blank lines for some reason, with code piped into the superset shell
