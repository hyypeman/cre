from langchain_core.messages import SystemMessage, HumanMessage
from typing import Literal, Dict, Any, List
import os
import logging

from langgraph.graph import START, StateGraph, END
from langgraph.graph.graph import CompiledGraph
from dotenv import load_dotenv
from IPython.display import Image
from .state import InputState, PropertyResearchState
from .nodes import (
    InitializerNode,
    ZolaNode,
    AcrisNode,
    DocumentProcessorNode,
    AnalyzerNode,
    PropertySharkNode,
    OpenCorporatesNode,
    SkipGenieNode,
    TruePeopleSearchNode,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class PropertyResearchGraph:
    def __init__(self, address=None):
        self.address = address

        # Initialize InputState
        self.input_state = InputState(address=address)

        # Initialize nodes and build workflow
        self._init_nodes()
        self._build_workflow()

    def _init_nodes(self):
        """Initialize all workflow nodes"""
        self.initializer = InitializerNode()
        self.zola_node = ZolaNode()
        self.acris_node = AcrisNode()
        self.document_processor = DocumentProcessorNode()
        self.property_shark_node = PropertySharkNode()
        self.opencorporates_node = OpenCorporatesNode()
        self.skipgenie_node = SkipGenieNode()
        self.true_people_search_node = TruePeopleSearchNode()
        self.analyzer = AnalyzerNode()

    def _build_workflow(self):
        """Configure the state graph workflow"""
        # Build the graph
        self.workflow = StateGraph(PropertyResearchState)

        # Add nodes
        self.workflow.add_node("initialize", self.initializer.run)
        self.workflow.add_node("zola_search", self.zola_node.run)
        self.workflow.add_node("acris_search", self.acris_node.run)
        self.workflow.add_node("process_documents", self.document_processor.run)
        self.workflow.add_node("property_shark_search", self.property_shark_node.run)
        self.workflow.add_node("search_opencorporates", self.opencorporates_node.run)
        self.workflow.add_node("search_skipgenie", self.skipgenie_node.run)
        self.workflow.add_node("search_true_people", self.true_people_search_node.run)
        self.workflow.add_node("analyze_owner", self.analyzer.run)

        # Define a parallel branch for initial data collection
        def join_parallel_results(state_dict):
            """Join results from parallel branches into a single state."""
            # Start with the state from any branch (they all have the same input)
            joined_state = state_dict["zola_search"].copy()

            # Add results from each branch
            if "acris_search" in state_dict:
                joined_state["acris_property_records"] = state_dict["acris_search"].get(
                    "acris_property_records"
                )

                # If documents were processed, include those results
                if "process_documents" in state_dict:
                    joined_state["property_ownership_records"] = state_dict[
                        "process_documents"
                    ].get("property_ownership_records")

            if "property_shark_search" in state_dict:
                joined_state["property_shark_ownership_data"] = state_dict[
                    "property_shark_search"
                ].get("property_shark_ownership_data")

            # Combine errors from all branches
            all_errors = []
            for branch_name, branch_state in state_dict.items():
                if branch_state.get("errors"):
                    all_errors.extend(branch_state["errors"])
            joined_state["errors"] = all_errors

            # Set current step
            joined_state["current_step"] = "Initial data collection completed"
            joined_state["next_steps"] = ["extract_owner_info"]

            return joined_state

        # Add edges
        self.workflow.add_edge(START, "initialize")

        # Set up parallel branches for initial data collection
        self.workflow.add_edge("initialize", "zola_search")
        self.workflow.add_edge("initialize", "acris_search")
        self.workflow.add_edge("initialize", "property_shark_search")

        # ACRIS documents processing branch
        self.workflow.add_conditional_edges(
            "acris_search", self._has_documents, {True: "process_documents", False: None}
        )

        # Join parallel branches
        self.workflow.add_parallel_branch_join(
            ["zola_search", "acris_search", "process_documents", "property_shark_search"],
            join_parallel_results,
            "analyze_owner",
        )

        # After analysis, check if we need to search OpenCorporates
        self.workflow.add_conditional_edges(
            "analyze_owner",
            self._is_llc_owner,
            {True: "search_opencorporates", False: "search_skipgenie"},
        )

        # Connect OpenCorporates to SkipGenie
        self.workflow.add_edge("search_opencorporates", "search_skipgenie")

        # Connect SkipGenie to TruePeopleSearch
        self.workflow.add_edge("search_skipgenie", "search_true_people")

        # Connect TruePeopleSearch to END
        self.workflow.add_edge("search_true_people", END)

    def _has_documents(self, state: PropertyResearchState) -> bool:
        """Check if ACRIS returned documents that need processing."""
        if not state.get("acris_property_records"):
            return False

        acris_results = state["acris_property_records"]
        return (
            isinstance(acris_results, dict)
            and "files" in acris_results
            and len(acris_results["files"]) > 0
        )

    def _is_llc_owner(self, state: PropertyResearchState) -> bool:
        """Check if the owner is an LLC and needs OpenCorporates search."""
        return state.get("owner_type", "").lower() == "llc"

    def compile(self):
        """Compile the workflow"""
        return self.workflow.compile()

    def run(self, state=None):
        """Run the workflow with the given state or the initialized input state"""
        app = self.compile()

        if state is None:
            # Initialize the full PropertyResearchState from the input state
            state = PropertyResearchState(
                address=self.input_state["address"],
                zola_owner_name=None,
                acris_property_records=None,
                property_ownership_records=None,
                property_shark_ownership_data=None,
                company_registry_data=None,
                person_search_results=None,
                owner_name=None,
                owner_type=None,
                contact_number=None,
                current_step="",
                next_steps=[],
                errors=[],
            )

        # Run the graph
        logger.info(f"Starting property research workflow for {state['address']}")
        result = app.invoke(state)
        logger.info("Property research workflow completed")
        return result


def main():
    """
    Main function to run the property research workflow.

    1. Gets the property address from user input
    2. Creates and compiles the workflow graph
    3. Saves a visualization of the workflow
    4. Runs the workflow and returns the results
    """
    # Get address from user input
    address = input("Enter property address to research: ")
    if not address:
        address = "798 LEXINGTON AVENUE, New York, NY"
        print(f"Using default address: {address}")

    # Create and compile the graph
    graph = PropertyResearchGraph(address=address)
    app = graph.compile()

    # Save workflow visualization
    try:
        image = Image(app.get_graph().draw_mermaid_png())
        with open("workflow_diagram.png", "wb") as f:
            f.write(image.data)
        print("Workflow diagram saved as workflow_diagram.png")
    except Exception as e:
        logger.warning(f"Could not save workflow diagram: {e}")

    # Run the workflow
    result = graph.run()

    # Print any errors encountered
    if result["errors"]:
        print("\nErrors encountered during research:")
        for error in result["errors"]:
            print(f"- {error}")

    # Print final ownership information
    print("\nFinal Ownership Information:")
    print(f"Owner Name: {result.get('owner_name', 'Unknown')}")
    print(f"Owner Type: {result.get('owner_type', 'Unknown')}")
    print(f"Contact Number: {result.get('contact_number', 'Not available')}")
    print(f"Address: {result.get('address', 'Unknown')}")

    return result


if __name__ == "__main__":
    main()
