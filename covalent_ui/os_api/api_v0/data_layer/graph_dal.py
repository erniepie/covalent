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

"""Graph Data Layer"""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from covalent_ui.os_api.api_v0.database.schema.electron_dependency import ElectronDependency
from covalent_ui.os_api.api_v0.database.schema.electrons_schema import Electron
from covalent_ui.os_api.api_v0.database.schema.lattices_schema import Lattice
from covalent_ui.os_api.api_v0.models.lattices_model import GraphResponse


class Graph:
    """Graph data access layer"""

    def __init__(self, db_con: Session) -> None:
        self.db_con = db_con

    def get_electron_id(self, lattice_id):
        """
        Get electron ids using parent lattice id
        Args:
            lattice_id: Refers to the parent_lattice_id in electron dependency
        Return:
            Electron ids
        """
        return (
            self.db_con.query(Electron.id, Electron.transport_graph_node_id)
            .filter(Electron.parent_lattice_id.in_(lattice_id))
            .first()
        )

    def get_lattices_id(self, dispatch_id: UUID):
        """
        Get Lattice id from dispatch id
        Args:
            lattice_id: Refers to the parent_lattice_id in electron dependency
        Return:
            Lattice ids
        """
        return (
            self.db_con.query(Lattice.id, Lattice.dispatch_id)
            .filter(Lattice.dispatch_id == str(dispatch_id))
            .first()
        )

    def get_nodes(self, lattice_id):
        """
        Get all nodes corresponding to lattices id
        Args:
            lattice_id: Refers to the parent_lattice_id in electron dependency
        Return:
            List of nodes
        """
        return (
            self.db_con.query(
                Electron.name,
                Electron.transport_graph_node_id.label("node_id"),
                Electron.started_at,
                Electron.completed_at,
                Electron.status,
                Electron.type,
            )
            .filter(Electron.parent_lattice_id.in_(lattice_id))
            .all()
        )

    def get_links(self, electron_id):
        """
        Get all links corresponding to electron id
        Args:
            electron_id: Refers to the electron id in electron dependency
        Return:
            List of links
        """
        return (
            self.db_con.query(
                ElectronDependency.edge_name,
                ElectronDependency.parameter_type,
                ElectronDependency.electron_id.label("source"),
                ElectronDependency.parent_electron_id.label("target"),
                ElectronDependency.arg_index,
            )
            .filter(~ElectronDependency.electron_id.in_(electron_id))
            .all()
        )

    def get_graph(self, dispatch_id: UUID):
        """
        Get graph data from parent lattice id
        When dispatch id passed to get graph
            Get list of nodes from Electrons table by passing list of latice id with the dispatch id
            Get list of links from Electron dependency table by passing in electron ids
        Args:
            dispatch_id: Refers to the dispatch id from lattices table
        Return:
            graph data with list of nodes and links
        """
        # Get all lattice id for that dispatch id
        lattice_id = self.get_lattices_id(dispatch_id=dispatch_id)
        if lattice_id is None:
            raise HTTPException(status_code=400, detail=[f"{dispatch_id} does not exists"])

        # Get all electron associated with sub lattice and lattice
        electron_id = self.get_electron_id(lattice_id=lattice_id)
        if electron_id is None:
            raise HTTPException(status_code=400, detail=["Something went wrong"])

        # Get list of nodes
        nodes = self.get_nodes(lattice_id=lattice_id)
        if nodes is None:
            nodes = None

        # Get list of electron dependency
        links = self.get_links(electron_id=electron_id)
        if links is None:
            links = None
        return GraphResponse(dispatch_id=lattice_id[1], graph={"nodes": nodes, "links": links})
