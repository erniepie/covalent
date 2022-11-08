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

"""Electrons Route"""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

import covalent_ui.api.v1.database.config.db as db
from covalent_ui.api.v1.data_layer.electron_dal import Electrons
from covalent_ui.api.v1.models.electrons_model import (
    ElectronExecutorResponse,
    ElectronFileOutput,
    ElectronFileResponse,
    ElectronResponse,
)
from covalent_ui.api.v1.utils.file_handle import FileHandler

routes: APIRouter = APIRouter()


def text_processor(handler: FileHandler, file_name):
    return handler.read_from_text(file_name)


def pickle_processor(handler: FileHandler, file_name):
    return handler.read_from_pickle(file_name)


@routes.get("/{dispatch_id}/electron/{electron_id}", response_model=ElectronResponse)
def get_electron_details(dispatch_id: uuid.UUID, electron_id: int):
    """Get Electron Details

    Args:
        electron_id: To fetch electron data with the provided electron id.

    Returns:
        Returns the electron details
    """
    with Session(db.engine) as session:
        electron = Electrons(session)
        result = electron.get_electrons_id(dispatch_id, electron_id)
        if result is None:
            raise HTTPException(
                status_code=400,
                detail=[
                    {
                        "loc": ["path", "dispatch_id"],
                        "msg": f"Dispatch ID {dispatch_id} or Electron ID does not exist",
                        "type": None,
                    }
                ],
            )
        return ElectronResponse(
            id=result["id"],
            node_id=result["transport_graph_node_id"],
            parent_lattice_id=result["parent_lattice_id"],
            type=result["type"],
            storage_path=result["storage_path"],
            name=result["name"],
            status=result["status"],
            started_at=result["started_at"],
            ended_at=result["completed_at"],
            runtime=result["runtime"],
            description="",
        )


@routes.get("/{dispatch_id}/electron/{electron_id}/details/{name}")
def get_electron_file(dispatch_id: uuid.UUID, electron_id: int, name: ElectronFileOutput):
    """
    Get Electron details
    Args:
        dispatch_id: Dispatch id of lattice/sublattice
        electron_id: Transport graph node id of a electron
        name: refers file type, like inputs, function_string, function, executor, result, value, key,
        stdout, deps, call_before, call_after, error, info
    Returns:
        Returns electron details based on the given name
    """
    try:
        with Session(db.engine) as session:
            electron = Electrons(session)
            result = electron.get_electrons_id(dispatch_id, electron_id)
            if result is None:
                raise HTTPException(
                    status_code=400,
                    detail=[
                        {
                            "loc": ["path", "dispatch_id"],
                            "msg": f"Dispatch ID {dispatch_id} or Electron ID does not exist",
                            "type": None,
                        }
                    ],
                )
            else:
                handler = FileHandler(result["storage_path"])
                if name == "inputs":
                    response, python_object = electron.get_electron_inputs(
                        dispatch_id=dispatch_id, electron_id=electron_id
                    )
                    return ElectronFileResponse(
                        data=str(response), python_object=str(python_object)
                    )
                types_switch = {
                    "function_string": {
                        "func": text_processor,
                        "params": [handler, result["function_string_filename"]],
                    },
                    "function": {
                        "func": pickle_processor,
                        "params": [handler, result["function_filename"]],
                    },
                    "executor": {
                        "func": pickle_processor,
                        "params": [handler, result["executor_data_filename"]],
                    },
                    "result": {
                        "func": pickle_processor,
                        "params": [handler, result["results_filename"]],
                    },
                    "value": {
                        "func": pickle_processor,
                        "params": [handler, result["value_filename"]],
                    },
                    "stdout": {
                        "func": text_processor,
                        "params": [handler, result["stdout_filename"]],
                    },
                    "deps": {
                        "func": pickle_processor,
                        "params": [handler, result["deps_filename"]],
                    },
                    "call_before": {
                        "func": pickle_processor,
                        "params": [handler, result["call_before_filename"]],
                    },
                    "call_after": {
                        "func": pickle_processor,
                        "params": [handler, result["call_after_filename"]],
                    },
                    "error": {
                        "func": text_processor,
                        "params": [handler, result["stderr_filename"]],
                    },
                    "info": {"func": text_processor, "params": [handler, result["info_filename"]]},
                }
                switcher = types_switch.get(name)
                if name in ["result", "function"]:
                    response, python_object = switcher["func"](*switcher["params"])
                    return ElectronFileResponse(data=response, python_object=python_object)
                elif name == "executor":
                    executor_name = result["executor"]
                    executor_data = switcher["func"](*switcher["params"])
                    return ElectronExecutorResponse(
                        executor_name=executor_name, executor_details=executor_data
                    )
                else:
                    response = switcher["func"](*switcher["params"])
                    return ElectronFileResponse(data=response)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=[
                {
                    "loc": ["path", "dispatch_id"],
                    "msg": f"Dispatch ID {dispatch_id} or Electron ID does not exist",
                    "type": None,
                }
            ],
        ) from exc
