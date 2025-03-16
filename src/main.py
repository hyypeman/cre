from langchain_core.messages import SystemMessage, HumanMessage
from typing import Literal, Dict, Any, List
import os
import logging

from langgraph.graph import START, StateGraph, END
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
        self.input_state = InputState(address=address)
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
        # Build the graph with checkpointing to handle parallel execution
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

        # Phase 1: Initial data collection
        self.workflow.add_edge(START, "initialize")

        # Run data collection in parallel
        self.workflow.add_edge("initialize", "zola_search")
        self.workflow.add_edge("initialize", "acris_search")
        self.workflow.add_edge("initialize", "property_shark_search")

        # Process ACRIS documents when available
        self.workflow.add_conditional_edges(
            "acris_search",
            lambda state: self._has_documents(state),
            {True: "process_documents", False: "analyze_owner"},
        )

        # Connect data sources to analyzer
        self.workflow.add_edge("zola_search", "analyze_owner")
        self.workflow.add_edge("property_shark_search", "analyze_owner")
        self.workflow.add_edge("process_documents", "analyze_owner")

        # Phase 2: LLC resolution and people search
        self.workflow.add_conditional_edges(
            "analyze_owner",
            lambda state: state.get("owner_type", "").lower() == "llc",
            {True: "search_opencorporates", False: "search_skipgenie"},
        )

        # Phase 3: People search and completion
        self.workflow.add_edge("search_opencorporates", "search_skipgenie")
        self.workflow.add_edge("search_skipgenie", "search_true_people")
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

    def compile(self):
        """Compile the workflow"""
        return self.workflow.compile()

    def run(self, state=None):
        """Run the workflow with the given state or the initialized input state"""
        app = self.compile()

        if state is None:
            # Initialize the state with default values
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
                current_step="starting workflow",
                next_steps=["initialize"],
                errors=[],
            )

        # Run the graph
        logger.info(f"Starting property research workflow for {state['address']}")
        result = app.invoke(state)
        logger.info("Property research workflow completed")

        # Update the final state
        result["current_step"] = "workflow completed"
        result["next_steps"] = []

        return result


def main():
    """Run the property research workflow."""
    # Get address from user input
    address = input("Enter property address to research: ")
    if not address:
        address = "798 LEXINGTON AVENUE, New York, NY"
        print(f"Using default address: {address}")

    # Create and run the workflow
    graph = PropertyResearchGraph(address=address)

    # Save workflow visualization
    try:
        app = graph.compile()
        image = Image(app.get_graph().draw_mermaid_png())
        with open("workflow_diagram.png", "wb") as f:
            f.write(image.data)
        print("Workflow diagram saved as workflow_diagram.png")
    except Exception as e:
        logger.warning(f"Could not save workflow diagram: {e}")

    # Run the workflow
    result = graph.run()

    # Print results
    if result["errors"]:
        print("\nErrors encountered during research:")
        for error in result["errors"]:
            print(f"- {error}")

    print("\nFinal Ownership Information:")
    print(f"Owner Name: {result.get('owner_name', 'Unknown')}")
    print(f"Owner Type: {result.get('owner_type', 'Unknown')}")
    print(f"Contact Number: {result.get('contact_number', 'Not available')}")
    print(f"Address: {result.get('address', 'Unknown')}")

    return result


if __name__ == "__main__":
    main()
