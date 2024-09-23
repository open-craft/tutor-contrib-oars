"""Delete all unused Aspects assets from Superset tables"""
import logging
from flask import g

from superset import security_manager
from superset.extensions import db
from superset.models.slice import Slice
from superset.connectors.sqla.models import SqlaTable
from superset.tags.models import TaggedObject, ObjectType
from superset.commands.chart.delete import DeleteChartCommand
from superset.commands.dataset.delete import DeleteDatasetCommand
from sqlalchemy.exc import NoResultFound
from superset.commands.exceptions import CommandInvalidError

logger = logging.getLogger("delete_assets")
PYTHONPATH = "/app/pythonpath"

ASSET_TABLES = {'charts': Slice, 'datasets': SqlaTable}
ASSET_NAME_COLUMN = {'charts': 'slice_name', 'datasets': 'table_name'}
ASSET_COMMANDS = {'charts': DeleteChartCommand, 'datasets': DeleteDatasetCommand}
OBJECT_TYPES = {'charts': ObjectType.chart, 'datasets': ObjectType.dataset} 

def delete_assets(unused_uuids, translated_asset_uuids):
    """Delete unused assets and their translated versions"""
    for type in unused_uuids:
        id_list = []
        asset_list = set()
        for uuid in unused_uuids[type] or []:
            try:
                row = db.session.query(ASSET_TABLES[type]).filter_by(uuid=uuid).one()
                id_list.append(row.id)
                asset_list.add(getattr(row,ASSET_NAME_COLUMN[type]))

                if uuid in translated_asset_uuids:
                    for child_uuid in translated_asset_uuids[uuid]:
                        row = db.session.query(ASSET_TABLES[type]).filter_by(uuid=child_uuid).one()
                        id_list.append(row.id)
                        asset_list.add(getattr(row,ASSET_NAME_COLUMN[type]))
            except NoResultFound:
                continue
        
        if len(id_list) > 0:
            try:
                logger.warning(f'Deleting the following {type}: ')
                logger.warning(asset_list)

                # Force our use to the admin user to prevent errors on delete
                g.user = security_manager.find_user(username="{{SUPERSET_ADMIN_USERNAME}}")

                # Delete tagged object rows first because the DeleteCommands are currently
                # broken in Superset if there is more than 1 tag per asset
                for id in id_list:
                    rows = db.session.query(TaggedObject).filter_by(object_id = id).all()
                    for row in rows:
                        db.session.delete(row)

                command = ASSET_COMMANDS[type](id_list)
                command.run()

            except CommandInvalidError as ex:
                logger.error("An error occurred: %s", ex.normalized_messages())
