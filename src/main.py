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
    TwilioNode,
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
        """Initialize the property research graph.

        Args:
            address: Optional initial address to research
        """
        self.address = address
        self.input_state = InputState(address=address) if address else None
        self._init_nodes()
        self._build_workflow()
        self.compiled_app = None

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
        self.twilio_node = TwilioNode()
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
        self.workflow.add_node("verify_phone", self.twilio_node.run)
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
        
        # Add phone verification after people search
        self.workflow.add_conditional_edges(
            "search_true_people",
            lambda state: state.get("owner_name") is not None,  # Process all results that have an owner
            {True: "verify_phone", False: END},
        )
        self.workflow.add_edge("verify_phone", END)

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
        """Compile the workflow and cache the compiled app.

        Returns:
            The compiled workflow app
        """
        if self.compiled_app is None:
            logger.info("Compiling property research workflow")
            self.compiled_app = self.workflow.compile()
        return self.compiled_app

    def set_address(self, address):
        """Set a new address for research without recompiling the graph.

        Args:
            address: The property address to research

        Returns:
            self: For method chaining
        """
        self.address = address
        self.input_state = InputState(address=address)
        return self

    def create_initial_state(self):
        """Create an initial state for the workflow based on the current address.

        Returns:
            PropertyResearchState: The initial state for the workflow
        """
        if not self.address:
            raise ValueError("Address must be set before creating initial state")

        return PropertyResearchState(
            address=self.address,
            zola_owner_name=None,
            acris_property_records=None,
            property_ownership_records=None,
            property_shark_ownership_data=None,
            company_registry_data=None,
            person_search_results=None,
            owner_name=None,
            owner_type=None,
            phone_verification=None,
            phone_number_valid=None,
            phone_analysis=None,
            contact_number=None,
            current_step="starting workflow",
            next_steps=["initialize"],
            errors=[],
        )

    def run(self, address=None):
        """Run the workflow with the given address or the current address.

        Args:
            address: Optional new address to research (will update the current address)

        Returns:
            The final state after workflow completion
        """
        # Update address if provided
        if address:
            self.set_address(address)

        if not self.address:
            raise ValueError("Address must be set before running the workflow")

        # Ensure the workflow is compiled
        app = self.compile()

        # Create initial state
        state = self.create_initial_state()

        # Run the graph
        logger.info(f"Starting property research workflow for {state['address']}")
        result = app.invoke(state)
        logger.info("Property research workflow completed")

        # Update the final state
        result["current_step"] = "workflow completed"
        result["next_steps"] = []

        return result

    def visualize(self, output_path="workflow_diagram.png"):
        """Generate and save a visualization of the workflow.

        Args:
            output_path: Path to save the visualization image

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            app = self.compile()
            image = Image(app.get_graph().draw_mermaid_png())
            with open(output_path, "wb") as f:
                f.write(image.data)
            logger.info(f"Workflow diagram saved as {output_path}")
            return True
        except Exception as e:
            logger.warning(f"Could not save workflow diagram: {e}")
            return False


def main():
    """Run the property research workflow."""
    # Create the workflow graph (without an initial address)
    graph = PropertyResearchGraph()

    # Compile the graph once
    graph.compile()

    # Save workflow visualization
    graph.visualize()

    # Process multiple addresses
    addresses = []

    # Get addresses from user input
    while True:
        address = input("Enter property address to research (or 'done' to finish): ")
        if address.lower() == "done":
            break
        if not address:
            continue
        addresses.append(address)

    # Use default address if none provided
    if not addresses:
        addresses = ["798 LEXINGTON AVENUE, New York, NY"]
        print(f"Using default address: {addresses[0]}")

    # Process each address using the same compiled graph
    results = []
    for address in addresses:
        print(f"\nResearching address: {address}")
        result = graph.run(address)
        results.append(result)

        # Print results
        if result["errors"]:
            print("\nErrors encountered during research:")
            for error in result["errors"]:
                print(f"- {error}")

        print("\nOwnership Information:")
        print(f"Owner Name: {result.get('owner_name', 'Unknown')}")
        print(f"Owner Type: {result.get('owner_type', 'Unknown')}")
        
        # Display phone information with enhanced validation info
        print("\nPhone Information:")
        if result.get("phone_analysis") and result["phone_analysis"].get("primary_phone"):
            primary = result["phone_analysis"]["primary_phone"]
            print(f"Primary Phone: {primary.get('formatted', 'Unknown')} (Verified)")
            
            # Show all valid phones
            if result["phone_analysis"].get("valid_phones"):
                print("\nAll Valid Phone Numbers:")
                for i, phone in enumerate(result["phone_analysis"]["valid_phones"], 1):
                    print(f"  {i}. {phone.get('formatted', phone.get('number', 'Unknown'))}")
        else:
            print(f"Contact Number: {result.get('contact_number', 'Not available')} (Not verified)")
            
        print(f"Address: {result.get('address', 'Unknown')}")

    print(f"\nProcessed {len(results)} addresses")
    return results


if __name__ == "__main__":
    main()
