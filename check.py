from pathlib import Path
import json
from typing import List, Dict, Any


def get_project_paths() -> Dict[str, Path]:
    """
    Resolve key paths relative to this check.py file.
    Returns a dict with:
    - input_file: path to MCP_AI/data/input/top500_school_websites.json
    - output_dir: path to MCP_AI/data/output
    """
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    input_file = data_dir / "input" / "top500_school_websites.json"
    output_dir = data_dir / "output"
    return {"input_file": input_file, "output_dir": output_dir}


def load_school_list(json_path: Path) -> List[Dict[str, Any]]:
    """Load the list of schools from the given JSON file."""
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def expected_filename(rank: Any, school: str) -> str:
    """Build the expected output file name for a given school entry."""
    return f"{rank}_{school}_schools_result.json"


def find_missing_outputs(entries: List[Dict[str, Any]], output_dir: Path) -> List[List[Any]]:
    """
    For each entry in the input list, check if the corresponding output file exists in output_dir.
    If not, collect the corresponding values in a list: [rank, school, website], and
    return a big list containing all such school lists.
    """
    missing: List[List[Any]] = []

    for item in entries:
        rank = item.get("rank")
        school = item.get("school")
        website = item.get("website")

        filename = expected_filename(rank, school)
        expected_path = output_dir / filename

        if not expected_path.exists():
            # Collect the corresponding values into a list: [rank, school, website]
            missing.append([rank, school, website])

    return missing


# New: importable function
def get_missing_list() -> List[List[Any]]:
    """
    可被 import 的函数：返回缺失结果文件的学校列表（每项为 [rank, school, website]）。
    """
    paths = get_project_paths()
    input_file: Path = paths["input_file"]
    output_dir: Path = paths["output_dir"]

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Even if output_dir does not exist, treat all entries as missing; no early return.
    entries = load_school_list(input_file)
    missing_list = find_missing_outputs(entries, output_dir)
    return missing_list


def main() -> None:
    # Use the importable function and keep CLI behavior
    missing_list = get_missing_list()
    print(json.dumps(missing_list, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()