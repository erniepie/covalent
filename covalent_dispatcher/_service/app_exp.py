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

import asyncio
import json
import shutil
from typing import Optional
from uuid import UUID

import anyio
from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

import covalent_dispatcher.entry_point as dispatcher
from covalent._results_manager.result import Result
from covalent._shared_files import logger

from .._dal.export import (
    export_serialized_result,
    get_dispatch_asset_uri,
    get_lattice_asset_uri,
    get_node_asset_uri,
)
from .._db.datastore import workflow_db
from .._db.models import Lattice
from .models import DispatchAssetKey, ElectronAssetKey, LatticeAssetKey

app_log = logger.app_log
log_stack_info = logger.log_stack_info

router: APIRouter = APIRouter()

app_log = logger.app_log
log_stack_info = logger.log_stack_info

router: APIRouter = APIRouter()


@router.post("/dispatchv2/submit")
async def submitv0(request: Request) -> UUID:
    """
    Function to accept the submit request of
    new dispatch and return the dispatch id
    back to the client.

    Args:
        None

    Returns:
        dispatch_id: The dispatch id in a json format
                     returned as a Fast API Response object.
    """
    try:
        data = await request.json()
        data = json.dumps(data).encode("utf-8")
        return await dispatcher.make_dispatch(data)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to submit workflow: {e}",
        ) from e


@router.post("/dispatchv2/resubmit")
async def resubmit(request: Request) -> str:
    """Endpoint to redispatch a workflow."""
    try:
        data = await request.json()
        dispatch_id = data["dispatch_id"]
        json_lattice = data["json_lattice"]
        electron_updates = data["electron_updates"]
        reuse_previous_results = data["reuse_previous_results"]
        return await dispatcher.make_redispatch(
            dispatch_id,
            json_lattice,
            electron_updates,
            reuse_previous_results,
        )

    except Exception as e:
        app_log.exception(f"Exception in redispatch handler: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to redispatch workflow: {e}",
        ) from e


@router.put("/dispatchv2/start/{dispatch_id}")
async def start(dispatch_id: str):
    try:
        await dispatcher.start_dispatch(dispatch_id)
        return dispatch_id
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to start workflow: {e}",
        ) from e


@router.get("/resultv2/{dispatch_id}")
async def get_result_v2(
    dispatch_id: str, wait: Optional[bool] = False, status_only: Optional[bool] = False
):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        _get_result_v2_sync,
        dispatch_id,
        wait,
        status_only,
    )


def _get_result_v2_sync(
    dispatch_id: str, wait: Optional[bool] = False, status_only: Optional[bool] = False
):
    with workflow_db.session() as session:
        lattice_record = session.query(Lattice).where(Lattice.dispatch_id == dispatch_id).first()
        status = lattice_record.status if lattice_record else None
        if not lattice_record:
            return JSONResponse(
                status_code=404,
                content={"message": f"The requested dispatch ID {dispatch_id} was not found."},
            )
        if not wait or status in [
            str(Result.COMPLETED),
            str(Result.FAILED),
            str(Result.CANCELLED),
            str(Result.POSTPROCESSING_FAILED),
            str(Result.PENDING_POSTPROCESSING),
        ]:
            output = {
                "id": dispatch_id,
                "status": lattice_record.status,
            }
            if not status_only:
                output["result_export"] = export_serialized_result(dispatch_id)

            return output

        response = JSONResponse(
            status_code=503,
            content={
                "message": "Result not ready to read yet. Please wait for a couple of seconds."
            },
            headers={"Retry-After": "2"},
        )
        return response


@router.get("/resultv2/{dispatch_id}/assets/node/{node_id}/{key}")
async def get_node_asset_exp(
    dispatch_id: str,
    node_id: int,
    key: ElectronAssetKey,
    start_byte: int = 0,
    end_byte: int = -1,
):
    app_log.debug(f"Requested asset {key.value} for node {dispatch_id}:{node_id}")

    if end_byte >= 0 and end_byte < start_byte:
        raise HTTPException(
            status_code=400,
            detail="Invalid byte range",
        )

    with workflow_db.session() as session:
        lattice_record = session.query(Lattice).where(Lattice.dispatch_id == dispatch_id).first()
        status = lattice_record.status if lattice_record else None
        if not lattice_record:
            return JSONResponse(
                status_code=404,
                content={"message": f"The requested dispatch ID {dispatch_id} was not found."},
            )

    try:
        path = get_node_asset_uri(dispatch_id, node_id, key.value)
    except:
        return JSONResponse(
            status_code=404,
            content={"message": f"Error retrieving asset {key.value}."},
        )
    generator = _generate_file_slice(path, start_byte, end_byte)
    return StreamingResponse(generator)


