import os
import shutil

# Paths
base_dir = r"e:\1_2026上半年\MCP\MCP\MCP_AI\data"
source_dir = os.path.join(base_dir, "985_universities")
dest_dir = os.path.join(base_dir, "selected_departments")

# Keywords based on user input
# 1. "信息技术管理" -> Covered by "信息", "计算机", "管理" (if IT related), "电子", "通信", "软件", "网络", "智能"
# 2. "计算机" -> Covered by "计算机", "软件", "计算", "网络", "智能", "人工智能"
# 3. "生命医学学科" -> Covered by "生命", "生物", "医", "药", "卫生", "护理"

keywords = [
    # IT & Computer & Management related
    "计算机", "软件", "网络", "智能", "人工智能", "计算",
    "信息", "电子", "通信", "自动化", "微电子",
    # Life Sciences & Medicine related
    "生命", "生物", "医", "药", "卫生", "护理", "临床", "基础医学", "公共卫生", "口腔"
]

def filter_departments():
    if not os.path.exists(source_dir):
        print(f"Source directory not found: {source_dir}")
        return

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        print(f"Created destination directory: {dest_dir}")

    universities = os.listdir(source_dir)
    print(f"Scanning {len(universities)} universities...")

    total_dept_count = 0
    copied_dept_count = 0

    for uni in universities:
        uni_src_path = os.path.join(source_dir, uni)
        
        if not os.path.isdir(uni_src_path):
            continue

        # Check departments within the university
        departments = os.listdir(uni_src_path)
        matched_depts = []

        for dept in departments:
            dept_src_path = os.path.join(uni_src_path, dept)
            if not os.path.isdir(dept_src_path):
                continue
            
            total_dept_count += 1
            
            # Check if department name contains any keyword
            is_match = False
            for kw in keywords:
                if kw in dept:
                    is_match = True
                    break
            
            if is_match:
                matched_depts.append(dept)

        if matched_depts:
            uni_dest_path = os.path.join(dest_dir, uni)
            if not os.path.exists(uni_dest_path):
                os.makedirs(uni_dest_path)
            
            print(f"Processing {uni}: Found {len(matched_depts)} matching departments.")
            
            for dept in matched_depts:
                dept_src = os.path.join(uni_src_path, dept)
                dept_dest = os.path.join(uni_dest_path, dept)
                
                if os.path.exists(dept_dest):
                    # print(f"  Skipping {dept}, already exists.")
                    pass
                else:
                    try:
                        shutil.copytree(dept_src, dept_dest)
                        copied_dept_count += 1
                    except Exception as e:
                        print(f"  Error copying {dept}: {e}")

    print(f"\nOperation complete.")
    print(f"Total departments scanned: {total_dept_count}")
    print(f"Matching departments copied: {copied_dept_count}")

if __name__ == "__main__":
    filter_departments()
