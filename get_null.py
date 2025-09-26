from pathlib import Path
import json
from typing import List, Dict, Any, Optional, Tuple


def _get_project_paths() -> Dict[str, Path]:
    """
    Resolve key paths relative to this get_null.py file.
    Returns a dict with:
    - input_file: path to MCP_AI/data/input/top500_school_websites.json
    - output_dir: path to MCP_AI/data/output
    """
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    input_file = data_dir / "input" / "top500_school_websites.json"
    output_dir = data_dir / "output"
    return {"input_file": input_file, "output_dir": output_dir}


def _load_school_list(json_path: Path) -> List[Dict[str, Any]]:
    """Load the list of schools from the given JSON file."""
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_school_index(entries: List[Dict[str, Any]]) -> Dict[Tuple[Any, str], Dict[str, Any]]:
    """Build an index mapping (rank, school) -> entry dict for quick lookup."""
    index: Dict[Tuple[Any, str], Dict[str, Any]] = {}
    for item in entries:
        index[(item.get("rank"), item.get("school"))] = item
    return index


def _parse_output_filename(path: Path) -> Optional[Tuple[int, str]]:
    """
    Parse output file name like "123_某某大学_schools_result.json" and return (rank, school_name).
    Returns None if the filename doesn't match expected pattern.
    """
    name = path.name
    suffix = "_schools_result.json"
    if not name.endswith(suffix):
        return None
    base = name[: -len(suffix)]
    # base expected like: "123_某某大学"
    pos = base.find("_")
    if pos == -1:
        return None
    rank_str = base[:pos]
    school = base[pos + 1 :]
    try:
        rank = int(rank_str)
    except ValueError:
        return None
    return rank, school


def _is_empty_list_json(file_path: Path) -> bool:
    """Return True if the JSON content is an empty list ([])."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, list) and len(data) == 0
    except Exception:
        # Any read/parse error treats as not-empty for safety
        return False


def get_null_list() -> List[List[Any]]:
    """
    顺序读取 data/output 文件夹下的所有 JSON 文件；
    如果某个 JSON 文件内容是空列表，则根据该文件名中的序号和学校名，
    在 data/input/top500_school_websites.json 中找到对应的学校信息，
    将该学校的 [rank, school, website] 追加到 null_list 中；最后返回 null_list。
    """
    paths = _get_project_paths()
    input_file: Path = paths["input_file"]
    output_dir: Path = paths["output_dir"]

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    if not output_dir.exists():
        # 如果输出目录不存在，显然也没有空列表文件，返回空列表
        return []

    entries = _load_school_list(input_file)
    index = _build_school_index(entries)

    # 收集并按照 (rank, school) 顺序排序
    files: List[Path] = [p for p in output_dir.glob("*.json")]

    def sort_key(p: Path):
        parsed = _parse_output_filename(p)
        # 文件名不符合预期时，放到末尾
        if parsed is None:
            return (float("inf"), p.name)
        rank, school = parsed
        return (rank, school)

    files.sort(key=sort_key)

    null_list: List[List[Any]] = []

    for file_path in files:
        if not _is_empty_list_json(file_path):
            continue

        parsed = _parse_output_filename(file_path)
        if not parsed:
            # 跳过不符合命名规范的文件
            continue
        rank, school = parsed

        # 先尝试 (rank, school) 精确匹配
        entry = index.get((rank, school))

        # 兼容处理：若精确匹配失败，尝试仅按学校名匹配（考虑部分排名更新/并列等情况）
        if entry is None:
            for item in entries:
                if item.get("school") == school:
                    entry = item
                    break

        # 若仍未找到，作为保守处理：尝试按 rank 匹配到第一条
        if entry is None:
            for item in entries:
                if item.get("rank") == rank:
                    entry = item
                    break

        if entry is None:
            # 未找到对应学校信息，跳过
            continue

        null_list.append([entry.get("rank"), entry.get("school"), entry.get("website")])

    return null_list


def main() -> None:
    result = get_null_list()
    for item in result:
        print(item)
    print(f"Total null schools: {len(result)}")


if __name__ == "__main__":
    main()