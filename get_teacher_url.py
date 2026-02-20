
def parse_schools_data(filename):
    schools = {}
    
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
                
            # 分割学校部分和学院部分
            parts = line.split('\\')
            
            # 提取学校名称（去掉前面的编号_）
            school_part = parts[0]
            if '_' in school_part:
                school_name = school_part.split('_', 1)[1]
                school_rank = int(school_part.split('_', 1)[0])
            else:
                school_name = school_part
                school_rank = 0
                
            # 如果学校不在字典中，初始化一个空列表
            if school_name not in schools:
                schools[school_name] = []
            
            # 如果有学院信息，提取学院名称
            if len(parts) > 1:
                college_part = parts[1]
                # 去掉学院名称中的文件后缀
                if college_part.endswith('_teachers.json'):
                    college_name = college_part.rsplit('_teachers.json', 1)[0]
                else:
                    college_name = college_part
                
                # 如果学院不在该学校的列表中，则添加
                if college_name not in schools[school_name]:
                    schools[school_name].append(college_name)
    
    return schools

import os
import json

filename = "empty_items5.txt"
# Ensure we read empty_items5.txt from the same directory as the script
script_dir = os.path.dirname(os.path.abspath(__file__))
filename_path = os.path.join(script_dir, filename)

if not os.path.exists(filename_path):
    print(f"Error: {filename_path} does not exist.")
    exit(1)

result = parse_schools_data(filename_path)
print(f"Loaded {len(result)} schools from {filename}")

path1 = os.path.join(script_dir, 'data', 'output_chinese')
path2 = os.path.join(script_dir, 'data', 'output_chinese4')

if not os.path.exists(path2):
    os.makedirs(path2)

# Build a mapping from school name to actual filename in path1
# to handle rank mismatches
school_file_map = {}
if os.path.exists(path1):
    for fname in os.listdir(path1):
        if fname.endswith('_schools_result.json'):
            # fname format expected: "Rank_SchoolName_schools_result.json"
            # Remove suffix
            prefix = fname[:-len('_schools_result.json')]
            # Split rank and name
            if '_' in prefix:
                try:
                    _, name = prefix.split('_', 1)
                    school_file_map[name] = fname
                except ValueError:
                    continue
else:
    print(f"Error: Data directory {path1} does not exist.")
    exit(1)

count_processed = 0
count_missing = 0

for school_name, colleges in result.items():
    if school_name in school_file_map:
        source_filename = school_file_map[school_name]
        source_file = os.path.join(path1, source_filename)
        target_file = os.path.join(path2, source_filename)
        
        if os.path.exists(source_file):
            try:
                with open(source_file, 'r', encoding='utf-8') as f:
                    source_data = json.load(f)
                
                err_list = []
                for data in source_data:
                    # Check if 'name' exists in data
                    if 'name' in data and data['name'] in colleges:
                        err_list.append(data)
                
                if err_list:
                    err_json = json.dumps(err_list, ensure_ascii=False, indent=2)
                    with open(target_file, 'w', encoding='utf-8') as f:
                        f.write(err_json)
                    count_processed += 1
                else:
                    print(f"No matching colleges found in {source_filename} for {school_name}")
                    
            except Exception as e:
                print(f"Error processing {source_filename}: {e}")
        else:
            print(f"Source file not found (physically): {source_file}")
    else:
        print(f"Source file not found for school: {school_name} (Looked in {path1})")
        count_missing += 1

print(f"Processing complete. Processed {count_processed} files. Missing/Skipped {count_missing} schools.")
