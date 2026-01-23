# import os
# import json
# from collections import defaultdict

# def count_dicts_in_json_files(folder_path, output_txt_path=None):
#     """
#     统计每个JSON文件的列表中字典的数量，并将结果保存到txt文件中
    
#     Args:
#         folder_path (str): 文件夹路径
#         output_txt_path (str, optional): 输出txt文件路径。如果为None，则使用默认路径
        
#     Returns:
#         tuple: (统计结果字典, 总JSON文件数量, 空项列表)
#     """
#     # 统计结果：文件路径 -> 字典数量
#     dict_count_stats = {}
#     total_json_count = 0
#     empty_items = []  # 存储空JSON文件/列表和空文件夹
#     file_errors = []  # 存储有错误的文件
    
#     # 默认输出路径
#     if output_txt_path is None:
#         output_txt_path = os.path.join(folder_path, "json_dict_count_report.txt")
    
#     # 检查文件夹是否存在
#     if not os.path.exists(folder_path):
#         print(f"错误：文件夹 '{folder_path}' 不存在")
#         return {}, 0, []
    
#     # 遍历文件夹及其所有子文件夹
#     for root, dirs, files in os.walk(folder_path):
#         # 检查当前文件夹是否有JSON文件
#         json_files_in_dir = [f for f in files if f.endswith('.json')]
#         has_json_files = len(json_files_in_dir) > 0
        
#         # 如果文件夹没有JSON文件且不是根目录，则认为是空文件夹
#         if not has_json_files and root != folder_path:
#             empty_items.append(os.path.relpath(root, folder_path))
        
#         # 处理当前文件夹中的JSON文件
#         for filename in json_files_in_dir:
#             total_json_count += 1
#             file_path = os.path.join(root, filename)
#             relative_path = os.path.relpath(file_path, folder_path)
            
#             try:
#                 # 读取并解析JSON文件
#                 with open(file_path, 'r', encoding='utf-8') as file:
#                     content = file.read().strip()
                    
#                     # 检查是否为空文件
#                     if not content:
#                         empty_items.append(relative_path)
#                         dict_count_stats[relative_path] = 0
#                         continue
                    
#                     # 解析JSON内容
#                     data = json.loads(content)
                    
#                     # 检查是否是列表
#                     if isinstance(data, list):
#                         # 统计列表中字典的数量
#                         dict_count = sum(1 for item in data if isinstance(item, dict))
                        
#                         # 记录统计结果
#                         dict_count_stats[relative_path] = dict_count
                        
#                         # 如果是空列表，添加到空项列表
#                         if dict_count == 0:
#                             empty_items.append(relative_path)
#                     else:
#                         # 如果不是列表，则记录为0个字典
#                         dict_count_stats[relative_path] = 0
#                         file_errors.append(f"{relative_path}: 文件内容不是列表格式")
                        
#             except json.JSONDecodeError:
#                 dict_count_stats[relative_path] = 0
#                 file_errors.append(f"{relative_path}: JSON格式错误")
#                 print(f"警告：文件 '{file_path}' 不是有效的JSON格式")
#             except Exception as e:
#                 dict_count_stats[relative_path] = 0
#                 file_errors.append(f"{relative_path}: 读取错误 - {str(e)}")
#                 print(f"读取文件 '{file_path}' 时出错: {e}")
    
#     # 将统计结果保存到txt文件
#     try:
#         with open(output_txt_path, 'w', encoding='utf-8') as f:
#             # 写入标题
#             f.write("JSON文件字典数量统计报告\n")
#             f.write("=" * 50 + "\n\n")
            
#             # 写入汇总信息
#             f.write(f"统计时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
#             f.write(f"扫描文件夹: {folder_path}\n")
#             f.write(f"总JSON文件数: {total_json_count}\n")
#             f.write(f"已统计文件数: {len(dict_count_stats)}\n\n")
            
#             # 按字典数量排序
#             sorted_items = sorted(dict_count_stats.items(), key=lambda x: x[1], reverse=True)
            
#             # 写入每个文件的详细统计
#             f.write("各文件字典数量统计:\n")
#             f.write("-" * 50 + "\n")
            
#             # 按照字典数量分组统计
#             count_distribution = defaultdict(int)
#             for path, count in dict_count_stats.items():
#                 count_distribution[count] += 1
            
#             # 写入数量分布
#             f.write("\n字典数量分布:\n")
#             for count in sorted(count_distribution.keys()):
#                 f.write(f"  字典数量 {count}: {count_distribution[count]} 个文件\n")
            
#             # 写入详细列表
#             f.write("\n\n详细文件列表:\n")
#             f.write("-" * 80 + "\n")
#             f.write(f"{'文件路径':<60} {'字典数量':>10}\n")
#             f.write("-" * 80 + "\n")
            
#             for path, count in sorted_items:
#                 f.write(f"{path:<60} {count:>10}\n")
            
#             # 写入空文件和文件夹信息
#             if empty_items:
#                 f.write(f"\n\n空文件和文件夹 ({len(empty_items)} 个):\n")
#                 f.write("-" * 80 + "\n")
#                 for item in sorted(empty_items):
#                     f.write(f"{item}\n")
            
#             # 写入错误信息
#             if file_errors:
#                 f.write(f"\n\n文件错误信息 ({len(file_errors)} 个):\n")
#                 f.write("-" * 80 + "\n")
#                 for error in file_errors:
#                     f.write(f"{error}\n")
            
#             # 写入统计摘要
#             f.write("\n" + "=" * 50 + "\n")
#             f.write("统计摘要:\n")
#             if dict_count_stats:
#                 total_dicts = sum(dict_count_stats.values())
#                 avg_dicts = total_dicts / len(dict_count_stats)
#                 max_dicts = max(dict_count_stats.values())
#                 max_file = max(dict_count_stats.items(), key=lambda x: x[1])[0]
                
