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

"""
Functions for cancelling jobs
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List

from covalent._shared_files import logger
from covalent._shared_files.util_classes import RESULT_STATUS

from .. import data_manager as datasvc
from ..data_modules import job_manager
from .utils import get_executor

app_log = logger.app_log

# Dedicated thread pool for invoking non-async Executor.cancel()
_cancel_threadpool = ThreadPoolExecutor()


async def _cancel_task(
    dispatch_id: str, task_id: int, selected_executor: List, job_handle: str
) -> None:
    """
    Cancel the task currently being executed by the executor

    Arg(s)
        dispatch_id: Dispatch ID
        task_id: Task ID of the electron in transport graph to be cancelled
        executor: Covalent executor currently being used to execute the task
        executor_data: Executor configuration arguments
        job_handle: Unique identifier assigned to the task by the backend running the job

    Return(s)
        cancel_job_result: Status of the job cancellation action
    """
    app_log.debug(f"Cancel task {task_id} using executor {selected_executor}")
    app_log.debug(f"job_handle: {job_handle}")

    try:
        executor = get_executor(
            node_id=task_id,
            selected_executor=selected_executor,
            loop=asyncio.get_running_loop(),
            pool=_cancel_threadpool,
        )

        task_metadata = {"dispatch_id": dispatch_id, "node_id": task_id}

        cancel_job_result = await executor._cancel(task_metadata, json.loads(job_handle))
    except Exception as ex:
        app_log.debug(f"Exception when cancel task {dispatch_id}:{task_id}: {ex}")
        cancel_job_result = False

    if cancel_job_result is True:
        await job_manager.set_job_status(dispatch_id, task_id, str(RESULT_STATUS.CANCELLED))
        app_log.debug(f"Cancelled task {dispatch_id}:{task_id}")


def _to_cancel_kwargs(
    index: int, node_id: int, node_metadata: List[dict], job_metadata: List[dict]
) -> dict:
    """
    Convert node_metadata for a given node `node_id` into a dictionary

    Arg(s)
        index: Index into the node_metadata list
        node_id: Node ID
        node_metadata: List of node metadata attributes
        job_metadata: List of metadata for the current job

    Return(s)
        Node metadata dictionary
    """
    selected_executor = [node_metadata[index]["executor"], node_metadata[index]["executor_data"]]
    return {
        "task_id": node_id,
        "selected_executor": selected_executor,
        "job_handle": job_metadata[index]["job_handle"],
    }


async def cancel_tasks(dispatch_id: str, task_ids: List[int]) -> None:
    """
    Request all tasks with `task_ids` to be cancelled in the workflow identified by `dispatch_id`

    Arg(s)
        dispatch_id: Dispatch ID of the workflow
        task_ids: List of task ids to be cancelled

    Return(s)
        None
    """
    job_metadata = await job_manager.get_jobs_metadata(dispatch_id, task_ids)
    node_metadata = await _get_metadata_for_nodes(dispatch_id, task_ids)
    app_log.debug(f"node metadata: {node_metadata}")
    app_log.debug(f"job metadata: {job_metadata}")
    cancel_task_kwargs = [
        _to_cancel_kwargs(i, x, node_metadata, job_metadata) for i, x in enumerate(task_ids)
    ]

    for kwargs in cancel_task_kwargs:
        asyncio.create_task(_cancel_task(dispatch_id, **kwargs))


async def _get_metadata_for_nodes(dispatch_id: str, node_ids: list) -> List[Any]:
    """
    Returns all the metadata associated with the node(s) for the workflow identified by `dispatch_id`

    Arg(s)
        dispatch_id: Dispatch ID of the workflow
        node_ids: List of node ids from the workflow to retrive the metadata for

    Return(s)
        List of node metadata for the given `node_ids`
    """

    attrs = await datasvc.get_attrs_for_electrons(
        dispatch_id,
        node_ids,
        ["executor", "executor_data"],
    )
    return attrs


async def _get_cancel_requested(dispatch_id: str, task_id: int) -> Any:
    """
    Query if a specific task has been requested to be cancelled

    Arg(s)
        dispatch_id: Dispatch ID of the workflow
        task_id: ID of the node to be cancelled

    Return(s)
        Whether the task has been requested to be cancelled or not
    """
    records = await job_manager.get_jobs_metadata(dispatch_id, [task_id])
    return records[0]["cancel_requested"]
