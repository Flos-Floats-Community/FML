import json
import os

# 版本JSON文件路径
version_json_path = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", ".minecraft", "versions", "26.1-snapshot-5", "26.1-snapshot-5.json")

print(f"检查文件: {version_json_path}")

if os.path.exists(version_json_path):
    print("文件存在")
    
    # 读取并解析JSON文件
    with open(version_json_path, 'r', encoding='utf-8') as f:
        try:
            version_data = json.load(f)
            print("JSON文件解析成功")
            
            # 检查downloads部分
            if "downloads" in version_data:
                print("找到downloads部分")
                
                if "client" in version_data["downloads"]:
                    print("找到client部分")
                    client_data = version_data["downloads"]["client"]
                    print(f"客户端JAR URL: {client_data.get('url', 'N/A')}")
                    print(f"客户端JAR大小: {client_data.get('size', 'N/A')} 字节")
                    print(f"客户端JAR SHA1: {client_data.get('sha1', 'N/A')}")
                else:
                    print("未找到client部分")
            else:
                print("未找到downloads部分")
                
            # 检查mainClass
            if "mainClass" in version_data:
                print(f"mainClass: {version_data['mainClass']}")
            else:
                print("未找到mainClass")
                
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
else:
    print("文件不存在")
