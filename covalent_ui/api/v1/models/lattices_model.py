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

"""Lattice request and response model"""

from datetime import datetime
from enum import Enum
from typing import Union

from pydantic import BaseModel


class LatticeDetailResponse(BaseModel):
    """Lattices details model"""

    dispatch_id: Union[str, None] = None
    status: Union[str, None] = None
    total_electrons: Union[int, None] = None
    total_electrons_completed: Union[int, None] = None
    started_at: Union[datetime, None] = None
    ended_at: Union[datetime, None] = None
    directory: Union[str, None] = None
    description: Union[str, None] = None
    runtime: Union[int, None] = None
    updated_at: Union[datetime, None] = None


class LatticeFileResponse(BaseModel):
    """Lattices File Response Model"""

    data: Union[str, None] = None


class LatticeExecutorResponse(BaseModel):
    """Lattices File Response Model"""

    executor_name: Union[str, None] = None
    executor_details: Union[dict, None] = None


class LatticeWorkflowExecutorResponse(BaseModel):
    """Lattices File Response Model"""

    workflow_executor_name: Union[str, None] = None
    workflow_executor_details: Union[dict, None] = None


class GraphResponse(BaseModel):
    """Graph Response Model"""

    dispatch_id: Union[str, None] = None
    graph: Union[dict, None] = None


class ElectronResponse(BaseModel):
    """Electron Response Model"""

    id: Union[int, None] = None
    node_id: Union[int, None] = None
    parent_lattice_id: Union[int, None] = None
    type: Union[str, None] = None
    storage_path: Union[str, None] = None
    name: Union[str, None] = None
    status: Union[str, None] = None
    started_at: Union[datetime, None] = None
    ended_at: Union[datetime, None] = None
    runtime: Union[int, None] = None
    description: Union[str, None] = None


class ElectronFileResponse(BaseModel):
    """Electron Response Model"""

    data: Union[str, None] = None


class ElectronExecutorResponse(BaseModel):
    """Lattices File Response Model"""

    executor_name: Union[str, None] = None
    executor_details: Union[dict, None] = None


class ElectronErrorResponse(BaseModel):
    """Eelctron Error Response Model"""

    data: Union[str, None] = None


class ElectronFunctionResponse(BaseModel):
    """Electron Function Response Model"""

    data: Union[str, None] = None


class FileOutput(str, Enum):
    RESULT = "result"
    FUNCTION_STRING = "function_string"
    INPUTS = "inputs"
    ERROR = "error"
    EXECUTOR = "executor"
    WORKFLOW_EXECUTOR = "workflow_executor"
    FUNCTION = "function"
    TRANSPORT_GRAPH = "transport_graph"
