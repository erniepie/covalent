# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the GNU Affero General Public License 3.0 (the "License").
# A copy of the License may be obtained with this software package or at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html
#
# Use of this file is prohibited except in compliance with the License. Any
# modifications or derivative works of this file must retain this copyright
# notice, and modified files must contain a notice indicating that they have
# been altered from the originals.
#
# Covalent is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
#
# Relief from the License may be granted by purchasing a commercial license.

"""Mappings between result attributes and DB records"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..._db import models

ATTRIBUTES = {
    "start_time",
    "end_time",
    "results_dir",
    "lattice",
    "dispatch_id",
    "root_dispatch_id",
    "electron_id",
    "status",
    "task_failed",
    "task_cancelled",
    "result",
    "num_nodes",
    "inputs",
    "error",
}

METADATA_KEYS = {
    "start_time",
    "end_time",
    "results_dir",
    "dispatch_id",
    "root_dispatch_id",
    "electron_id",
    "status",
    "num_nodes",
}


ASSET_KEYS = {
    "inputs",
    "result",
    "error",
}

_meta_record_map = {
    "start_time": "started_at",
    "end_time": "completed_at",
    "results_dir": "results_dir",
    "dispatch_id": "dispatch_id",
    "root_dispatch_id": "root_dispatch_id",
    "electron_id": "electron_id",
    "status": "status",
    "num_nodes": "electron_num",
    "completed_electron_num": "completed_electron_num",
}

# Obsoleted by LatticeAsset table
_asset_record_map = {
    "inputs": "inputs_filename",
    "result": "results_filename",
    "error": "error_filename",
}


def _to_pure_meta(session: Session, record: models.Lattice):
    pure_metadata = {k: getattr(record, v) for k, v in _meta_record_map.items()}
    del pure_metadata["completed_electron_num"]

    return pure_metadata


def _to_asset_meta(session: Session, record: models.Lattice):
    # get asset ids
    stmt = select(models.LatticeAsset).where(models.LatticeAsset.lattice_id == record.id)
    lattice_asset_links = session.scalars(stmt).all()
    return {x.key: x.asset_id for x in lattice_asset_links}


def _to_db_meta(session: Session, record: models.Lattice):
    db_metadata = {
        "lattice_id": record.id,
        "electron_id": record.electron_id,
        "storage_path": record.storage_path,
        "storage_type": record.storage_type,
        "completed_electron_num": record.completed_electron_num,
    }
    return db_metadata
