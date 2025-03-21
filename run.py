#!/usr/bin/env python3
"""
Property Research System - Entry point script

This script runs the property research workflow from the root directory,
properly handling all imports.
"""

import argparse
import ast
import os
import pandas as pd
from src.main import PropertyResearchGraph


def check_existing_addresses(addresses):
    """
    Check which addresses already exist in the spreadsheet.

    Args:
        addresses: List of addresses to check

    Returns:
        tuple: (existing_addresses, new_addresses)
    """
    # Path to the spreadsheet
    excel_path = os.path.join(os.getcwd(), "results", "property_owners.xlsx")

    # If spreadsheet doesn't exist, all addresses are new
    if not os.path.exists(excel_path):
        return [], addresses

    try:
        # Load the spreadsheet
        df = pd.read_excel(excel_path)

        # Get existing addresses
        existing_addresses = set(df["Property Address"].values)

        # Separate addresses into existing and new
        already_processed = [addr for addr in addresses if addr in existing_addresses]
        to_process = [addr for addr in addresses if addr not in existing_addresses]

        return already_processed, to_process
    except Exception as e:
        print(f"Error checking existing addresses: {e}")
        # In case of error, assume all addresses are new
        return [], addresses


def process_addresses(addresses=None):
    """
    Process a list of addresses using the property research workflow.

    Args:
        addresses: Optional list of addresses to process. If None, addresses will be
                 requested via interactive input.

    Returns:
        List of results for each address
    """
    # Create the workflow graph
    graph = PropertyResearchGraph()

    # Compile the graph once
    graph.compile()

    # Save workflow visualization
    graph.visualize()

    # If no addresses provided, get them from user input
    if addresses is None:
        addresses = []
        print("Enter addresses one by one:")
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

    # Check which addresses are already processed
    already_processed, to_process = check_existing_addresses(addresses)

    # Print info about already processed addresses
    if already_processed:
        print(f"\nSkipping {len(already_processed)} already processed addresses:")
        for addr in already_processed:
            print(f"  - {addr}")

    # If all addresses are already processed, return early
    if not to_process:
        print("\nAll addresses have already been processed. Nothing to do.")
        return []

    # Process the remaining addresses
    total_to_process = len(to_process)
    print(f"\nProcessing {total_to_process} new addresses...")

    # Process each address using the same compiled graph
    results = []
    for idx, address in enumerate(to_process):
        remaining = total_to_process - idx - 1
        print(f"\n[{idx + 1}/{total_to_process}] Processing address: {address}")
        print(f"Remaining addresses: {remaining}")

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
        print(f"Contact Number: {result.get('contact_number', 'Not available')}")
        print(f"Address: {result.get('address', 'Unknown')}")

        if remaining > 0:
            print(f"\nNext address: {to_process[idx + 1]}")

    print(f"\nProcessed {len(results)} new addresses")
    print(f"Skipped {len(already_processed)} existing addresses")
    print(f"Total: {len(already_processed) + len(results)} addresses")
    return results


def main():
    """Command-line entry point with support for address list argument."""
    parser = argparse.ArgumentParser(description="Property Research System")
    parser.add_argument(
        "--addresses",
        "-a",
        type=str,
        help="List of addresses to process, formatted as a Python list string. Example: \"['123 Main St, NY', '456 Park Ave, NY']\"",
    )
    parser.add_argument(
        "--file", "-f", type=str, help="Path to a text file containing addresses, one per line"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Process all addresses even if they already exist in the spreadsheet",
    )

    args = parser.parse_args()

    # Get addresses from arguments
    addresses = None

    # Process addresses from a file if provided
    if args.file:
        try:
            with open(args.file, "r") as f:
                addresses = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error reading address file: {e}")
            return []

    # Process addresses from command line argument if provided
    if args.addresses:
        try:
            # Parse the string representation of a list into an actual Python list
            addresses = ast.literal_eval(args.addresses)
            if not isinstance(addresses, list):
                raise ValueError("Addresses must be provided as a list")
        except Exception as e:
            print(f"Error parsing addresses: {e}")
            print("Make sure the addresses are formatted as a Python list string.")
            print("Example: \"['123 Main St, NY', '456 Park Ave, NY']\"")
            return []

    # If force flag is used, clear the addresses_to_skip list
    if args.force and addresses:
        print(
            "Force flag is set - will process all addresses even if they already exist in spreadsheet"
        )
        return process_addresses(addresses)

    # Run the processor with whatever addresses we have
    return process_addresses(addresses)


if __name__ == "__main__":
    main()
