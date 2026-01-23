import json
import os

dir_path = r'd:\project08\MCP_AI\data\output_chinese3'

total_pairs = 0
no_url = 0
for filename in os.listdir(dir_path):
    if filename.endswith('.json'):
        file_path = os.path.join(dir_path, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    # if item['URL'] == '' or item['URL'] is None or not item['URL'].startswith('http'):
                    if item['URL'] == '' or item['URL'] is None:
                        no_url += 1
                    if item['URL'] is not None and item['URL'] != '':
                        if not item['URL'].startswith('http'):
                            print(file_path +'----------'+ item['name'])
                if isinstance(data, list):
                    total_pairs += len(data)
        except Exception as e:
            print(f"Error processing {filename}: {e}")

print(f"Total name-URL pairs: {total_pairs}")
print(f"Total pairs with no URL: {no_url}")


