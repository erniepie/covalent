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

from copy import deepcopy
from functools import wraps
from typing import Callable, Dict, List, Optional, Union

import requests

from .._results_manager import wait
from .._results_manager.result import Result
from .._results_manager.results_manager import get_result
from .._shared_files import logger
from .._shared_files.config import get_config
from .._workflow.lattice import Lattice
from ..triggers import BaseTrigger
from .base import BaseDispatcher

app_log = logger.app_log
log_stack_info = logger.log_stack_info


def get_redispatch_request_body(
    dispatch_id: str,
    new_args: Optional[List] = None,
    new_kwargs: Optional[Dict] = None,
    replace_electrons: Optional[Dict[str, Callable]] = None,
    reuse_previous_results: bool = False,
) -> Dict:
    """Get request body for re-dispatching a workflow."""
    if new_args is None:
        new_args = []
    if new_kwargs is None:
        new_kwargs = {}
    if replace_electrons is None:
        replace_electrons = {}
    if new_args or new_kwargs:
        res = get_result(
            dispatch_id,
            workflow_output=False,
            intermediate_outputs=False,
            sublattice_results=False,
        )
        lat = res.lattice
        lat.build_graph(*new_args, **new_kwargs)
        json_lattice = lat.serialize_to_json()
    else:
        json_lattice = None
    updates = {k: v.electron_object.as_transportable_dict for k, v in replace_electrons.items()}

    return {
        "json_lattice": json_lattice,
        "dispatch_id": dispatch_id,
        "electron_updates": updates,
        "reuse_previous_results": reuse_previous_results,
    }


