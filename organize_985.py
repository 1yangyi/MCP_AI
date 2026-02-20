import os
import shutil

# Paths
base_dir = r"e:\1_2026上半年\MCP\MCP\MCP_AI\data"
source_dir = os.path.join(base_dir, "schoolTeachers")
dest_dir = os.path.join(base_dir, "985_universities")

# 985 Universities List
universities_985 = [
    "北京大学", "中国人民大学", "清华大学", "北京航空航天大学", "北京理工大学", 
    "中国农业大学", "北京师范大学", "中央民族大学", "南开大学", "天津大学", 
    "大连理工大学", "东北大学", "吉林大学", "哈尔滨工业大学", "复旦大学", 
    "同济大学", "上海交通大学", "华东师范大学", "南京大学", "东南大学", 
    "浙江大学", "中国科学技术大学", "厦门大学", "山东大学", "中国海洋大学", 
    "武汉大学", "华中科技大学", "湖南大学", "中南大学", "国防科技大学", 
    "中山大学", "华南理工大学", "四川大学", "电子科技大学", "重庆大学", 
    "西安交通大学", "西北工业大学", "西北农林科技大学", "兰州大学"
]

def organize():
    if not os.path.exists(source_dir):
        print(f"Source directory not found: {source_dir}")
        return

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        print(f"Created destination directory: {dest_dir}")

    files = os.listdir(source_dir)
    print(f"Found {len(files)} items in source directory.")

    count = 0
    for item in files:
        src_path = os.path.join(source_dir, item)
        
        if not os.path.isdir(src_path):
            continue

        # Check if folder name matches any of the 985 university names
        # Format is usually "Rank_Name", e.g., "10_天津大学"
        matched_uni = None
        
        # Split by underscore to handle "Rank_Name" format
        parts = item.split('_', 1)
        folder_uni_name = parts[1] if len(parts) > 1 else item
        
        if folder_uni_name in universities_985:
            matched_uni = folder_uni_name
        
        if matched_uni:
            dest_path = os.path.join(dest_dir, item)
            print(f"Copying {item} to {dest_dir}...")
            
            if os.path.exists(dest_path):
                print(f"  Skipping {item}, already exists.")
            else:
                try:
                    shutil.copytree(src_path, dest_path)
                    count += 1
                except Exception as e:
                    print(f"  Error copying {item}: {e}")

    print(f"Operation complete. Copied {count} folders.")

if __name__ == "__main__":
    print("Starting organization script...")
    organize()
