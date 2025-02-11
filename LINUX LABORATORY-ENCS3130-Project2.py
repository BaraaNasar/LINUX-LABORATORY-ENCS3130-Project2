#######################################################

#Students Names:
    #Baraa Nasar-1210880
    #Ro'A Gaith-1210832

#######################################################

import json
import re
from datetime import datetime

def convert_units(value, unit):
    """Convert value to standardized units (e.g., bytes, bits, percentage)."""
    if unit == "G":  # If the unit is Gigabit, convert to bits (1 G = 10^9 bits)
        return value * 10**9
    if unit == "GB":  # If it's Gigabytes, convert to Bytes (1 GB = 1024^3 bytes)
        return value * 1024**3
    if unit == "Gbit":  # For Gigabits, convert to bits
        return value * 10**9
    if unit == "Mbps":  # If it's Megabits, convert to bits (1 Mbps = 10^6 bps)
        return value * 10**6
    if unit == "KB":  # Convert KB to Bytes (1 KB = 1024 bytes)
        return value * 1024
    if unit == "B":  # Bytes to Bytes (standardized)
        return value
    if unit == "%":  # Percentage (no change)
        return value
    if unit == "TB":  # Convert Terabytes to Bytes (1 TB = 1024^4 bytes)
        return value * 1024**4
    if unit == "Mb":  # Convert Megabytes to Bytes (1 MB = 1024^2 bytes)
        return value * 1024**2
    return value  # Default return if no conversion needed

def extract_unit_and_value(value):
    # Ensure the value is a string
    if isinstance(value, int):
        value = str(value)  # Convert to string if it's an integer

    # Skip values that represent IP addresses or non-numeric data
    if re.match(r"\d+\.\d+\.\d+\.\d+", value.strip()):  # Regex for IP address pattern
        return None, None

    # Now it's safe to apply string methods like strip
    match = re.match(r"([0-9\.]+)\s*([a-zA-Z]+)?", value.strip())

    if match:
        try:
            numeric_value = float(match.group(1))  # Convert to float
            unit = match.group(2) if match.group(2) else None
            return numeric_value, unit
        except ValueError:  # Handle cases where the conversion fails
            return None, None
    else:
        return None, None



def normalize(value):
    """Normalize values by removing units and standardizing the value to bytes."""
    if isinstance(value, str):
        value = value.strip().replace("_", "").replace('"', '').lower()
        value = value.replace("%", "")  # Remove percentage symbol

    # Extract numeric value and unit from the value string
    numeric_value, unit = extract_unit_and_value(value)

    if numeric_value is not None:
        # Convert the numeric value to standardized units (bytes)
        if unit == 'kb' or unit == 'kb':
            standardized_value = convert_units(numeric_value, 'KB')  # Convert KB to bytes
        else:
            standardized_value = convert_units(numeric_value, unit)

        return round(standardized_value, 2)  # Round to 2 decimal places for precision

    # If value doesn't need conversion, return as string
    try:
        return float(value)  # Try converting to float if it's not numeric
    except ValueError:
        return value.strip().lower()  # Return the value as is if conversion fails




# Update the comparison to handle the tolerance-based check
def compare_with_tolerance(value1, value2, tolerance=0.01):
    """Compare two values with a tolerance."""
    try:
        # Attempt to convert the values to float for numeric comparison
        value1 = float(value1)
        value2 = float(value2)
    except ValueError:
        # If the values cannot be converted to float, compare them as strings
        # Normalize strings (remove leading/trailing spaces and convert to lower case)
        value1 = str(value1).strip().lower()
        value2 = str(value2).strip().lower()

    # Compare numbers or strings
    if isinstance(value1, float) and isinstance(value2, float):
        return abs(value1 - value2) <= (tolerance * max(value1, value2))
    elif isinstance(value1, str) and isinstance(value2, str):
        return value1 == value2
    return False


