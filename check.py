import os

def delete_empty_folders(folder_path):
    """
    删除指定文件夹及其子文件夹中的所有空文件夹
    """
    # 使用 os.walk 遍历所有子文件夹（从最深层的开始）
    for root, dirs, files in os.walk(folder_path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            
            # 检查文件夹是否为空
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                    print(f"已删除空文件夹: {dir_path}")
                except OSError as e:
                    print(f"删除文件夹失败 {dir_path}: {e}")


from src.config import PROJECT_ROOT
import json
MIDDLE_FILE_DIR = PROJECT_ROOT / "middle_file2"
try:
    # Load school websites
    chinese_schools_path = PROJECT_ROOT / "data" / "input" / "chinese_schoolsURL.json"
    with open(chinese_schools_path, 'r', encoding='utf-8') as f:
        schools_data = json.load(f)
except Exception as e:
    print(f"加载学校数据失败: {str(e)}")
    exit(1)
rank = 0
input_dir = PROJECT_ROOT / "data" / "output_chinese2"
output_base = PROJECT_ROOT / "data" / "schools2"
deleted_folders = []
for school in schools_data:
    university_name = school['name']
    website = school['website']
    rank += 1
    # if rank != 3:
    #     continue
    if website == '':
        # print(f"学校: {university_name} 没有网址")
        continue
    try:
        matching_files = list(input_dir.glob(f"*_{university_name}_schools_result.json"))
        if not matching_files:
            print(f"Skipping {university_name}: no JSON file found in output_chinese")
            continue
        if len(matching_files) > 1:
            print(f"Warning: Multiple JSON files found for {university_name}, using the first one")
        json_path = matching_files[0]
        print(f"Processing university: {university_name} using {json_path}\n")
        with open(json_path, 'r', encoding='utf-8') as f:
            colleges = json.load(f)
    except Exception as e:
        print(f"处理大学 {university_name} 时发生异常: {str(e)}")
        continue

    output_dir = output_base / f"{rank}_{university_name}"

    for college in colleges:
        try:
            college_name = college["name"]
            college_url = college["URL"]
            print(f"学院: {college_name} 网址: {college_url}")
            if college_url == '':
                continue
            if not college_url.startswith("http"):
                delete_college_file = output_dir / college_name
                delete_empty_folders(delete_college_file)
                deleted_folders.append(delete_college_file)
        except Exception as e:
            print(f"处理学院 {college_name} 时发生异常: {str(e)}")
            continue
print(f"共删除了 {len(deleted_folders)} 个空文件夹")
print(deleted_folders)
