from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict
from typing import Literal, List, Dict, Any, Optional
import os

from langgraph.graph import START, StateGraph, END
from langgraph.prebuilt import ToolNode
from zola_scraper import lookup_zola_owner
from acris_scraper import search_acris
from social_media_search import search_social_media
from document_processor import extract_text_from_pdf
from dotenv import load_dotenv
from IPython.display import display, Image

# Load environment variables
load_dotenv()


# Define the state
class PropertyResearchState(TypedDict):
    address: str
    zola_results: Optional[str]
    acris_results: Optional[str]
    social_media_results: Optional[Dict]
    documents: Optional[List[Dict]]
    owner_info: Optional[Dict]
    current_step: str
    next_steps: List[str]
    errors: List[str]
    final_report: Optional[str]


# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Define the nodes


def initialize_research(state: PropertyResearchState) -> PropertyResearchState:
    """Initialize the research process with the given address."""
    print(f"🔍 Starting property research for: {state['address']}")
    return {
        **state,
        "current_step": "Initializing research",
        "next_steps": ["zola_search"],
        "errors": [],
    }


def zola_search(state: PropertyResearchState) -> PropertyResearchState:
    """Search ZoLa for property information."""
    print(f"🏢 Searching ZoLa for: {state['address']}")
    try:
        zola_results = lookup_zola_owner(state["address"])
        return {
            **state,
            "zola_results": zola_results,
            "current_step": "ZoLa search completed",
            "next_steps": ["acris_search"],
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [f"ZoLa search error: {str(e)}"],
            "current_step": "ZoLa search failed",
            "next_steps": ["acris_search"],  # Continue to next step even if this fails
        }


def acris_search(state: PropertyResearchState) -> PropertyResearchState:
    """Search ACRIS for property documents and ownership information."""
    print(f"📄 Searching ACRIS for: {state['address']}")
    try:
        acris_results = search_acris(state["address"])
        return {
            **state,
            "acris_results": acris_results,
            "current_step": "ACRIS search completed",
            "next_steps": ["process_documents"],
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [f"ACRIS search error: {str(e)}"],
            "current_step": "ACRIS search failed",
            "next_steps": ["social_media_search"],  # Skip document processing if ACRIS fails
        }


def process_documents(state: PropertyResearchState) -> PropertyResearchState:
    """Process any PDF documents found in ACRIS."""
    print("📑 Processing property documents")
    if not state.get("acris_results"):
        return {
            **state,
            "current_step": "Document processing skipped (no ACRIS results)",
            "next_steps": ["social_media_search"],
        }

    try:
        # This would extract text from PDFs found in ACRIS
        documents = []
        # For each document URL in acris_results, extract text
        # documents.append(extract_text_from_pdf(doc_url))

        return {
            **state,
            "documents": documents,
            "current_step": "Document processing completed",
            "next_steps": ["social_media_search"],
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [f"Document processing error: {str(e)}"],
            "current_step": "Document processing failed",
            "next_steps": ["social_media_search"],
        }


def social_media_search(state: PropertyResearchState) -> PropertyResearchState:
    """Search social media and business databases for owner information."""
    print("🌐 Searching social media and business databases")

    # Extract potential owner names from ZoLa and ACRIS results
    potential_owners = []
    if state.get("zola_results"):
        # Extract owner names from ZoLa results
        if "Owner:" in state["zola_results"]:
            owner = state["zola_results"].split("Owner:")[1].strip()
            potential_owners.append(owner)

    if not potential_owners:
        return {
            **state,
            "current_step": "Social media search skipped (no owner names found)",
            "next_steps": ["analyze_results"],
        }

    try:
        social_results = {}
        for owner in potential_owners:
            social_results[owner] = search_social_media(owner)

        return {
            **state,
            "social_media_results": social_results,
            "current_step": "Social media search completed",
            "next_steps": ["analyze_results"],
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [f"Social media search error: {str(e)}"],
            "current_step": "Social media search failed",
            "next_steps": ["analyze_results"],
        }


