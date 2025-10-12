from asyncio.windows_events import NULL
from src.config import PROJECT_ROOT
from urllib.parse import urljoin
input_dir = PROJECT_ROOT / "data" / "input"
if __name__ == "__main__":
    # Load school websites from JSON file
    import json
    chinese_schools_path = input_dir / "top500_school_websites.json"
    with open(chinese_schools_path, 'r', encoding='utf-8') as f:
        schools_data = json.load(f)
    school_urls = {school['school']: school['website'] for school in schools_data}

    input_dir = PROJECT_ROOT / "data" / "output"
    empty_count = 0
    empty_list = []
    lost_count = 0
    lost_list = []
    """
    以下被注释的部分为URL拼接功能
    """
    spliced_list = []

    for school in schools_data:
        university_name = school['school']
        school_website = school['website']
        matching_files = list(input_dir.glob(f"*_{university_name}_schools_result.json"))
        if not matching_files:
            #print(f" {university_name} json文件不存在")
            lost_count += 1
            lost_list.append(json_path)
            continue
        if len(matching_files) > 1:
            print(f" {university_name} 存在多个json文件，使用第一个: {matching_files[0]}")
            print(f" 其他json文件: {matching_files[1:]}")
        json_path = matching_files[0]

        with open(json_path, 'r', encoding='utf-8') as f:
            colleges = json.load(f)
            if len(colleges) == 0:
                # print(f" {university_name} 没有学院信息: {json_path}")
                empty_count += 1
                empty_list.append(json_path)
                continue
            # updated = False
            # for college in colleges:
            #     if "URL" not in college:
            #         print(f" {university_name} {college['name']} 没有URL信息")
            #         break
            #     college_name = college["name"]
            #     college_url = college["URL"]
            #     if college_url is None:
            #         break
            #     if not college_url.startswith("http"):
            #         print(f" {university_name} {college_name} URL 不是绝对路径: {college_url}")
            #         spliced_url = urljoin(school_website, college_url)
            #         print(school_website)
            #         print(f" 尝试拼接为: {spliced_url}")
            #         college["URL"] = spliced_url
            #         spliced_list.append(f"{university_name} - {college_name}")
            #         updated = True
            # if updated:
            #     with open(json_path, 'w', encoding='utf-8') as f:
            #         json.dump(colleges, f, ensure_ascii=False, indent=4)
            #     print(f"更新了 {university_name} 的 JSON 文件: {json_path}")
    print(f"{empty_count}个学校没有学院信息:")
    for item in empty_list:
        print(item)
    print(f"{lost_count}个学校json文件不存在:")
    for item in lost_list:
        print(item)
    # print("进行了拼接的学校和学院:")
    # for item in spliced_list:
    #     print(item)