#                 f.write(f"字典总数: {total_dicts}\n")
#                 f.write(f"平均每个文件字典数: {avg_dicts:.2f}\n")
#                 f.write(f"最大字典数: {max_dicts} (文件: {max_file})\n")
#                 f.write(f"空文件/列表数: {len([c for c in dict_count_stats.values() if c == 0])}\n")
            
#         print(f"统计结果已保存到: {output_txt_path}")
        
#     except Exception as e:
#         print(f"保存统计结果到txt文件时出错: {e}")
    
#     # 计算空列表文件数量（字典数量为0的文件）
#     empty_list_count = sum(1 for count in dict_count_stats.values() if count == 0)
    
#     return dict_count_stats, total_json_count, empty_items


# # 如果需要导入datetime模块，请确保在文件开头添加
# import datetime

# # 使用示例
# if __name__ == "__main__":
#     # 示例用法
#     folder_path = "D:\project08\MCP_AI\data\schoolTeachers"
#     output_file = "statistics_report.txt"
    
#     stats, total_files, empty_items = count_dicts_in_json_files(folder_path, output_file)
    
#     print(f"\n统计完成:")
#     print(f"总JSON文件数: {total_files}")
#     print(f"已统计文件数: {len(stats)}")
#     print(f"空项数量: {len(empty_items)}")
    
#     # 显示前10个文件的结果
#     print("\n字典数量最多的前10个文件:")
#     sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
#     for i, (path, count) in enumerate(sorted_stats[:10], 1):
#         print(f"{i:2}. {path}: {count} 个字典")





import os
import json
import glob
from pathlib import Path
"""
统计指定文件夹下所有json文件中字典的数量
"""
def count_dicts_in_json_files(folder_path, output_file='empty_items5.txt'):
    """
    统计指定文件夹下所有json文件中字典的数量
    
    参数:
        folder_path: 输入文件夹路径
        output_file: 输出txt文件名
    """
    
    # 确保输出文件路径正确
    output_path = Path(output_file)
    
    # 检查输入文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"错误：文件夹 '{folder_path}' 不存在！")
        return
    
    print(f"开始处理文件夹: {folder_path}")
    
    results = []
    total_dicts = 0
    total_json_files = 0
    
    try:
        # 遍历二级文件夹
        second_level_dirs = [d for d in os.listdir(folder_path) 
                           if os.path.isdir(os.path.join(folder_path, d))]
        
        if not second_level_dirs:
            print(f"警告：在 '{folder_path}' 中未找到二级文件夹")
            return
        
        for second_dir in second_level_dirs:
            second_dir_path = os.path.join(folder_path, second_dir)
            
            # 遍历三级文件夹
            third_level_dirs = [d for d in os.listdir(second_dir_path) 
                              if os.path.isdir(os.path.join(second_dir_path, d))]
            
            for third_dir in third_level_dirs:
                third_dir_path = os.path.join(second_dir_path, third_dir)
                
                # 查找json文件
                json_files = glob.glob(os.path.join(third_dir_path, '*.json'))
                
                # 只处理第一个json文件（根据要求至多有一个）
                if json_files:
                    json_file = json_files[0]  # 取第一个json文件
                    
                    relative_path = os.path.relpath(json_file, folder_path)
                    try:
                        # 读取并解析json文件
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # 统计字典数量
                        dict_count = 0
                        
                        if isinstance(data, dict):
                            # 如果json本身是一个字典
                            dict_count = 1
                            dict_type = "字典"
                        elif isinstance(data, list):
                            # 如果json是一个列表，统计列表中的字典数量
                            dict_count = sum(1 for item in data if isinstance(item, dict))
                            dict_type = f"列表中的字典"
                        else:
                            dict_type = "其他类型（无字典）"
                        
                        # 记录结果
                        results.append({
                            'path': relative_path,
                            'count': dict_count,
                            'type': dict_type
                        })
                        
                        total_dicts += dict_count
                        total_json_files += 1
                        
                        print(f"已处理: {json_file} - 找到{dict_count}个字典")
                        
                    except json.JSONDecodeError as e:
                        print(f"错误：无法解析JSON文件 '{json_file}': {e}")
                        results.append({
                            'path': relative_path,
                            'count': 0,
                            'type': f"JSON解析错误: {str(e)}"
                        })
                    except Exception as e:
                        print(f"错误：处理文件 '{json_file}' 时出错: {e}")
                        results.append({
                            'path': relative_path,
                            'count': 0,
                            'type': f"处理错误: {str(e)}"
                        })
        
        # 对results列表进行排序：按照result['path']以'_'分割后的第一部分转为int类型进行排序
        results.sort(key=lambda r: int(r['path'].split('_')[0]) if '_' in r['path'] and r['path'].split('_')[0].isdigit() else 0)
        
        # 将结果写入txt文件
        with open(output_path, 'w', encoding='utf-8') as f:        
            for i, result in enumerate(results, 1):
                if result['count'] < 20 and result['count'] != 0:
                    f.write(f"{result['path']}\n")
            
        
    except Exception as e:
        print(f"程序执行出错: {e}")
        import traceback
        traceback.print_exc()

# 使用示例函数
def main():
    # 示例用法1：直接指定文件夹路径
    folder_path = 'D:\project08\MCP_AI\data\schoolTeachers'

    
    # 运行统计
    count_dicts_in_json_files(folder_path)
    
    # 示例用法2：如果你想指定输出文件名
    # count_dicts_in_json_files(folder_path, "my_dict_count.txt")

if __name__ == "__main__":
    main()
