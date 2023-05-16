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
Defines the core functionality of the result service
"""

import functools
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional

import networkx as nx

from covalent._results_manager import Result
from covalent._shared_files import logger
from covalent._shared_files.config import get_config
from covalent._shared_files.schemas.result import ResultSchema
from covalent._shared_files.util_classes import RESULT_STATUS
from covalent._workflow.lattice import Lattice
from covalent_dispatcher._dal.tg_ops import TransportGraphOps

from .._dal.export import export_serialized_result
from .._dal.result import Result as SRVResult
from .._dal.result import get_result_object as get_result_object_from_db
from .._db import update
from .._db.write_result_to_db import resolve_electron_id
from . import dispatcher
from .data_modules import importer as manifest_importer
from .data_modules.utils import run_in_executor

app_log = logger.app_log
log_stack_info = logger.log_stack_info

# References to result objects of live dispatches
_registered_dispatches = {}

STATELESS = get_config("dispatcher.use_stateless_datamgr") != "false"


def generate_node_result(
    node_id,
    node_name=None,
    start_time=None,
    end_time=None,
    status=None,
    output=None,
    error=None,
    stdout=None,
    stderr=None,
):
    return {
        "node_id": node_id,
        "node_name": node_name,
        "start_time": start_time,
        "end_time": end_time,
        "status": status,
        "output": output,
        "error": error,
        "stdout": stdout,
        "stderr": stderr,
    }


# Domain: result
async def update_node_result(dispatch_id, node_result):
    app_log.debug("Updating node result (run_planned_workflow).")
    valid_update = True
    try:
        node_id = node_result["node_id"]
        node_status = node_result["status"]
        node_info = await get_electron_attributes(
            dispatch_id, node_id, ["type", "sub_dispatch_id"]
        )
        node_type = node_info["type"]
        sub_dispatch_id = node_info["sub_dispatch_id"]

        # Handle returns from _build_sublattice_graph -- change
        # COMPLETED -> DISPATCHING
        node_result = await _filter_sublattice_status(
            dispatch_id, node_id, node_status, node_type, sub_dispatch_id, node_result
        )
        result_object = await run_in_executor(get_result_object, dispatch_id, True)
        update_partial = functools.partial(result_object._update_node, **node_result)

        valid_update = await run_in_executor(update_partial)
        if not valid_update:
            app_log.warning(
                f"Invalid status update {node_status} for node {dispatch_id}:{node_id}"
            )
            return

        if node_result["status"] == RESULT_STATUS.DISPATCHING:
            app_log.debug("Received sublattice dispatch")
            try:
                sub_dispatch_id = await _make_sublattice_dispatch(result_object, node_result)
            except Exception as ex:
                tb = "".join(traceback.TracebackException.from_exception(ex).format())
                node_result["status"] = RESULT_STATUS.FAILED
                node_result["error"] = tb
                update_partial = functools.partial(result_object._update_node, **node_result)
                await run_in_executor(update_partial)

    except KeyError as ex:
        valid_update = False
        app_log.exception(f"Error persisting node update: {ex}")

    except Exception as ex:
        app_log.exception(f"Error persisting node update: {ex}")
        sub_dispatch_id = None
        node_result["status"] = Result.FAILED

    finally:
        if not valid_update:
            return

        node_id = node_result["node_id"]
        node_status = node_result["status"]
        dispatch_id = dispatch_id

        detail = {"sub_dispatch_id": sub_dispatch_id} if sub_dispatch_id else {}
        if node_status and valid_update:
            await dispatcher.notify_node_status(dispatch_id, node_id, node_status, detail)


# Domain: result
def initialize_result_object(
    json_lattice: str, parent_result_object: SRVResult = None, parent_electron_id: int = None
) -> Result:
    """Convenience function for constructing a result object from a json-serialized lattice.

    Args:
        json_lattice: a JSON-serialized lattice
        parent_result_object: the parent result object if json_lattice is a sublattice
        parent_electron_id: the DB id of the parent electron (for sublattices)

    Returns:
        Result: result object
    """

    dispatch_id = get_unique_id()
    lattice = Lattice.deserialize_from_json(json_lattice)
    result_object = Result(lattice, dispatch_id)
    if parent_result_object:
        result_object._root_dispatch_id = parent_result_object.root_dispatch_id

    result_object._electron_id = parent_electron_id
    result_object._initialize_nodes()
    app_log.debug("2: Constructed result object and initialized nodes.")

    update.persist(result_object, electron_id=parent_electron_id)
    app_log.debug("Result object persisted.")

    return result_object


# Domain: result
def get_unique_id() -> str:
    """
    Get a unique ID.

    Args:
        None

    Returns:
        str: Unique ID
    """

    return str(uuid.uuid4())


async def make_dispatch(
    json_lattice: str, parent_result_object: SRVResult = None, parent_electron_id: int = None
) -> Result:
    result_object = await run_in_executor(
        initialize_result_object,
        json_lattice,
        parent_result_object,
        parent_electron_id,
    )
    _register_result_object(result_object)
    return result_object.dispatch_id


def _get_result_object_from_new_lattice(
    json_lattice: str, old_result_object: SRVResult, reuse_previous_results: bool
) -> SRVResult:
    """Get new SRVResult for re-dispatching from new lattice json."""
    lat = Lattice.deserialize_from_json(json_lattice)
    sdk_result = Result(lat, get_unique_id())
    sdk_result._initialize_nodes()

    # Record the new result in the DB so that we can perform graph
    # diffs using db queries.

    update.persist(sdk_result)
    result_object = get_result_object_from_db(sdk_result.dispatch_id, False)

    if reuse_previous_results:
        tg = result_object.lattice.transport_graph
        tg_old = old_result_object.lattice.transport_graph
        reusable_nodes = TransportGraphOps(tg_old).get_reusable_nodes(tg)
        TransportGraphOps(tg).copy_nodes_from(tg_old, reusable_nodes)

    return result_object


def _make_derived_dispatch_sync(
    parent_dispatch_id: str,
    json_lattice: Optional[str] = None,
    electron_updates: Optional[Dict[str, Callable]] = None,
    reuse_previous_results: bool = False,
) -> str:
    """Make a re-dispatch from a previous dispatch."""
    if electron_updates is None:
        electron_updates = {}

    # includes parameter value hashes
    old_result_object = get_result_object_from_db(
        dispatch_id=parent_dispatch_id,
        bare=False,
    )

    # reuse the previously submitted lattice if no new json_lattice
    serialized_old_res = export_serialized_result(old_result_object.dispatch_id)
    if not json_lattice:
        json_lattice = serialized_old_res["lattice"]

    result_object = _get_result_object_from_new_lattice(
        json_lattice, old_result_object, reuse_previous_results
    )

    ops = TransportGraphOps(result_object.lattice.transport_graph)
    ops.apply_electron_updates(electron_updates)

    _register_result_object(result_object)

    return result_object.dispatch_id


async def make_derived_dispatch(
    parent_dispatch_id: str,
    json_lattice: Optional[str] = None,
    electron_updates: Optional[Dict[str, Callable]] = None,
    reuse_previous_results: bool = False,
) -> str:
    """Make a re-dispatch from a previous dispatch."""

    return await run_in_executor(
        _make_derived_dispatch_sync,
        parent_dispatch_id,
        json_lattice,
        electron_updates,
        reuse_previous_results,
    )


def get_result_object(dispatch_id: str, bare: bool = True) -> SRVResult:
    if STATELESS:
        app_log.debug(f"Getting result object from db, bare={bare}")
        return get_result_object_from_db(dispatch_id, bare)
    else:
        app_log.debug("Getting cached result object")
        return _registered_dispatches[dispatch_id]


def _register_result_object(result_object: Result):
    if not STATELESS:
        dispatch_id = result_object.dispatch_id
        _registered_dispatches[dispatch_id] = get_result_object_from_db(dispatch_id)


def finalize_dispatch(dispatch_id: str):
    app_log.debug(f"Finalizing dispatch {dispatch_id}")
    if not STATELESS:
        del _registered_dispatches[dispatch_id]


async def persist_result(dispatch_id: str):
    result_object = get_result_object(dispatch_id)
    await _update_parent_electron(result_object)


async def _update_parent_electron(result_object: SRVResult):
    parent_eid = result_object._electron_id

    if parent_eid:
        dispatch_id, node_id = resolve_electron_id(parent_eid)
        status = result_object.status
        if status == Result.POSTPROCESSING_FAILED:
            status = Result.FAILED
        node_result = generate_node_result(
            node_id=node_id,
            end_time=result_object.end_time,
            status=status,
        )
        parent_result_obj = get_result_object(dispatch_id)
        app_log.debug(f"Updating sublattice parent node {dispatch_id}:{node_id}")
        await update_node_result(parent_result_obj.dispatch_id, node_result)


def _get_attrs_for_electrons_sync(
    dispatch_id: str, node_ids: List[int], keys: List[str]
) -> List[Dict]:
    result_object = get_result_object(dispatch_id)
    refresh = False if STATELESS else True
    attrs = result_object.lattice.transport_graph.get_values_for_nodes(
        node_ids=node_ids,
        keys=keys,
        refresh=refresh,
    )
    return attrs


async def get_attrs_for_electrons(
    dispatch_id: str, node_ids: List[int], keys: List[str]
) -> List[Dict]:
    return await run_in_executor(
        _get_attrs_for_electrons_sync,
        dispatch_id,
        node_ids,
        keys,
    )


async def get_electron_attribute(dispatch_id: str, node_id: int, key: str) -> Any:
    query_res = await get_electron_attributes(dispatch_id, node_id, [key])
    return query_res[key]


async def get_electron_attributes(dispatch_id: str, node_id: int, keys: str) -> Any:
    attrs = await get_attrs_for_electrons(dispatch_id, [node_id], keys)
    return attrs[0]


async def _filter_sublattice_status(
    dispatch_id, node_id, status, node_type, sub_dispatch_id, node_result
):
    if status == Result.COMPLETED and node_type == "sublattice" and not sub_dispatch_id:
        node_result["status"] = RESULT_STATUS.DISPATCHING
    return node_result


# NB: this loads the JSON sublattice in memory
async def _make_sublattice_dispatch(result_object: SRVResult, node_result: dict):
    node_id = node_result["node_id"]
    bg_output = await get_electron_attribute(result_object.dispatch_id, node_id, "output")
    # json_lattice = bg_output.object_string
    manifest = ResultSchema.parse_raw(bg_output.object_string)
    parent_node = await run_in_executor(
        result_object.lattice.transport_graph.get_node,
        node_id,
    )
    parent_electron_id = parent_node._electron_id

    imported_manifest = await manifest_importer.import_manifest(
        manifest=manifest,
        parent_dispatch_id=result_object.dispatch_id,
        parent_electron_id=parent_electron_id,
    )

    return imported_manifest.metadata.dispatch_id
    # return await make_dispatch(json_lattice, result_object, parent_electron_id)


# Common Result object queries

# Dispatch


def generate_dispatch_result(
    dispatch_id,
    start_time=None,
    end_time=None,
    status=None,
    error=None,
    result=None,
):
    return {
        "start_time": start_time,
        "end_time": end_time,
        "status": status,
        "error": error,
        "result": result,
    }


def _update_dispatch_result_sync(dispatch_id, dispatch_result):
    result_object = get_result_object(dispatch_id)
    result_object._update_dispatch(**dispatch_result)


async def update_dispatch_result(dispatch_id, dispatch_result):
    await run_in_executor(_update_dispatch_result_sync, dispatch_id, dispatch_result)


def _get_dispatch_attributes_sync(dispatch_id: str, keys: List[str]) -> Any:
    refresh = False if STATELESS else True
    result_object = get_result_object(dispatch_id)
    return result_object.get_values(keys, refresh=refresh)


async def get_dispatch_attributes(dispatch_id: str, keys: List[str]) -> Dict:
    return await run_in_executor(
        _get_dispatch_attributes_sync,
        dispatch_id,
        keys,
    )


# Ensure that a dispatch is only run once; in the future, also check
# if all assets have been uploaded
def _ensure_dispatch_sync(dispatch_id: str) -> bool:
    return SRVResult.ensure_run_once(dispatch_id)


async def ensure_dispatch(dispatch_id: str) -> bool:
    """Check if a dispatch can be run.

    The following criteria must be met:
    * The dispatch has not been run before.
    * (later) all assets have been uploaded
    """
    return await run_in_executor(
        _ensure_dispatch_sync,
        dispatch_id,
    )


# Graph queries


async def get_incomplete_tasks(dispatch_id: str):
    # Need to filter all electrons in the latice
    result_object = get_result_object(dispatch_id, False)
    refresh = False if STATELESS else True
    return await run_in_executor(
        result_object._get_incomplete_nodes,
        refresh,
    )


def get_incoming_edges_sync(dispatch_id: str, node_id: int):
    result_object = get_result_object(dispatch_id)
    return result_object.lattice.transport_graph.get_incoming_edges(node_id)


async def get_incoming_edges(dispatch_id: str, node_id: int):
    return await run_in_executor(get_incoming_edges_sync, dispatch_id, node_id)


def get_node_successors_sync(
    dispatch_id: str,
    node_id: int,
    attrs: List[str],
) -> List[Dict]:
    result_object = get_result_object(dispatch_id)
    return result_object.lattice.transport_graph.get_successors(node_id, attrs)


async def get_node_successors(
    dispatch_id: str,
    node_id: int,
    attrs: List[str] = ["task_group_id"],
) -> List[Dict]:
    return await run_in_executor(get_node_successors_sync, dispatch_id, node_id, attrs)


def get_graph_nodes_links_sync(dispatch_id: str) -> dict:
    """Return the internal transport graph in NX node-link form"""

    # Need the whole NX graph here
    result_object = get_result_object(dispatch_id, False)
    g = result_object.lattice.transport_graph.get_internal_graph_copy()
    return nx.readwrite.node_link_data(g)


async def get_graph_nodes_links(dispatch_id: str) -> dict:
    return await run_in_executor(get_graph_nodes_links_sync, dispatch_id)


def get_nodes_sync(dispatch_id: str) -> List[int]:
    # Read the whole NX graph
    result_object = get_result_object(dispatch_id, False)
    g = result_object.lattice.transport_graph.get_internal_graph_copy()
    return list(g.nodes)


async def get_nodes(dispatch_id: str) -> List[int]:
    return await run_in_executor(get_nodes, dispatch_id)