class DataComparator:
    @staticmethod
    def compare(gnmi_output, cli_outputs):
        discrepancies = []
        matches = []

        # Flatten gNMI JSON for easier comparison
        def flatten_json(data, parent_key=''):
            items = []
            for key, value in data.items():
                new_key = f"{parent_key}.{key}" if parent_key else key
                if isinstance(value, dict):
                    items.extend(flatten_json(value, new_key).items())
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        items.extend(flatten_json(item, f"{new_key}[{i}]").items())
                else:
                    items.append((new_key, value))
            return dict(items)

        gnmi_flat = flatten_json(gnmi_output)

        # Compare gNMI and CLI values
        for key, gnmi_value in gnmi_flat.items():
            found = False
            for cli_output in cli_outputs:
                if key in cli_output:
                    found = True
                    cli_value = cli_output[key]

                    # Normalize both gNMI and CLI values
                    gnmi_normalized = normalize(gnmi_value)
                    cli_normalized = normalize(cli_value)

                    # Compare values with tolerance using the new compare_with_tolerance function
                    if compare_with_tolerance(gnmi_normalized, cli_normalized, tolerance=0.01):
                        matches.append(f"Match for key '{key}': gNMI={gnmi_value}, CLI={cli_value}")
                    else:
                        discrepancies.append(
                            f"Mismatch for key '{key}': gNMI={gnmi_value}, CLI={cli_value}"
                        )

            if not found:
                discrepancies.append(f"Missing key '{key}' in CLI outputs.")

        # Check for extra keys in CLI outputs
        for cli_output in cli_outputs:
            for key in cli_output:
                if key not in gnmi_flat:
                    discrepancies.append(f"Extra key '{key}' found in CLI outputs.")

        return discrepancies, matches


def load_json_file(file_path):
    """Load JSON data from a file."""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

def load_cli_files(file_paths):
    """Load and parse CLI outputs from multiple files."""
    cli_outputs = []
    for file_path in file_paths:
        try:
            parsed_data = {}
            with open(file_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    if ':' in line:
                        if ',' in line:
                            # Handle multiple values in a single line
                            pairs = line.split(',')
                            for pair in pairs:
                                key, value = pair.split(":", 1)
                                key = key.strip()
                                value = value.strip().strip('"')  # Remove quotes here
                                if key == "neighbor_id" or key == "state":
                                    index = len([k for k in parsed_data.keys() if k.startswith("adjacencies[")]) // 2
                                    parsed_data[f"adjacencies[{index}].{key}"] = value
                                else:
                                    parsed_data[key] = value
                        else:
                            key, value = line.split(":", 1)
                            key = key.strip()
                            value = value.strip().strip('"')  # Remove quotes here
                            parsed_data[key] = value
            cli_outputs.append(parsed_data)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
    return cli_outputs

def write_results_to_file(file_path, discrepancies, matches, gnmi_path, cli_paths):
    """Write the results to a file, appending new data while preserving previous content."""
    with open(file_path, 'a') as file:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        file.write(f"\n--- Run at {timestamp} ---\n")

        # Log input paths
        file.write(f"gNMI file path: {gnmi_path}\n")
        file.write(f"CLI file paths: {', '.join(cli_paths)}\n")

        # Log results
        if discrepancies:
            file.write("\nDiscrepancies found:\n")
            for discrepancy in discrepancies:
                file.write(f"- {discrepancy}\n")
        else:
            file.write("\nAll values match; no discrepancies found.\n")

        if matches:
            file.write("\nMatches found:\n")
            for match in matches:
                file.write(f"- {match}\n")
        else:
            file.write("\nNo matches found.\n")

        file.write("\n" + "-" * 40 + "\n")

def main():
    # Get file paths from user
    gnmi_file_path = input("Enter the path to the gNMI output file (JSON format): ").strip()
    cli_file_paths = input(
        "Enter the paths to the CLI output files (key-value format), separated by commas: "
    ).strip().split(',')
    result_file_path = input("Enter the path to save the output results file: ").strip()

    # Load data from files
    gnmi_output = load_json_file(gnmi_file_path)
    cli_outputs = load_cli_files(cli_file_paths)

    if gnmi_output is None or not cli_outputs:
        with open(result_file_path, 'a') as file:
            file.write("\nError: Failed to load input files.\n")
        return

    comparator = DataComparator()
    discrepancies, matches = comparator.compare(gnmi_output, cli_outputs)

    # Write results to file
    write_results_to_file(result_file_path, discrepancies, matches, gnmi_file_path, cli_file_paths)
    print(f"\nResults written to file: {result_file_path}")

if __name__ == "__main__":
    main()



