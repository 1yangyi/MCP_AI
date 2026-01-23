
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
result = parse_schools_data(filename)
print(result)
# print(result)
path1 = 'D:\project08\MCP_AI\data\output_chinese'
path2 = 'D:\project08\MCP_AI\data\output_chinese4'
count = 0
# exit(0)
for school, colleges in result.items():
    count += 1
    source_file = os.path.join(path1, f"{count}_{school}_schools_result.json")
    target_file = os.path.join(path2, f"{count}_{school}_schools_result.json")
    if os.path.exists(source_file):
        with open(source_file, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
        err_list = []
        for data in source_data:
            if data['name'] in result[school]:
                err_list.append(data)
        err_json = json.dumps(err_list, ensure_ascii=False, indent=2)
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(err_json)
    else:
        print(f"Source file not found for {source_file}")