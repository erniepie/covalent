# Copyright 2023 Agnostiq Inc.
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


"""Functions to transform ResultSchema -> Result"""

import json
import os
from typing import Dict, Tuple

from sqlalchemy.orm import Session

from covalent._shared_files import logger
from covalent._shared_files.schemas.electron import (
    ASSET_FILENAME_MAP,
    ELECTRON_CALL_AFTER_FILENAME,
    ELECTRON_CALL_BEFORE_FILENAME,
    ELECTRON_DEPS_FILENAME,
    ELECTRON_ERROR_FILENAME,
    ELECTRON_FUNCTION_FILENAME,
    ELECTRON_FUNCTION_STRING_FILENAME,
    ELECTRON_RESULTS_FILENAME,
    ELECTRON_STDERR_FILENAME,
    ELECTRON_STDOUT_FILENAME,
    ELECTRON_STORAGE_TYPE,
    ELECTRON_VALUE_FILENAME,
    ElectronAssets,
    ElectronSchema,
)

from ..._db import models
from ..._db.write_result_to_db import get_electron_type
from ..._object_store.base import BaseProvider
from ..asset import Asset
from ..electron import ElectronMeta
from ..lattice import Lattice

app_log = logger.app_log


def import_electron(
    session: Session,
    dispatch_id: str,
    e: ElectronSchema,
    lat: Lattice,
    object_store: BaseProvider,
    job_id: int,
) -> Tuple[models.Electron, ElectronSchema]:
    """Returns (electron_id, ElectronSchema)"""

    electron_assets, asset_recs = import_electron_assets(
        session,
        dispatch_id,
        e,
        object_store,
    )

    # Hack for legacy DB columns
    node_storage_path = asset_recs["function"].storage_path

    electron_kwargs = _get_electron_meta(e, lat, node_storage_path, job_id)
    electron_row = ElectronMeta.insert(session, insert_kwargs=electron_kwargs, flush=False)

    return (
        electron_row,
        asset_recs,
        ElectronSchema(id=e.id, metadata=e.metadata, assets=electron_assets),
    )


def _get_electron_meta(
    e: ElectronSchema, lat: Lattice, node_storage_path: str, job_id: int
) -> dict:
    kwargs = {
        "transport_graph_node_id": e.id,
        "task_group_id": e.metadata.task_group_id,
        "name": e.metadata.name,
        "executor": e.metadata.executor,
        "executor_data": json.dumps(e.metadata.executor_data),
        "status": e.metadata.status,
        "started_at": e.metadata.start_time,
        "completed_at": e.metadata.end_time,
    }
    db_kwargs = {
        "parent_lattice_id": lat.metadata.primary_key,
        "type": get_electron_type(e.metadata.name),
        "job_id": job_id,
    }
    kwargs.update(db_kwargs)

    legacy_kwargs = {
        "storage_type": ELECTRON_STORAGE_TYPE,
        "storage_path": str(node_storage_path),
        "function_filename": ELECTRON_FUNCTION_FILENAME,
        "function_string_filename": ELECTRON_FUNCTION_STRING_FILENAME,
        "results_filename": ELECTRON_RESULTS_FILENAME,
        "value_filename": ELECTRON_VALUE_FILENAME,
        "stdout_filename": ELECTRON_STDOUT_FILENAME,
        "stderr_filename": ELECTRON_STDERR_FILENAME,
        "error_filename": ELECTRON_ERROR_FILENAME,
        "deps_filename": ELECTRON_DEPS_FILENAME,
        "call_before_filename": ELECTRON_CALL_BEFORE_FILENAME,
        "call_after_filename": ELECTRON_CALL_AFTER_FILENAME,
    }
    kwargs.update(legacy_kwargs)
    return kwargs


def import_electron_assets(
    session: Session,
    dispatch_id,
    e: ElectronSchema,
    object_store: BaseProvider,
) -> Tuple[ElectronAssets, Dict[str, models.Asset]]:
    """Insert asset records


    Returns pair (ElectronAssets, asset_records), where
    `asset_records` is a mapping from asset key to asset records.

    """

    # Maps asset keys to asset records
    asset_recs = {}

    for asset_key, asset in e.assets:
        node_storage_path, object_key = object_store.get_uri_components(
            dispatch_id,
            e.id,
            asset_key,
        )

        object_key = ASSET_FILENAME_MAP[asset_key]
        local_uri = os.path.join(node_storage_path, object_key)
        asset_kwargs = {
            "storage_type": object_store.scheme,
            "storage_path": node_storage_path,
            "object_key": object_key,
            "digest_alg": asset.digest_alg,
            "digest": asset.digest,
            "remote_uri": asset.uri,
            "size": asset.size,
        }
        asset_recs[asset_key] = Asset.insert(session, insert_kwargs=asset_kwargs, flush=False)

        # Send this back to the client
        asset.digest = None
        asset.remote_uri = f"file://{local_uri}"

    # Register custom assets
    if e.custom_assets:
        for asset_key, asset in e.custom_assets.items():
            object_key = f"{asset_key}.data"
            local_uri = os.path.join(node_storage_path, object_key)

            asset_kwargs = {
                "storage_type": object_store.scheme,
                "storage_path": node_storage_path,
                "object_key": object_key,
                "digest_alg": asset.digest_alg,
                "digest": asset.digest,
                "remote_uri": asset.uri,
                "size": asset.size,
            }
            asset_recs[asset_key] = Asset.insert(session, insert_kwargs=asset_kwargs, flush=False)

            # Send this back to the client
            asset.remote_uri = f"file://{local_uri}" if asset.digest else ""
            asset.digest = None

    return e.assets, asset_recs