class LocalDispatcher(BaseDispatcher):
    """
    Local dispatcher which sends the workflow to the locally running
    dispatcher server.
    """

    @staticmethod
    def dispatch(
        orig_lattice: Lattice, dispatcher_addr: str = None, *, disable_run: bool = False
    ) -> Callable:
        """
        Wrapping the dispatching functionality to allow input passing
        and server address specification.

        Afterwards, send the lattice to the dispatcher server and return
        the assigned dispatch id.

        Args:
            orig_lattice: The lattice/workflow to send to the dispatcher server.
            dispatcher_addr: The address of the dispatcher server.  If None then then defaults to the address set in Covalent's config.

        Returns:
            Wrapper function which takes the inputs of the workflow as arguments
        """

        # Extract triggers here
        triggers_data = orig_lattice.metadata.pop("triggers")

        if not disable_run:
            # Determine whether to disable first run based on trigger_data
            disable_run = triggers_data is not None

        @wraps(orig_lattice)
        def wrapper(*args, **kwargs) -> str:
            """
            Send the lattice to the dispatcher server and return
            the assigned dispatch id.

            Args:
                *args: The inputs of the workflow.
                **kwargs: The keyword arguments of the workflow.

            Returns:
                The dispatch id of the workflow.
            """

            dispatch_id = LocalDispatcher.submit(orig_lattice, dispatcher_addr)(*args, **kwargs)

            if triggers_data:
                LocalDispatcher.register_triggers(triggers_data, dispatch_id)

            if not disable_run:
                return LocalDispatcher.start(dispatch_id, dispatcher_addr)
            else:
                return dispatch_id

        return wrapper

    @staticmethod
    def submit(
        orig_lattice: Lattice,
        dispatcher_addr: str = None,
    ) -> Callable:
        """
        Wrapping the dispatching functionality to allow input passing
        and server address specification.

        Afterwards, send the lattice to the dispatcher server and return
        the assigned dispatch id.

        Args:
            orig_lattice: The lattice/workflow to send to the dispatcher server.
            dispatcher_addr: The address of the dispatcher server.  If None then then defaults to the address set in Covalent's config.

        Returns:
            Wrapper function which takes the inputs of the workflow as arguments
        """

        if dispatcher_addr is None:
            dispatcher_addr = (
                get_config("dispatcher.address") + ":" + str(get_config("dispatcher.port"))
            )

        @wraps(orig_lattice)
        def wrapper(*args, **kwargs) -> str:
            """
            Send the lattice to the dispatcher server and return
            the assigned dispatch id.

            Args:
                *args: The inputs of the workflow.
                **kwargs: The keyword arguments of the workflow.

            Returns:
                The dispatch id of the workflow.
            """

            lattice = deepcopy(orig_lattice)

            lattice.build_graph(*args, **kwargs)

            # Serialize the transport graph to JSON
            json_lattice = lattice.serialize_to_json()

            test_url = f"http://{dispatcher_addr}/api/v1/dispatchv2/submit"

            r = requests.post(test_url, data=json_lattice)
            r.raise_for_status()
            return r.content.decode("utf-8").strip().replace('"', "")

        return wrapper

    @staticmethod
    def start(
        dispatch_id: str,
        dispatcher_addr: str = None,
    ) -> Callable:
        """
        Wrapping the dispatching functionality to allow input passing
        and server address specification.

        Afterwards, send the lattice to the dispatcher server and return
        the assigned dispatch id.

        Args:
            orig_lattice: The lattice/workflow to send to the dispatcher server.
            dispatcher_addr: The address of the dispatcher server.  If None then then defaults to the address set in Covalent's config.

        Returns:
            Wrapper function which takes the inputs of the workflow as arguments
        """

        if dispatcher_addr is None:
            dispatcher_addr = (
                get_config("dispatcher.address") + ":" + str(get_config("dispatcher.port"))
            )

        test_url = f"http://{dispatcher_addr}/api/v1/dispatchv2/start/{dispatch_id}"
        r = requests.put(test_url)
        r.raise_for_status()
        return r.content.decode("utf-8").strip().replace('"', "")

    @staticmethod
    def dispatch_sync(
        lattice: Lattice,
        dispatcher_addr: str = None,
    ) -> Callable:
        """
        Wrapping the synchronous dispatching functionality to allow input
        passing and server address specification.

        Afterwards, sends the lattice to the dispatcher server and return
        the result of the executed workflow.

        Args:
            orig_lattice: The lattice/workflow to send to the dispatcher server.
            dispatcher_addr: The address of the dispatcher server. If None then then defaults to the address set in Covalent's config.

        Returns:
            Wrapper function which takes the inputs of the workflow as arguments.
        """

        if dispatcher_addr is None:
            dispatcher_addr = (
                get_config("dispatcher.address") + ":" + str(get_config("dispatcher.port"))
            )

        @wraps(lattice)
        def wrapper(*args, **kwargs) -> Result:
            """
            Send the lattice to the dispatcher server and return
            the result of the executed workflow.

            Args:
                *args: The inputs of the workflow.
                **kwargs: The keyword arguments of the workflow.

            Returns:
                The result of the executed workflow.
            """

            return get_result(
                LocalDispatcher.dispatch(lattice, dispatcher_addr)(*args, **kwargs),
                wait=wait.EXTREME,
            )

        return wrapper

    @staticmethod
    def redispatch(
        dispatch_id: str,
        dispatcher_addr: str = None,
        replace_electrons: Dict[str, Callable] = None,
        reuse_previous_results: bool = False,
    ) -> Callable:
        """
        Wrapping the dispatching functionality to allow input passing and server address specification.

        Args:
            dispatch_id: The dispatch id of the workflow to re-dispatch.
            dispatcher_addr: The address of the dispatcher server. If None then then defaults to the address set in Covalent's config.
            replace_electrons: A dictionary of electron names and the new electron to replace them with.
            reuse_previous_results: Boolean value whether to reuse the results from the previous dispatch.

        Returns:
            Wrapper function which takes the inputs of the workflow as arguments.
        """

        if dispatcher_addr is None:
            dispatcher_addr = (
                get_config("dispatcher.address") + ":" + str(get_config("dispatcher.port"))
            )

        if replace_electrons is None:
            replace_electrons = {}

        def func(*new_args, **new_kwargs):
            """
            Prepare the redispatch request body and redispatch the workflow.

            Args:
                *args: The inputs of the workflow.
                **kwargs: The keyword arguments of the workflow.

            Returns:
                The result of the executed workflow.
            """

            redispatch_id = LocalDispatcher.resubmit(
                dispatch_id,
                dispatcher_addr,
                replace_electrons,
                reuse_previous_results,
            )(*new_args, **new_kwargs)

            return LocalDispatcher.start(redispatch_id, dispatcher_addr)

        return func

    @staticmethod
    def resubmit(
        dispatch_id: str,
        dispatcher_addr: str = None,
        replace_electrons: Dict[str, Callable] = None,
        reuse_previous_results: bool = False,
    ) -> Callable:
        """
        Wrapping the dispatching functionality to allow input passing and server address specification.

        Args:
            dispatch_id: The dispatch id of the workflow to re-dispatch.
            dispatcher_addr: The address of the dispatcher server. If None then then defaults to the address set in Covalent's config.
            replace_electrons: A dictionary of electron names and the new electron to replace them with.
            reuse_previous_results: Boolean value whether to reuse the results from the previous dispatch.

        Returns:
            Wrapper function which takes the inputs of the workflow as arguments.
        """

        if dispatcher_addr is None:
            dispatcher_addr = (
                get_config("dispatcher.address") + ":" + str(get_config("dispatcher.port"))
            )

        if replace_electrons is None:
            replace_electrons = {}

        def func(*new_args, **new_kwargs):
            """
            Prepare the redispatch request body and redispatch the workflow.

            Args:
                *args: The inputs of the workflow.
                **kwargs: The keyword arguments of the workflow.

            Returns:
                The result of the executed workflow.
            """

            body = get_redispatch_request_body(
                dispatch_id, new_args, new_kwargs, replace_electrons, reuse_previous_results
            )

            url = f"http://{dispatcher_addr}/api/v1/dispatchv2/resubmit"
            r = requests.post(url, json=body)
            r.raise_for_status()
            return r.content.decode("utf-8").strip().replace('"', "")

        return func

    @staticmethod
    def register_triggers(triggers_data: List[Dict], dispatch_id: str) -> None:
        """
        Register the given triggers to the Triggers server.
        Register also starts the `observe()` method of said trigger.
        This is done by calling `BaseTrigger._register` method
        with the given trigger dictionary and is equivalent to
        calling the trigger objects `register()` method.

        Args:
            triggers_data: List of trigger dictionaries to be registered
            dispatch_id: Lattice's dispatch id to be linked with given triggers

        Returns:
            None
        """

        for tr_dict in triggers_data:
            tr_dict["lattice_dispatch_id"] = dispatch_id
            BaseTrigger._register(tr_dict)

    @staticmethod
    def stop_triggers(
        dispatch_ids: Union[str, List[str]], triggers_server_addr: str = None
    ) -> None:
        """
        Stop observing on all triggers of all given dispatch ids registered on the Triggers server.
        Args:
            dispatch_ids: Dispatch ID(s) for whose triggers are to be stopped
            triggers_server_addr: Address of the Triggers server; configured dispatcher's address is used as default
        Returns:
            None
        """

        if triggers_server_addr is None:
            triggers_server_addr = (
                "http://"
                + get_config("dispatcher.address")
                + ":"
                + str(get_config("dispatcher.port"))
            )

        stop_triggers_url = f"{triggers_server_addr}/api/triggers/stop_observe"

        if isinstance(dispatch_ids, str):
            dispatch_ids = [dispatch_ids]

        r = requests.post(stop_triggers_url, json=dispatch_ids)
        r.raise_for_status()

        app_log.debug("Triggers for following dispatch_ids have stopped observing:")
        for d_id in dispatch_ids:
            app_log.debug(d_id)
