from langchain_core.messages import SystemMessage, HumanMessage
from typing import Literal
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
        self.workflow.add_node("analyze_owner", self.analyzer.run)

        # Add edges
        self.workflow.add_edge(START, "initialize")
        self.workflow.add_edge("initialize", "zola_search")
        self.workflow.add_edge("zola_search", "acris_search")

        # Conditional edge from acris_search
        self.workflow.add_conditional_edges(
            "acris_search", self._has_documents, {True: "process_documents", False: "analyze_owner"}
        )

        # Connect document processor to conditional check for owner info
        self.workflow.add_conditional_edges(
            "process_documents",
            self._has_owner_info,
            {True: "search_opencorporates", False: "property_shark_search"},
        )

        # Connect property shark to conditional check for owner info
        self.workflow.add_conditional_edges(
            "property_shark_search",
            self._has_owner_info,
            {True: "search_opencorporates", False: "analyze_owner"},
        )

        # Connect opencorporates to analyzer
        self.workflow.add_edge("search_opencorporates", "analyze_owner")

        # Connect analyzer to end
        self.workflow.add_edge("analyze_owner", END)

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

    def _has_owner_info(self, state: PropertyResearchState) -> bool:
        """Check if we have owner information (name or LLC) to proceed with."""
        return state.get("owner_name") is not None

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

    return result


if __name__ == "__main__":
    main()
