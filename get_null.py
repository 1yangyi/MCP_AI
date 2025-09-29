# from pathlib import Path
# import json
# from typing import List, Dict, Any, Optional, Tuple


# def _get_project_paths() -> Dict[str, Path]:
#     """
#     Resolve key paths relative to this get_null.py file.
#     Returns a dict with:
#     - input_file: path to MCP_AI/data/input/top500_school_websites.json
#     - output_dir: path to MCP_AI/data/output
#     """
#     base_dir = Path(__file__).resolve().parent
#     data_dir = base_dir / "data"
#     input_file = data_dir / "input" / "top500_school_websites.json"
#     output_dir = data_dir / "output"
#     return {"input_file": input_file, "output_dir": output_dir}


# def _load_school_list(json_path: Path) -> List[Dict[str, Any]]:
#     """Load the list of schools from the given JSON file."""
#     with json_path.open("r", encoding="utf-8") as f:
#         return json.load(f)


# def _build_school_index(entries: List[Dict[str, Any]]) -> Dict[Tuple[Any, str], Dict[str, Any]]:
#     """Build an index mapping (rank, school) -> entry dict for quick lookup."""
#     index: Dict[Tuple[Any, str], Dict[str, Any]] = {}
#     for item in entries:
#         index[(item.get("rank"), item.get("school"))] = item
#     return index


# def _parse_output_filename(path: Path) -> Optional[Tuple[int, str]]:
#     """
#     Parse output file name like "123_某某大学_schools_result.json" and return (rank, school_name).
#     Returns None if the filename doesn't match expected pattern.
#     """
#     name = path.name
#     suffix = "_schools_result.json"
#     if not name.endswith(suffix):
#         return None
#     base = name[: -len(suffix)]
#     # base expected like: "123_某某大学"
#     pos = base.find("_")
#     if pos == -1:
#         return None
#     rank_str = base[:pos]
#     school = base[pos + 1 :]
#     try:
#         rank = int(rank_str)
#     except ValueError:
#         return None
#     return rank, school


# def _is_empty_list_json(file_path: Path) -> bool:
#     """Return True if the JSON content is an empty list ([])."""
#     try:
#         with file_path.open("r", encoding="utf-8") as f:
#             data = json.load(f)
#         return isinstance(data, list) and len(data) == 0
#     except Exception:
#         # Any read/parse error treats as not-empty for safety
#         return False


# def get_null_list() -> List[List[Any]]:
#     """
#     顺序读取 data/output 文件夹下的所有 JSON 文件；
#     如果某个 JSON 文件内容是空列表，则根据该文件名中的序号和学校名，
#     在 data/input/top500_school_websites.json 中找到对应的学校信息，
#     将该学校的 [rank, school, website] 追加到 null_list 中；最后返回 null_list。
#     """
#     paths = _get_project_paths()
#     input_file: Path = paths["input_file"]
#     output_dir: Path = paths["output_dir"]

#     if not input_file.exists():
#         raise FileNotFoundError(f"Input file not found: {input_file}")
#     if not output_dir.exists():
#         # 如果输出目录不存在，显然也没有空列表文件，返回空列表
#         return []

#     entries = _load_school_list(input_file)
#     index = _build_school_index(entries)

#     # 收集并按照 (rank, school) 顺序排序
#     files: List[Path] = [p for p in output_dir.glob("*.json")]

#     def sort_key(p: Path):
#         parsed = _parse_output_filename(p)
#         # 文件名不符合预期时，放到末尾
#         if parsed is None:
#             return (float("inf"), p.name)
#         rank, school = parsed
#         return (rank, school)

#     files.sort(key=sort_key)

#     null_list: List[List[Any]] = []

#     for file_path in files:
#         if not _is_empty_list_json(file_path):
#             continue

#         parsed = _parse_output_filename(file_path)
#         if not parsed:
#             # 跳过不符合命名规范的文件
#             continue
#         rank, school = parsed

#         # 先尝试 (rank, school) 精确匹配
#         entry = index.get((rank, school))

#         # 兼容处理：若精确匹配失败，尝试仅按学校名匹配（考虑部分排名更新/并列等情况）
#         if entry is None:
#             for item in entries:
#                 if item.get("school") == school:
#                     entry = item
#                     break

#         # 若仍未找到，作为保守处理：尝试按 rank 匹配到第一条
#         if entry is None:
#             for item in entries:
#                 if item.get("rank") == rank:
#                     entry = item
#                     break

#         if entry is None:
#             # 未找到对应学校信息，跳过
#             continue

#         null_list.append([entry.get("rank"), entry.get("school"), entry.get("website")])

#     return null_list


# def main() -> None:
#     result = get_null_list()
#     for item in result:
#         print(item)
#     print(f"Total null schools: {len(result)}")


# if __name__ == "__main__":
#     main()


import os
import json

def count_empty_list_files(folder_path):
    """
    统计文件夹中空列表的JSON文件数量
    
    Args:
        folder_path (str): 文件夹路径
        
    Returns:
        tuple: (空列表文件数量, 总JSON文件数量, 空列表文件列表)
    """
    empty_list_count = 0
    total_json_count = 0
    empty_list_files = []
    
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"错误：文件夹 '{folder_path}' 不存在")
        return 0, 0, []
    
    # 遍历文件夹中的所有文件
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        # 只处理JSON文件
        if filename.endswith('.json') and os.path.isfile(file_path):
            total_json_count += 1
            
            try:
                # 读取并解析JSON文件
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read().strip()
                    
                    # 检查是否为空文件
                    if not content:
                        empty_list_count += 1
                        empty_list_files.append(filename)
                        continue
                    
                    # 解析JSON内容
                    data = json.loads(content)
                    
                    # 检查是否是空列表
                    if isinstance(data, list) and len(data) == 0:
                        empty_list_count += 1
                        empty_list_files.append(filename)
                        
            except json.JSONDecodeError:
                print(f"警告：文件 '{filename}' 不是有效的JSON格式")
            except Exception as e:
                print(f"读取文件 '{filename}' 时出错: {e}")
    
    return empty_list_count, total_json_count, empty_list_files

def main():
    # 设置文件夹路径（请修改为你的实际路径）
    folder_path = 'MCP_AI\data\output_chinese'
    
    # 如果没有输入路径，使用当前目录
    if not folder_path:
        folder_path = "."
    
    # 统计空列表文件
    empty_count, total_count, empty_files = count_empty_list_files(folder_path)
    
    # 输出结果
    print("\n" + "="*50)
    print("统计结果:")
    print(f"文件夹路径: {os.path.abspath(folder_path)}")
    print(f"总JSON文件数量: {total_count}")
    print(f"空列表文件数量: {empty_count}")
    print(f"空列表文件占比: {empty_count/total_count*100:.2f}%" if total_count > 0 else "空列表文件占比: 0%")
    
    if empty_files:
        print("\n空列表文件列表:")
        for i, filename in enumerate(empty_files, 1):
            print(f"{i}. {filename}")
    else:
        print("\n没有找到空列表的JSON文件")
    print("="*50)

# 更简洁的版本（如果你只需要基本功能）
def simple_count(folder_path):
    """简化版本，只返回数量"""
    count = 0
    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.loads(file.read())
                    if isinstance(data, list) and len(data) == 0:
                        count += 1
            except:
                continue
    return count

if __name__ == "__main__":
    main()
    
    # 如果你想直接使用，取消下面的注释并修改路径
    # result = count_empty_list_files("你的文件夹路径")
    # print(f"空列表文件数量: {result[0]}")