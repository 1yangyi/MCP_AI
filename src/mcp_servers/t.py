import json
import os
from pathlib import Path

def read_school_json(file_path):
    """
    读取指定的school.json文件
    
    参数:
    file_path (str): JSON文件的完整路径
    
    返回:
    dict: 解析后的JSON数据，如果出错则返回None
    """
    try:
        # 将路径转换为Path对象
        json_file = Path(file_path)
        
        # 检查文件是否存在
        if not json_file.exists():
            print(f"错误: 文件 '{file_path}' 不存在")
            return None
        
        # 检查是否为JSON文件
        if json_file.suffix.lower() != '.json':
            print(f"错误: 文件 '{file_path}' 不是JSON文件")
            return None
        
        # 读取JSON文件
        with open(json_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
            print(f"成功读取文件: {json_file.name}")
            return data
            
    except json.JSONDecodeError as e:
        print(f"错误: 文件 '{json_file.name}' 不是有效的JSON格式 - {str(e)}")
        return None
    except Exception as e:
        print(f"读取文件 '{json_file.name}' 时出错: {str(e)}")
        return None

# 使用示例
if __name__ == "__main__":
    # 指定文件路径
    json_file_path = r"D:\project08\MCP_AI\data\input\top500_school_websites.json"
    
    # 读取JSON文件
    school_data = read_school_json(json_file_path)
    for item in school_data:
        print(item["school"])
        print(item["website"])
        print(item)
    
    
    # # 处理读取到的数据
    # if school_data is not None:
    #     print("\n文件内容摘要:")
    #     print(f"数据类型: {type(school_data)}")
        
        
    #     # 如果是列表，显示长度和前几个元素
    #     if isinstance(school_data, list):
    #         print(f"列表长度: {len(school_data)}")
            
    #         if school_data:
    #             print("\n前几个元素:")
    #             for i, item in enumerate(school_data[:3]):  # 只显示前3个元素
    #                 print(f"[{i}]: {item}")
    #             if len(school_data) > 3:
    #                 print(f"... 还有 {len(school_data) - 3} 个元素")
    # else:
    #     print("未能成功读取JSON文件")