def analyze_results(state: PropertyResearchState) -> PropertyResearchState:
    """Analyze all collected data and generate a comprehensive report."""
    print("🧠 Analyzing results and generating report")

    # Prepare the prompt for the LLM
    prompt = f"""
    Analyze the following property ownership information and create a comprehensive report:
    
    Address: {state["address"]}
    
    ZoLa Results: {state.get("zola_results", "Not available")}
    
    ACRIS Results: {state.get("acris_results", "Not available")}
    
    Social Media Results: {state.get("social_media_results", "Not available")}
    
    Document Analysis: {state.get("documents", "Not available")}
    
    Errors encountered: {state.get("errors", [])}
    
    Please provide:
    1. The most likely owner(s) of the property
    2. Contact information found (if any)
    3. Business entities associated with the owner
    4. Confidence level in the findings
    5. Recommended next steps for further research
    """

    messages = [
        SystemMessage(
            content="You are a property ownership research expert. Analyze the provided information and create a detailed report."
        ),
        HumanMessage(content=prompt),
    ]

    response = llm.invoke(messages)

    return {
        **state,
        "final_report": response.content,
        "current_step": "Analysis completed",
        "next_steps": ["complete"],
    }


def route_next_step(
    state: PropertyResearchState,
) -> Literal[
    "zola_search",
    "acris_search",
    "process_documents",
    "social_media_search",
    "analyze_results",
    "complete",
]:
    """Determine the next step in the research process."""
    if not state.get("next_steps"):
        return "complete"

    next_step = state["next_steps"][0]
    if next_step == "zola_search":
        return "zola_search"
    elif next_step == "acris_search":
        return "acris_search"
    elif next_step == "process_documents":
        return "process_documents"
    elif next_step == "social_media_search":
        return "social_media_search"
    elif next_step == "analyze_results":
        return "analyze_results"
    else:
        return "complete"


def main():
    # Build the graph
    workflow = StateGraph(PropertyResearchState)

    # Add nodes
    workflow.add_node("initialize", initialize_research)
    workflow.add_node("zola_search", zola_search)
    workflow.add_node("acris_search", acris_search)
    workflow.add_node("process_documents", process_documents)
    workflow.add_node("social_media_search", social_media_search)
    workflow.add_node("analyze_results", analyze_results)

    # Add edges
    workflow.add_edge(START, "initialize")
    workflow.add_conditional_edges(
        "initialize", route_next_step, {"zola_search": "zola_search", "complete": END}
    )
    workflow.add_conditional_edges(
        "zola_search", route_next_step, {"acris_search": "acris_search", "complete": END}
    )
    workflow.add_conditional_edges(
        "acris_search",
        route_next_step,
        {
            "process_documents": "process_documents",
            "social_media_search": "social_media_search",
            "complete": END,
        },
    )
    workflow.add_conditional_edges(
        "process_documents",
        route_next_step,
        {"social_media_search": "social_media_search", "complete": END},
    )
    workflow.add_conditional_edges(
        "social_media_search",
        route_next_step,
        {"analyze_results": "analyze_results", "complete": END},
    )
    workflow.add_conditional_edges("analyze_results", route_next_step, {"complete": END})

    # Compile the graph
    app = workflow.compile()
    image = Image(app.get_graph().draw_mermaid_png())
    # Save the workflow diagram
    with open("workflow_diagram.png", "wb") as f:
        f.write(image.data)
    print("Workflow diagram saved as workflow_diagram.png")
    return app


if __name__ == "__main__":
    app = main()

    # Example usage
    address = input("Enter property address to research: ")
    if not address:
        address = "798 LEXINGTON AVENUE, New York, NY"
        print(f"Using default address: {address}")

    # Initialize the state
    initial_state = {
        "address": address,
        "zola_results": None,
        "acris_results": None,
        "social_media_results": None,
        "documents": None,
        "owner_info": None,
        "current_step": "",
        "next_steps": [],
        "errors": [],
        "final_report": None,
    }

    # Run the graph
    result = app.invoke(initial_state)

    # Print the final report
    print("\n" + "=" * 50)
    print("PROPERTY OWNERSHIP REPORT")
    print("=" * 50)
    print(result["final_report"])
    print("=" * 50)

    # Print any errors encountered
    if result["errors"]:
        print("\nErrors encountered during research:")
        for error in result["errors"]:
            print(f"- {error}")
