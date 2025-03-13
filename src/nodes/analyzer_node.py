import logging
import re
import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from ..state import PropertyResearchState

logger = logging.getLogger(__name__)


class AnalyzerNode:
    """Node for analyzing collected data and determining owner information."""

    def __init__(self, model_name="gpt-4o", temperature=0):
        """Initialize the analyzer node."""
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)

    def run(self, state: PropertyResearchState) -> PropertyResearchState:
        """
        Analyze data to determine owner information.

        1. Extracts owner information from ZoLa and ACRIS data
        2. Determines if the owner is an individual or LLC/company
        3. Sets this as the final output of the workflow
        """
        logger.info("🧠 Analyzing property data to determine owner information")
        print("🧠 Analyzing property data to determine owner information")

        try:
            # Extract owner information with LLM
            owner_info = self._extract_owner_info(state)

            # Print the owner information as JSON
            owner_output = {
                "owner_name": owner_info["owner_name"],
                "owner_type": owner_info["owner_type"],
                "confidence": owner_info["confidence"],
                "address": state["address"],
            }

            print("\n" + "=" * 50)
            print("PROPERTY OWNERSHIP INFORMATION")
            print("=" * 50)
            print(json.dumps(owner_output, indent=2))
            print("=" * 50)

            # Create the final state
            final_state = {
                **state,
                "owner_name": owner_info["owner_name"],
                "owner_type": owner_info["owner_type"],
                "current_step": "Analysis completed",
                "next_steps": ["complete"],
            }

            # Print the full research state as JSON
            print("\n" + "=" * 50)
            print("PROPERTY RESEARCH STATE")
            print("=" * 50)

            # Create a simplified version of the state for display
            display_state = {
                k: v for k, v in final_state.items() if v is not None and k != "errors"
            }
            if state["errors"]:
                display_state["errors"] = state["errors"]

            print(json.dumps(display_state, indent=2, default=str))
            print("=" * 50)

            return final_state

        except Exception as e:
            error_msg = f"Owner analysis error: {str(e)}"
            logger.error(error_msg)

            return {
                **state,
                "errors": state["errors"] + [error_msg],
                "current_step": "Owner analysis failed",
                "next_steps": ["complete"],
            }

    def _extract_owner_info(self, state: PropertyResearchState) -> dict:
        """Extract owner information using LLM."""
        logger.info("Extracting owner information with LLM")

        # Prepare the prompt for the LLM
        prompt = f"""
        Analyze the following property ownership information:
        
        Address: {state["address"]}
        ZoLa Results: {state.get("zola_results", "Not available")}
        ACRIS Results: {state.get("acris_results", "Not available")}
        Document Analysis: {state.get("documents", "Not available")}
        
        Extract and provide ONLY the following in JSON format:
        1. owner_name: The most likely owner name (individual or company)
        2. owner_type: Either "individual", "llc", "corporation", or "unknown"
        3. confidence: Your confidence level (high, medium, low)
        """

        messages = [
            SystemMessage(
                content="You are a property ownership research expert. Extract owner information from the data."
            ),
            HumanMessage(content=prompt),
        ]

        response = self.llm.invoke(messages)
        content = response.content

        # Extract key information using regex
        owner_name_match = re.search(r'"owner_name"\s*:\s*"([^"]+)"', content)
        owner_type_match = re.search(r'"owner_type"\s*:\s*"([^"]+)"', content)
        confidence_match = re.search(r'"confidence"\s*:\s*"([^"]+)"', content)

        owner_name = owner_name_match.group(1) if owner_name_match else "Unknown"
        owner_type = owner_type_match.group(1) if owner_type_match else "unknown"
        confidence = confidence_match.group(1) if confidence_match else "low"

        logger.info(f"Extracted owner: {owner_name} ({owner_type}), confidence: {confidence}")

        return {"owner_name": owner_name, "owner_type": owner_type, "confidence": confidence}