@router.get("/resultv2/{dispatch_id}/assets/dispatch/{key}")
async def get_dispatch_asset_exp(
    dispatch_id: str,
    key: DispatchAssetKey,
    start_byte: int = 0,
    end_byte: int = -1,
):
    app_log.debug(f"Requested asset {key.value} for dispatch {dispatch_id}")

    if end_byte >= 0 and end_byte < start_byte:
        raise HTTPException(
            status_code=400,
            detail="Invalid byte range",
        )

    with workflow_db.session() as session:
        lattice_record = session.query(Lattice).where(Lattice.dispatch_id == dispatch_id).first()
        status = lattice_record.status if lattice_record else None
        if not lattice_record:
            return JSONResponse(
                status_code=404,
                content={"message": f"The requested dispatch ID {dispatch_id} was not found."},
            )

    try:
        path = get_dispatch_asset_uri(dispatch_id, key.value)
        app_log.debug(f"Dispatch result uri: {path}")
    except:
        return JSONResponse(
            status_code=404,
            content={"message": f"Error retrieving asset {key.value}."},
        )

    generator = _generate_file_slice(path, start_byte, end_byte)
    return StreamingResponse(generator)


@router.get("/resultv2/{dispatch_id}/assets/lattice/{key}")
async def get_lattice_asset_exp(
    dispatch_id: str,
    key: LatticeAssetKey,
    start_byte: int = 0,
    end_byte: int = -1,
):
    app_log.debug(f"Requested lattice asset {key.value} for dispatch {dispatch_id}")

    if end_byte >= 0 and end_byte < start_byte:
        raise HTTPException(
            status_code=400,
            detail="Invalid byte range",
        )

    with workflow_db.session() as session:
        lattice_record = session.query(Lattice).where(Lattice.dispatch_id == dispatch_id).first()
        status = lattice_record.status if lattice_record else None
        if not lattice_record:
            return JSONResponse(
                status_code=404,
                content={"message": f"The requested dispatch ID {dispatch_id} was not found."},
            )

    try:
        path = get_lattice_asset_uri(dispatch_id, key.value)
        app_log.debug(f"Lattice asset uri: {path}")
    except:
        return JSONResponse(
            status_code=404,
            content={"message": f"Error retrieving asset {key.value}."},
        )
    generator = _generate_file_slice(path, start_byte, end_byte)
    return StreamingResponse(generator)


# Demo only!!!
@router.post("/resultv2/{dispatch_id}/assets/node/{node_id}/{key}")
async def upload_node_asset_exp(dispatch_id: str, node_id: int, key: str, asset_file: UploadFile):
    app_log.debug(f"Requested asset {key} for node {dispatch_id}:{node_id}")

    with workflow_db.session() as session:
        lattice_record = session.query(Lattice).where(Lattice.dispatch_id == dispatch_id).first()
        status = lattice_record.status if lattice_record else None
        if not lattice_record:
            return JSONResponse(
                status_code=404,
                content={"message": f"The requested dispatch ID {dispatch_id} was not found."},
            )

    try:
        path = get_node_asset_uri(dispatch_id, node_id, key)
    except:
        return JSONResponse(
            status_code=404,
            content={"message": f"Error retrieving metadata for asset {key}."},
        )

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _copy_file_obj, asset_file.file, path)

    return f"Uploaded file to {path}"


def _copy_file_obj(src_fileobj, dest_path):
    with open(dest_path, "wb") as dest_fileobj:
        shutil.copyfileobj(src_fileobj, dest_fileobj)


async def _generate_file_slice(
    file_path: str, start_byte: int, end_byte: int, chunk_size: int = 65536
):
    """Generator of a byte slice from a file"""
    byte_pos = start_byte

    async with await anyio.open_file(file_path, "rb") as f:
        await f.seek(start_byte)
        if end_byte < 0:
            async for chunk in f:
                yield chunk
        else:
            while byte_pos + chunk_size < end_byte:
                byte_pos += chunk_size
                yield await f.read(chunk_size)
            yield await f.read(end_byte - byte_pos)