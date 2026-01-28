import sys
import os
import json
import requests
import webbrowser
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import concurrent.futures
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QComboBox, QFileDialog, 
    QProgressBar, QTextEdit, QTabWidget, QGroupBox, QCheckBox,
    QMessageBox, QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

# 忽略SSL证书验证
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

def get_ssl_verify():
    return False

def get_download_url(url):
    """获取加速下载链接"""
    # BMCLAPI加速源
    bmclapi_base = "https://bmclapi2.bangbang93.com"
    
    # 替换Mojang官方域名
    if "launchermeta.mojang.com" in url:
        return url.replace("https://launchermeta.mojang.com", bmclapi_base)
    elif "resources.download.minecraft.net" in url:
        return url.replace("https://resources.download.minecraft.net", f"{bmclapi_base}/assets")
    elif "libraries.minecraft.net" in url:
        return url.replace("https://libraries.minecraft.net", f"{bmclapi_base}/maven")
    elif "files.minecraftforge.net" in url:
        return url.replace("https://files.minecraftforge.net", f"{bmclapi_base}/forge")
    elif "piston-data.mojang.com" in url:
        # 处理piston-data域名的客户端JAR下载
        if "/client.jar" in url:
            # 提取版本ID和文件哈希
            parts = url.split("/")
            if len(parts) > 5:
                # 构建BMCLAPI格式的URL
                return f"{bmclapi_base}/version/{parts[-2]}/{parts[-1]}"
    
    return url

# 全局变量，用于存储授权码
g_auth_code = None
g_auth_error = None

# 缓存相关配置
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".float_launcher", "cache")
CACHE_EXPIRY = 24 * 60 * 60  # 缓存过期时间（秒）

# 确保缓存目录存在
os.makedirs(CACHE_DIR, exist_ok=True)

def save_to_cache(key, data):
    """保存数据到缓存"""
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    cache_data = {
        "data": data,
        "timestamp": int(datetime.now().timestamp())
    }
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2)

def load_from_cache(key):
    """从缓存加载数据"""
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(cache_file):
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 检查缓存是否过期
        if int(datetime.now().timestamp()) - cache_data["timestamp"] > CACHE_EXPIRY:
            os.remove(cache_file)
            return None
        
        return cache_data["data"]
    except Exception as e:
        print(f"加载缓存失败: {e}")
        if os.path.exists(cache_file):
            os.remove(cache_file)
        return None

def clear_cache():
    """清除所有缓存"""
    for file in os.listdir(CACHE_DIR):
        if file.endswith('.json'):
            os.remove(os.path.join(CACHE_DIR, file))

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global g_auth_code, g_auth_error
        
        try:
            # 解析URL
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # 检查是否有授权码
            if 'code' in query_params:
                g_auth_code = query_params['code'][0]
                
                # 发送成功响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write("<html><head><title>认证成功</title></head>".encode('utf-8'))
                self.wfile.write("<body><h1>认证成功！</h1>".encode('utf-8'))
                self.wfile.write("<p>您可以关闭此窗口并返回启动器。</p></body></html>".encode('utf-8'))
            elif 'error' in query_params:
                g_auth_error = query_params['error'][0]
                
                # 发送错误响应
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write("<html><head><title>认证失败</title></head>".encode('utf-8'))
                self.wfile.write("<body><h1>认证失败！</h1>".encode('utf-8'))
                self.wfile.write(("<p>错误: " + g_auth_error + "</p>").encode('utf-8'))
                self.wfile.write("<p>请返回启动器并重新尝试。</p></body></html>".encode('utf-8'))
            else:
                # 发送默认响应
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write("<html><head><title>Float Minecraft Launcher</title></head>".encode('utf-8'))
                self.wfile.write("<body><h1>欢迎使用Float Minecraft Launcher</h1>".encode('utf-8'))
                self.wfile.write("<p>此页面用于Microsoft账户认证回调。</p></body></html>".encode('utf-8'))
        except Exception as e:
            # 发送错误响应
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write("<html><head><title>服务器错误</title></head>".encode('utf-8'))
            self.wfile.write("<body><h1>服务器错误</h1>".encode('utf-8'))
            self.wfile.write("<p>请返回启动器并重新尝试。</p></body></html>".encode('utf-8'))
    
    def log_message(self, format, *args):
        # 禁用默认日志，避免干扰
        pass

class AuthThread(QThread):
    auth_complete = pyqtSignal(str)
    auth_error = pyqtSignal(str)
    
    def __init__(self, client_id, redirect_uri):
        super().__init__()
        self.client_id = client_id
        self.redirect_uri = redirect_uri
    
    def run(self):
        global g_auth_code, g_auth_error
        
        try:
            # 重置全局变量
            g_auth_code = None
            g_auth_error = None
            
            # 启动本地服务器
            server_address = ('', 5000)
            httpd = HTTPServer(server_address, OAuthHandler)
            
            # 在后台线程中启动服务器
            server_thread = threading.Thread(target=httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            # 构造授权URL
            auth_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
            params = {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "response_mode": "query",
                "scope": "XboxLive.signin offline_access",
                "state": "random_state"
            }
            
            auth_url_full = f"{auth_url}?{urllib.parse.urlencode(params)}"
            webbrowser.open(auth_url_full)
            
            # 等待授权码
            import time
            start_time = time.time()
            timeout = 300  # 5分钟超时
            
            while g_auth_code is None and g_auth_error is None:
                if time.time() - start_time > timeout:
                    raise Exception("认证超时，请重新尝试")
                time.sleep(1)
            
            # 停止服务器
            httpd.shutdown()
            
            if g_auth_error:
                raise Exception(f"认证错误: {g_auth_error}")
            
            self.auth_complete.emit(g_auth_code)
        except Exception as e:
            self.auth_error.emit(str(e))

class TokenThread(QThread):
    token_complete = pyqtSignal(dict)
    token_error = pyqtSignal(str)
    
    def __init__(self, client_id, auth_code, redirect_uri):
        super().__init__()
        self.client_id = client_id
        self.auth_code = auth_code
        self.redirect_uri = redirect_uri
    
    def run(self):
        try:
            # 获取访问令牌
            token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
            data = {
                "client_id": self.client_id,
                "code": self.auth_code,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "scope": "XboxLive.signin offline_access"
            }
            
            # 设置正确的Content-Type请求头
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            response = requests.post(token_url, data=data, headers=headers, verify=get_ssl_verify())
            response.raise_for_status()
            tokens = response.json()
            self.token_complete.emit(tokens)
        except Exception as e:
            self.token_error.emit(str(e))

class XboxAuthThread(QThread):
    xbox_complete = pyqtSignal(dict)
    xbox_error = pyqtSignal(str)
    
    def __init__(self, access_token):
        super().__init__()
        self.access_token = access_token
    
    def run(self):
        try:
            # Xbox Live认证
            xbox_auth_url = "https://user.auth.xboxlive.com/user/authenticate"
            
            # 第一次尝试，带d=前缀
            xbox_data = {
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": f"d={self.access_token}"
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT"
            }
            
            # 设置正确的请求头
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            try:
                response = requests.post(xbox_auth_url, json=xbox_data, headers=headers, verify=get_ssl_verify())
                response.raise_for_status()
                xbox_token = response.json()
            except requests.exceptions.HTTPError as e:
                # 如果遇到Bad Request错误，尝试去掉d=前缀
                if e.response.status_code == 400:
                    # 第二次尝试，不带d=前缀
                    xbox_data["Properties"]["RpsTicket"] = self.access_token
                    response = requests.post(xbox_auth_url, json=xbox_data, headers=headers, verify=get_ssl_verify())
                    response.raise_for_status()
                    xbox_token = response.json()
                else:
                    raise
            
            # 获取XSTS令牌
            xsts_url = "https://xsts.auth.xboxlive.com/xsts/authorize"
            xsts_data = {
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [xbox_token["Token"]]
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT"
            }
            
            response = requests.post(xsts_url, json=xsts_data, headers=headers, verify=get_ssl_verify())
            response.raise_for_status()
            xsts_token = response.json()
            
            result = {
                "xbox_token": xbox_token,
                "xsts_token": xsts_token,
                "user_hash": xsts_token["DisplayClaims"]["xui"][0]["uhs"]
            }
            self.xbox_complete.emit(result)
        except Exception as e:
            self.xbox_error.emit(str(e))

class MinecraftAuthThread(QThread):
    minecraft_complete = pyqtSignal(dict)
    minecraft_error = pyqtSignal(str)
    
    def __init__(self, user_hash, xsts_token):
        super().__init__()
        self.user_hash = user_hash
        self.xsts_token = xsts_token
    
    def run(self):
        try:
            # Minecraft认证 - 按照官方规范实现
            minecraft_auth_url = "https://api.minecraftservices.com/authentication/login_with_xbox"
            
            # 构建身份令牌，格式：XBL3.0 x={用户哈希};{XSTS令牌}
            identity_token = f"XBL3.0 x={self.user_hash};{self.xsts_token}"
            
            minecraft_data = {
                "identityToken": identity_token
            }
            
    
            # 添加重试机制
            max_retries = 3
            retry_delay = 2  # 秒
            
            for attempt in range(max_retries):
                try:
                    print("SENTING:",
                        minecraft_auth_url, 
                        minecraft_data,
                    )
                    # 发送认证请求
                    response = requests.post(
                        minecraft_auth_url, 
                        json=minecraft_data,
                        timeout=30  # 添加超时设置
                    )
                    print("SENTBACK", response.status_code, response.json())
                    # 记录响应状态
                    if response.status_code == 429:
                        # 速率限制，需要等待更长时间
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(retry_delay * 3)  # 更长的等待时间
                            retry_delay *= 2
                            continue
                    elif response.status_code == 403:
                        # 403错误，可能是API暂时不可用
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                            continue
                    
                    # 检查响应状态码
                    response.raise_for_status()
                    
                    # 解析响应
                    minecraft_token = response.json()
                    
                    # 验证响应包含必要的字段
                    required_fields = ["access_token", "token_type", "expires_in"]
                    for field in required_fields:
                        if field not in minecraft_token:
                            raise Exception(f"响应缺少必要字段: {field}")
                    
                    # 认证成功
                    self.minecraft_complete.emit(minecraft_token)
                    return
                    
                except requests.exceptions.RequestException as e:
                    # 网络请求错误
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        raise
                except ValueError as e:
                    # JSON解析错误
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        raise
            
        except Exception as e:
            # 详细的错误信息
            error_msg = str(e)
            if "403" in error_msg:
                error_msg += "\n可能的原因：\n1. Mojang API暂时维护\n2. 网络连接问题\n3. IP地址被限制\n4. FastGit加速服务影响\n5. Microsoft账户未拥有Minecraft游戏"
            elif "429" in error_msg:
                error_msg += "\n可能的原因：\n请求过于频繁，请稍后再试"
            elif "timeout" in error_msg:
                error_msg += "\n可能的原因：\n网络连接超时，请检查网络连接"
            elif "400" in error_msg:
                error_msg += "\n可能的原因：\n身份令牌格式错误，请检查XBL令牌和用户哈希"
            self.minecraft_error.emit(error_msg)

from PyQt5.QtWidgets import QProgressDialog

class VersionDownloadThread(QThread):
    download_progress = pyqtSignal(int)
    download_complete = pyqtSignal(str)
    download_error = pyqtSignal(str)

class LibraryCheckThread(QThread):
    progress_updated = pyqtSignal(int, str)
    check_complete = pyqtSignal(str, dict)
    check_error = pyqtSignal(str)
    
    def __init__(self, version_data, game_dir, version_id):
        super().__init__()
        self.version_data = version_data
        self.game_dir = game_dir
        self.version_id = version_id
        self.total_libraries = 0
        self.processed_libraries = 0
    
    def run(self):
        try:
            # 初始化结果
            result = {
                "classpath": [],
                "missing_libraries": []
            }
            
            # 添加客户端jar
            client_jar = os.path.join(self.game_dir, "versions", self.version_id, f"{self.version_id}.jar")
            if not os.path.exists(client_jar):
                error_msg = f"客户端JAR文件不存在: {client_jar}"
                result["missing_libraries"].append(error_msg)
                self.check_error.emit(error_msg)
                return
            result["classpath"].append(client_jar)
            
            # 处理库文件
            if "libraries" in self.version_data:
                libraries = self.version_data["libraries"]
                self.total_libraries = len(libraries)
                
                for library in libraries:
                    try:
                        # 检查是否需要此库
                        if "rules" in library:
                            if not self.should_download_library(library["rules"]):
                                self.processed_libraries += 1
                                progress = int((self.processed_libraries / self.total_libraries) * 100)
                                self.progress_updated.emit(progress, f"跳过不需要的库...")
                                continue
                        
                        # 获取库文件信息
                        artifact = library.get("downloads", {}).get("artifact")
                        if not artifact:
                            self.processed_libraries += 1
                            progress = int((self.processed_libraries / self.total_libraries) * 100)
                            self.progress_updated.emit(progress, f"跳过无artifact的库...")
                            continue
                        
                        library_path = os.path.join(self.game_dir, "libraries", artifact["path"])
                        
                        # 检查文件是否存在
                        if os.path.exists(library_path):
                            # 检查文件大小
                            if os.path.getsize(library_path) == artifact.get("size", 0):
                                result["classpath"].append(library_path)
                                self.processed_libraries += 1
                                progress = int((self.processed_libraries / self.total_libraries) * 100)
                                self.progress_updated.emit(progress, f"验证库文件: {os.path.basename(library_path)}")
                                continue
                        
                        # 创建目录
                        os.makedirs(os.path.dirname(library_path), exist_ok=True)
                        
                        # 下载库文件
                        import time
                        start_time = time.time()
                        url = artifact["url"]
                        accelerated_url = get_download_url(url)
                        
                        # 显示开始下载信息
                        self.progress_updated.emit(
                            int((self.processed_libraries / self.total_libraries) * 100),
                            f"开始下载: {os.path.basename(library_path)} (加速源)"
                        )
                        
                        response = requests.get(accelerated_url, verify=get_ssl_verify(), stream=True)
                        response.raise_for_status()
                        
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded_size = 0
                        last_time = time.time()
                        last_size = 0
                        
                        # 立即显示初始下载状态
                        initial_status = f"下载中: {os.path.basename(library_path)} (0KB/{total_size//1024}KB) (计算中...)"
                        initial_progress = int((self.processed_libraries / self.total_libraries) * 100)
                        self.progress_updated.emit(initial_progress, initial_status)
                        
                        with open(library_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    current_time = time.time()
                                    time_diff = current_time - last_time
                                    
                                    # 每0.3秒更新一次进度和速度，更及时
                                    if time_diff > 0.3:
                                        # 计算速度
                                        size_diff = downloaded_size - last_size
                                        speed = size_diff / time_diff / 1024  # KB/s
                                        
                                        # 计算综合进度
                                        download_progress = int((downloaded_size / total_size) * 30) if total_size > 0 else 0
                                        library_progress = int((self.processed_libraries / self.total_libraries) * 70)
                                        total_progress = library_progress + download_progress
                                        
                                        # 更新状态
                                        status = f"下载中: {os.path.basename(library_path)} "
                                        status += f"({downloaded_size//1024}KB/{total_size//1024}KB) "
                                        status += f"({speed:.1f}KB/s)"
                                        
                                        self.progress_updated.emit(total_progress, status)
                                        last_time = current_time
                                        last_size = downloaded_size
                        
                        # 计算平均速度
                        total_time = time.time() - start_time
                        avg_speed = downloaded_size / total_time / 1024 if total_time > 0 else 0
                        
                        result["classpath"].append(library_path)
                        self.processed_libraries += 1
                        final_progress = int((self.processed_libraries / self.total_libraries) * 100)
                        self.progress_updated.emit(
                            final_progress,
                            f"下载完成: {os.path.basename(library_path)} (平均速度: {avg_speed:.1f}KB/s)"
                        )
                        
                    except Exception as e:
                        self.processed_libraries += 1
                        error_msg = f"处理库文件时出错: {e}"
                        result["missing_libraries"].append(error_msg)
                        progress = int((self.processed_libraries / self.total_libraries) * 100)
                        self.progress_updated.emit(progress, f"错误: {os.path.basename(library_path)}")
                        continue
            
            # 构建类路径字符串
            if os.name == "nt":  # Windows
                classpath_str = ";".join(result["classpath"])
            else:  # Linux/macOS
                classpath_str = ":".join(result["classpath"])
            
            result["classpath_str"] = classpath_str
            self.check_complete.emit("库文件检查完成", result)
            
        except Exception as e:
            self.check_error.emit(str(e))
    
    def should_download_library(self, rules):
        """检查是否应该下载库文件"""
        for rule in rules:
            action = rule.get("action")
            if "os" in rule:
                os_rule = rule["os"]
                if "name" in os_rule:
                    os_name = os_rule["name"]
                    # 简单实现：只检查当前操作系统是否匹配
                    if os_name == "windows" and os.name != "nt":
                        return action == "disallow"
                    elif os_name == "linux" and os.name != "posix":
                        return action == "disallow"
                    elif os_name == "osx" and not sys.platform == "darwin":
                        return action == "disallow"
        return True

class VersionDownloadThread(QThread):
    download_progress = pyqtSignal(int)
    download_complete = pyqtSignal(str)
    download_error = pyqtSignal(str)
    
    def __init__(self, version_id, download_dir):
        super().__init__()
        self.version_id = version_id
        self.download_dir = download_dir
        self.total_files = 0
        self.downloaded_files = 0
        self.download_dir = download_dir
        self.total_files = 0
        self.downloaded_files = 0
    
    def run(self):
        try:
            # 创建版本目录
            version_dir = os.path.join(self.download_dir, "versions", self.version_id)
            os.makedirs(version_dir, exist_ok=True)
            
            # 获取版本信息
            # 尝试从缓存加载版本清单
            version_manifest = load_from_cache("version_manifest")
            
            # 如果缓存不存在或已过期，重新下载
            if not version_manifest:
                version_manifest_url = f"https://launchermeta.mojang.com/mc/game/version_manifest.json"
                accelerated_url = get_download_url(version_manifest_url)
                response = requests.get(accelerated_url, verify=get_ssl_verify())
                response.raise_for_status()
                version_manifest = response.json()
                
                # 保存到缓存
                save_to_cache("version_manifest", version_manifest)
            
            version_info = None
            for version in version_manifest["versions"]:
                if version["id"] == self.version_id:
                    version_info = version
                    break
            
            if not version_info:
                self.download_error.emit(f"版本 {self.version_id} 不存在")
                return
            
            # 下载版本json
            version_json_path = os.path.join(version_dir, f"{self.version_id}.json")
            
            # 检查是否需要下载版本json
            if not os.path.exists(version_json_path):
                version_json_url = version_info["url"]
                accelerated_url = get_download_url(version_json_url)
                response = requests.get(accelerated_url, verify=get_ssl_verify(), stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(version_json_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            if total_size > 0:
                                progress = int((downloaded_size / total_size) * 100)
                                self.download_progress.emit(progress)
            
            # 读取版本json获取客户端jar下载链接
            with open(version_json_path, 'r', encoding='utf-8') as f:
                version_data = json.load(f)
            
            # 下载客户端jar
            client_data = version_data["downloads"]["client"]
            client_jar_url = client_data["url"]
            expected_size = client_data.get("size", 0)
            accelerated_url = get_download_url(client_jar_url)
            # 移除log方法调用
            client_jar_path = os.path.join(version_dir, f"{self.version_id}.jar")
            
            # 下载客户端jar
            response = requests.get(accelerated_url, verify=get_ssl_verify(), stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            import time
            start_time = time.time()
            last_time = start_time
            last_size = 0
            
            with open(client_jar_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        current_time = time.time()
                        time_diff = current_time - last_time
                        
                        # 每0.5秒更新一次进度和速度
                        if time_diff > 0.5:
                            if total_size > 0:
                                progress = int((downloaded_size / total_size) * 100)
                                self.download_progress.emit(progress)
                            
                            # 计算速度
                            size_diff = downloaded_size - last_size
                            speed = size_diff / time_diff / 1024  # KB/s
                            print(f"下载速度: {speed:.1f}KB/s, 已下载: {downloaded_size//1024}KB/{total_size//1024}KB")
                            
                            last_time = current_time
                            last_size = downloaded_size
            
            # 计算平均速度
            total_time = time.time() - start_time
            avg_speed = downloaded_size / total_time / 1024 if total_time > 0 else 0
            print(f"客户端JAR下载完成，平均速度: {avg_speed:.1f}KB/s")
            
            # 验证文件大小
            if expected_size > 0:
                actual_size = os.path.getsize(client_jar_path)
                if actual_size != expected_size:
                    raise Exception(f"客户端JAR文件大小不匹配，预期: {expected_size} 字节，实际: {actual_size} 字节")
                else:
                    print(f"客户端JAR文件大小验证成功: {actual_size} 字节")
            
            # 下载libraries
            self.download_progress.emit(50)  # 进度标记
            self.download_libraries(version_data, self.download_dir)
            
            # 提取natives
            self.download_progress.emit(65)  # 进度标记
            self.extract_natives(version_data, self.download_dir, self.version_id)
            
            # 下载assets
            self.download_progress.emit(75)  # 进度标记
            self.download_assets(version_data, self.download_dir)
            
            self.download_complete.emit(f"版本 {self.version_id} 下载完成")
        except Exception as e:
            self.download_error.emit(str(e))
    
    def download_libraries(self, version_data, game_dir):
        """下载库文件"""
        if "libraries" not in version_data:
            return
        
        libraries = version_data["libraries"]
        valid_libraries = []
        
        # 先筛选出需要下载的库文件
        for library in libraries:
            try:
                # 检查是否需要下载此库
                if "rules" in library:
                    if not self.should_download_library(library["rules"]):
                        continue
                
                # 获取库下载信息
                artifact = library.get("downloads", {}).get("artifact")
                if not artifact:
                    continue
                
                url = artifact["url"]
                path = artifact["path"]
                library_path = os.path.join(game_dir, "libraries", path)
                
                # 检查文件是否已存在
                if os.path.exists(library_path):
                    # 检查文件大小是否正确
                    if os.path.getsize(library_path) == artifact.get("size", 0):
                        continue
                
                valid_libraries.append((url, path, library_path, artifact.get("size", 0)))
            except Exception as e:
                print(f"处理库文件时出错: {e}")
                continue
        
        self.total_files = len(valid_libraries)
        self.downloaded_files = 0
        
        # 使用线程池并行下载
        max_workers = min(8, os.cpu_count() * 2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有下载任务
            future_to_library = {
                executor.submit(self.download_single_file, url, path, library_path, size): library_path
                for url, path, library_path, size in valid_libraries
            }
            
            # 处理下载结果
            for future in concurrent.futures.as_completed(future_to_library):
                try:
                    future.result()
                    self.downloaded_files += 1
                    
                    # 更新进度
                    if self.total_files > 0:
                        progress = 50 + int((self.downloaded_files / self.total_files) * 25)
                        self.download_progress.emit(progress)
                except Exception as e:
                    print(f"下载库文件失败: {e}")
                    continue
    
    def download_single_file(self, url, path, file_path, expected_size):
        """下载单个文件"""
        # 创建目录
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 下载文件
        accelerated_url = get_download_url(url)
        response = requests.get(accelerated_url, verify=get_ssl_verify(), stream=True)
        response.raise_for_status()
        
        downloaded_size = 0
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
        
        # 验证文件大小
        if expected_size > 0 and os.path.getsize(file_path) != expected_size:
            os.remove(file_path)
            raise Exception(f"文件大小不匹配，预期: {expected_size}, 实际: {os.path.getsize(file_path)}")
    
    def download_assets(self, version_data, game_dir):
        """下载资源文件"""
        if "assetIndex" not in version_data:
            return
        
        asset_index = version_data["assetIndex"]
        asset_index_url = asset_index["url"]
        asset_index_path = os.path.join(game_dir, "assets", "indexes", f"{asset_index['id']}.json")
        
        # 创建目录
        os.makedirs(os.path.dirname(asset_index_path), exist_ok=True)
        
        # 下载资源索引文件
        accelerated_url = get_download_url(asset_index_url)
        response = requests.get(accelerated_url, verify=get_ssl_verify(), stream=True)
        response.raise_for_status()
        
        downloaded_size = 0
        with open(asset_index_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
        
        # 读取资源索引并下载资源文件
        with open(asset_index_path, 'r', encoding='utf-8') as f:
            assets_data = json.load(f)
        
        objects = assets_data.get("objects", {})
        valid_assets = []
        
        # 先筛选出需要下载的资源文件
        for hash_key, asset_info in objects.items():
            try:
                hash_value = asset_info["hash"]
                size = asset_info["size"]
                
                # 构建资源文件路径
                asset_path = os.path.join(game_dir, "assets", "objects", hash_value[:2], hash_value)
                
                # 检查文件是否已存在
                if os.path.exists(asset_path):
                    if os.path.getsize(asset_path) == size:
                        continue
                
                asset_url = f"https://resources.download.minecraft.net/{hash_value[:2]}/{hash_value}"
                valid_assets.append((asset_url, asset_path, size))
            except Exception as e:
                print(f"处理资源文件时出错: {e}")
                continue
        
        self.total_files = len(valid_assets)
        self.downloaded_files = 0
        
        # 使用线程池并行下载
        max_workers = min(16, os.cpu_count() * 4)  # 资源文件更小，可以使用更多线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有下载任务
            future_to_asset = {
                executor.submit(self.download_single_file, url, "", path, size): path
                for url, path, size in valid_assets
            }
            
            # 处理下载结果
            for future in concurrent.futures.as_completed(future_to_asset):
                try:
                    future.result()
                    self.downloaded_files += 1
                    
                    # 更新进度
                    if self.total_files > 0:
                        progress = 75 + int((self.downloaded_files / self.total_files) * 25)
                        self.download_progress.emit(progress)
                except Exception as e:
                    print(f"下载资源文件失败: {e}")
                    continue
    
    def should_download_library(self, rules):
        """检查是否应该下载库文件"""
        for rule in rules:
            action = rule.get("action")
            if "os" in rule:
                os_rule = rule["os"]
                if "name" in os_rule:
                    os_name = os_rule["name"]
                    # 简单实现：只检查当前操作系统是否匹配
                    if os_name == "windows" and os.name != "nt":
                        return action == "disallow"
                    elif os_name == "linux" and os.name != "posix":
                        return action == "disallow"
                    elif os_name == "osx" and not sys.platform == "darwin":
                        return action == "disallow"
        return True
    
    def extract_natives(self, version_data, game_dir, version_id):
        """提取原生库文件"""
        # 创建natives目录
        natives_dir = os.path.join(game_dir, "natives")
        os.makedirs(natives_dir, exist_ok=True)
        
        if "libraries" not in version_data:
            return
        
        libraries = version_data["libraries"]
        
        for library in libraries:
            try:
                # 检查是否需要此库
                if "rules" in library:
                    if not self.should_download_library(library["rules"]):
                        continue
                
                # 检查是否有natives
                downloads = library.get("downloads", {})
                classifiers = downloads.get("classifiers", {})
                
                # 根据操作系统选择natives
                native_key = None
                if os.name == "nt":  # Windows
                    native_key = "natives-windows"
                elif sys.platform == "darwin":  # macOS
                    native_key = "natives-osx"
                else:  # Linux
                    native_key = "natives-linux"
                
                if native_key in classifiers:
                    native_info = classifiers[native_key]
                    native_url = native_info["url"]
                    native_path = os.path.join(game_dir, "libraries", native_info["path"])
                    
                    # 创建目录
                    os.makedirs(os.path.dirname(native_path), exist_ok=True)
                    
                    # 检查文件是否已存在
                    if not os.path.exists(native_path):
                        # 下载natives文件
                        response = requests.get(native_url, verify=get_ssl_verify(), stream=True)
                        response.raise_for_status()
                        
                        with open(native_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                    
                    # 提取natives文件
                    import zipfile
                    with zipfile.ZipFile(native_path, 'r') as zip_ref:
                        zip_ref.extractall(natives_dir)
                        
            except Exception as e:
                # 提取失败，记录错误但继续
                print(f"提取natives失败: {e}")
                continue

class Launcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Float Minecraft Launcher")
        self.setGeometry(100, 100, 800, 600)
        
        # 应用配置
        self.client_id = "36220c59-28ce-45bb-b27d-2bef78c2d425"
        self.redirect_uri = "http://localhost:5000"
        self.config_file = "config.json"
        
        # 初始化配置
        self.config = self.load_config()
        
        # 创建主窗口
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 创建布局
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # 创建登录标签页
        self.login_tab = QWidget()
        self.tab_widget.addTab(self.login_tab, "登录")
        self.setup_login_tab()
        
        # 创建版本管理标签页
        self.version_tab = QWidget()
        self.tab_widget.addTab(self.version_tab, "版本管理")
        self.setup_version_tab()
        
        # 创建设置标签页
        self.settings_tab = QWidget()
        self.tab_widget.addTab(self.settings_tab, "设置")
        self.setup_settings_tab()
        
        # 创建控制台
        self.console_group = QGroupBox("控制台")
        self.main_layout.addWidget(self.console_group)
        
        self.console_layout = QVBoxLayout(self.console_group)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console_layout.addWidget(self.console)
        
        # 初始化版本列表
        self.load_versions()
    
    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.console.append(f"[{timestamp}] {message}")
        self.console.ensureCursorVisible()
    
    def load_config(self):
        default_config = {
            "java_path": "",
            "game_dir": os.path.join(os.path.expanduser("~"), "AppData", "Roaming", ".minecraft"),
            "auth_token": "",
            "refresh_token": "",
            "user_info": {}
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default_config
        else:
            return default_config
    
    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def setup_login_tab(self):
        layout = QVBoxLayout(self.login_tab)
        
        # 登录方式选择
        login_method_group = QGroupBox("登录方式")
        layout.addWidget(login_method_group)
        
        login_method_layout = QVBoxLayout(login_method_group)
        
        # Microsoft登录
        self.microsoft_login_button = QPushButton("Microsoft 登录 (正版)")
        self.microsoft_login_button.clicked.connect(self.start_auth)
        login_method_layout.addWidget(self.microsoft_login_button)
        
        # 离线登录表单
        offline_group = QGroupBox("离线登录")
        login_method_layout.addWidget(offline_group)
        
        offline_layout = QGridLayout(offline_group)
        
        offline_layout.addWidget(QLabel("用户名:"), 0, 0)
        self.offline_username = QLineEdit()
        self.offline_username.setPlaceholderText("输入离线模式用户名")
        offline_layout.addWidget(self.offline_username, 0, 1)
        
        self.offline_login_button = QPushButton("登录")
        self.offline_login_button.clicked.connect(self.offline_login)
        offline_layout.addWidget(self.offline_login_button, 1, 0, 1, 2)
        
        # 提示信息
        offline_note = QLabel("注意：离线登录无需网络连接，仅用于正版登录失败时的备用方案")
        offline_note.setWordWrap(True)
        offline_note.setStyleSheet("color: #666; font-size: 10px;")
        login_method_layout.addWidget(offline_note)
        
        # 用户信息显示
        self.user_info_group = QGroupBox("用户信息")
        layout.addWidget(self.user_info_group)
        
        self.user_info_layout = QGridLayout(self.user_info_group)
        
        self.username_label = QLabel("用户名: 未登录")
        self.user_info_layout.addWidget(self.username_label, 0, 0, 1, 2)
        
        self.account_type_label = QLabel("账户类型: 未登录")
        self.user_info_layout.addWidget(self.account_type_label, 1, 0, 1, 2)
        
        self.minecraft_owned_label = QLabel("Minecraft: 未验证")
        self.user_info_layout.addWidget(self.minecraft_owned_label, 2, 0, 1, 2)
        
        self.logout_button = QPushButton("登出")
        self.logout_button.clicked.connect(self.logout)
        self.logout_button.setEnabled(False)
        self.user_info_layout.addWidget(self.logout_button, 3, 0)
        
        # 启动按钮
        self.launch_button = QPushButton("启动游戏")
        self.launch_button.clicked.connect(self.launch_game)
        self.launch_button.setEnabled(False)
        self.user_info_layout.addWidget(self.launch_button, 3, 1)
    
    def setup_version_tab(self):
        layout = QVBoxLayout(self.version_tab)
        
        # 版本选择
        version_group = QGroupBox("版本选择")
        layout.addWidget(version_group)
        
        version_layout = QHBoxLayout(version_group)
        
        self.version_combo = QComboBox()
        version_layout.addWidget(QLabel("选择版本:"))
        version_layout.addWidget(self.version_combo, 1)
        
        # 下载版本
        download_group = QGroupBox("下载版本")
        layout.addWidget(download_group)
        
        download_layout = QHBoxLayout(download_group)
        
        self.version_input = QLineEdit()
        self.version_input.setPlaceholderText("输入版本号，例如: 1.19.4")
        download_layout.addWidget(QLabel("版本号:"))
        download_layout.addWidget(self.version_input, 1)
        
        self.download_button = QPushButton("下载")
        self.download_button.clicked.connect(self.download_version)
        download_layout.addWidget(self.download_button)
        
        # 下载进度
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
    
    def setup_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        
        # Java路径设置
        java_group = QGroupBox("Java 设置")
        layout.addWidget(java_group)
        
        java_layout = QHBoxLayout(java_group)
        
        self.java_path_edit = QLineEdit(self.config.get("java_path", ""))
        java_layout.addWidget(QLabel("Java 路径:"))
        java_layout.addWidget(self.java_path_edit, 1)
        
        self.java_browse_button = QPushButton("浏览")
        self.java_browse_button.clicked.connect(self.browse_java)
        java_layout.addWidget(self.java_browse_button)
        
        # 游戏目录设置
        game_dir_group = QGroupBox("游戏目录设置")
        layout.addWidget(game_dir_group)
        
        game_dir_layout = QHBoxLayout(game_dir_group)
        
        self.game_dir_edit = QLineEdit(self.config.get("game_dir", ""))
        game_dir_layout.addWidget(QLabel("游戏目录:"))
        game_dir_layout.addWidget(self.game_dir_edit, 1)
        
        self.game_dir_browse_button = QPushButton("浏览")
        self.game_dir_browse_button.clicked.connect(self.browse_game_dir)
        game_dir_layout.addWidget(self.game_dir_browse_button)
        
        # 保存设置按钮
        self.save_settings_button = QPushButton("保存设置")
        self.save_settings_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_settings_button)
    
    def browse_java(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Java可执行文件", "", "Java可执行文件 (*.exe);;所有文件 (*)", options=options
        )
        if file_path:
            self.java_path_edit.setText(file_path)
    
    def browse_game_dir(self):
        options = QFileDialog.Options()
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择游戏目录", "", options=options
        )
        if dir_path:
            self.game_dir_edit.setText(dir_path)
    
    def save_settings(self):
        self.config["java_path"] = self.java_path_edit.text()
        self.config["game_dir"] = self.game_dir_edit.text()
        self.save_config()
        self.log("设置已保存")
    
    def start_auth(self):
        self.log("正在启动Microsoft登录...")
        
        # 启动认证线程
        self.auth_thread = AuthThread(self.client_id, self.redirect_uri)
        self.auth_thread.auth_complete.connect(self.on_auth_complete)
        self.auth_thread.auth_error.connect(self.on_auth_error)
        self.auth_thread.start()
    
    def on_auth_complete(self, auth_code):
        self.log("授权码获取成功，正在获取令牌...")
        
        # 获取访问令牌
        self.token_thread = TokenThread(self.client_id, auth_code, self.redirect_uri)
        self.token_thread.token_complete.connect(self.on_token_complete)
        self.token_thread.token_error.connect(self.on_token_error)
        self.token_thread.start()
    
    def on_auth_error(self, error):
        self.log(f"认证错误: {error}")
        QMessageBox.critical(self, "错误", f"认证失败: {error}")
    
    def on_token_complete(self, tokens):
        self.log("令牌获取成功，正在进行Xbox Live认证...")
        
        # 保存令牌
        self.config["auth_token"] = tokens["access_token"]
        self.config["refresh_token"] = tokens["refresh_token"]
        
        # Xbox Live认证
        self.xbox_thread = XboxAuthThread(tokens["access_token"])
        self.xbox_thread.xbox_complete.connect(self.on_xbox_complete)
        self.xbox_thread.xbox_error.connect(self.on_xbox_error)
        self.xbox_thread.start()
    
    def on_token_error(self, error):
        self.log(f"令牌获取错误: {error}")
        QMessageBox.critical(self, "错误", f"令牌获取失败: {error}")
    
    def on_xbox_complete(self, xbox_data):
        self.log("Xbox Live认证成功，正在进行Minecraft认证...")
        
        # Minecraft认证
        self.minecraft_thread = MinecraftAuthThread(
            xbox_data["user_hash"],
            xbox_data["xsts_token"]["Token"]
        )
        self.minecraft_thread.minecraft_complete.connect(self.on_minecraft_complete)
        self.minecraft_thread.minecraft_error.connect(self.on_minecraft_error)
        self.minecraft_thread.start()
    
    def on_xbox_error(self, error):
        self.log(f"Xbox Live认证错误: {error}")
        QMessageBox.critical(self, "错误", f"Xbox Live认证失败: {error}")
    
    def on_minecraft_complete(self, minecraft_data):
        self.log("Minecraft认证成功！")
        
        # 获取用户信息
        user_info_url = "https://api.minecraftservices.com/minecraft/profile"
        headers = {
            "Authorization": f"Bearer {minecraft_data['access_token']}"
        }
        
        try:
            response = requests.get(user_info_url, headers=headers, verify=get_ssl_verify())
            response.raise_for_status()
            user_info = response.json()
            
            # 保存认证信息
            self.config["auth_token"] = minecraft_data["access_token"]
            self.config["user_info"] = {
                "name": user_info.get('name', 'Unknown'),
                "id": user_info.get('id', ''),
                "account_type": "microsoft"
            }
            
            # 验证游戏所有权
            self.verify_minecraft_ownership(minecraft_data["access_token"])
            
            self.save_config()
            
            # 更新UI
            self.username_label.setText(f"用户名: {user_info.get('name', 'Unknown')}")
            self.account_type_label.setText("账户类型: Microsoft")
            self.logout_button.setEnabled(True)
            self.launch_button.setEnabled(True)
            
            self.log(f"登录成功: {user_info.get('name', 'Unknown')}")
        except Exception as e:
            self.log(f"获取用户信息失败: {e}")
    
    def on_minecraft_error(self, error):
        self.log(f"Minecraft认证错误: {error}")
        QMessageBox.critical(self, "错误", f"Minecraft认证失败: {error}")
    
    def offline_login(self):
        """离线登录"""
        username = self.offline_username.text().strip()
        
        if not username:
            QMessageBox.warning(self, "警告", "请输入用户名")
            return
        
        self.log(f"正在进行离线登录: {username}")
        
        try:
            # 生成随机的UUID作为离线账户ID
            import uuid
            offline_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, username))
            
            # 保存离线登录信息
            self.config["auth_token"] = f"offline_{offline_uuid}"
            self.config["user_info"] = {
                "name": username,
                "id": offline_uuid,
                "account_type": "offline"
            }
            self.config["has_minecraft"] = True  # 离线模式默认拥有游戏
            
            self.save_config()
            
            # 更新UI
            self.username_label.setText(f"用户名: {username}")
            self.account_type_label.setText("账户类型: 离线模式")
            self.minecraft_owned_label.setText("Minecraft: 离线模式")
            self.logout_button.setEnabled(True)
            self.launch_button.setEnabled(True)
            
            self.log(f"离线登录成功: {username}")
            
        except Exception as e:
            error_msg = str(e)
            self.log(f"离线登录错误: {error_msg}")
            QMessageBox.critical(self, "错误", f"登录失败: {error_msg}")
    
    def verify_minecraft_ownership(self, access_token):
        """验证账户是否拥有Minecraft"""
        try:
            self.log("正在验证Minecraft游戏所有权...")
            
            # 发送验证请求
            response = requests.get(
                "https://api.minecraftservices.com/entitlements/mcstore",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                },
                verify=get_ssl_verify()
            )
            
            response.raise_for_status()
            entitlements = response.json()
            
            # 检查是否拥有Minecraft
            has_minecraft = False
            if "items" in entitlements:
                for item in entitlements["items"]:
                    if item.get("name") in ["product_minecraft", "game_minecraft"]:
                        has_minecraft = True
                        break
            
            if has_minecraft:
                self.minecraft_owned_label.setText("Minecraft: 已拥有")
                self.config["has_minecraft"] = True
                self.log("验证成功: 账户拥有Minecraft")
            else:
                self.minecraft_owned_label.setText("Minecraft: 未拥有")
                self.config["has_minecraft"] = False
                self.log("验证失败: 账户未拥有Minecraft")
                QMessageBox.warning(self, "警告", "您的账户未拥有Minecraft游戏")
            
            self.save_config()
            
        except Exception as e:
            self.log(f"验证游戏所有权失败: {e}")
            self.minecraft_owned_label.setText("Minecraft: 验证失败")
            self.config["has_minecraft"] = False
            self.save_config()
    
    def logout(self):
        self.config["auth_token"] = ""
        self.config["refresh_token"] = ""
        self.config["user_info"] = {}
        self.config["has_minecraft"] = False
        self.save_config()
        
        self.username_label.setText("用户名: 未登录")
        self.account_type_label.setText("账户类型: 未登录")
        self.minecraft_owned_label.setText("Minecraft: 未验证")
        self.logout_button.setEnabled(False)
        self.launch_button.setEnabled(False)
        
        self.log("已登出")
    
    def load_versions(self):
        try:
            # 尝试从缓存加载版本清单
            version_manifest = load_from_cache("version_manifest")
            
            # 如果缓存不存在或已过期，重新下载
            if not version_manifest:
                self.log("从服务器获取版本清单...")
                version_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
                response = requests.get(version_manifest_url, verify=get_ssl_verify())
                response.raise_for_status()
                version_manifest = response.json()
                
                # 保存到缓存
                save_to_cache("version_manifest", version_manifest)
                self.log("版本清单已缓存")
            else:
                self.log("从缓存加载版本清单")
            
            # 清空现有选项
            self.version_combo.clear()
            
            # 添加版本到下拉框
            for version in version_manifest["versions"]:
                self.version_combo.addItem(f"{version['id']} ({version['type']})")
            
            self.log(f"成功加载 {len(version_manifest['versions'])} 个版本")
        except Exception as e:
            self.log(f"加载版本列表失败: {e}")
    
    def download_version(self):
        version_id = self.version_input.text().strip()
        if not version_id:
            QMessageBox.warning(self, "警告", "请输入版本号")
            return
        
        game_dir = self.config.get("game_dir", os.path.join(os.path.expanduser("~"), "AppData", "Roaming", ".minecraft"))
        
        self.log(f"开始下载版本: {version_id}")
        
        # 启动下载线程
        self.download_thread = VersionDownloadThread(version_id, game_dir)
        self.download_thread.download_progress.connect(self.update_progress)
        self.download_thread.download_complete.connect(self.on_download_complete)
        self.download_thread.download_error.connect(self.on_download_error)
        self.download_thread.start()
    
    def update_progress(self, progress):
        self.progress_bar.setValue(progress)
    
    def on_download_complete(self, message):
        self.log(message)
        self.progress_bar.setValue(0)
        QMessageBox.information(self, "成功", message)
        # 重新加载版本列表
        self.load_versions()
    
    def on_download_error(self, error):
        self.log(f"下载错误: {error}")
        self.progress_bar.setValue(0)
        QMessageBox.critical(self, "错误", f"下载失败: {error}")
    
    def launch_game(self):
        selected_version = self.version_combo.currentText()
        version_id = selected_version.split(" ")[0]
        
        java_path = self.config.get("java_path", "")
        game_dir = self.config.get("game_dir", os.path.join(os.path.expanduser("~"), "AppData", "Roaming", ".minecraft"))
        
        # 快速检查Java路径
        if not java_path:
            QMessageBox.warning(self, "警告", "Java路径未设置")
            return
        
        if not os.path.exists(java_path):
            QMessageBox.warning(self, "警告", "Java路径不存在")
            return
        
        # 快速检查版本是否存在
        version_dir = os.path.join(game_dir, "versions", version_id)
        version_json_path = os.path.join(version_dir, f"{version_id}.json")
        
        if not os.path.exists(version_dir) or not os.path.exists(version_json_path):
            # 自动下载，不询问用户
            self.log(f"版本 {version_id} 未下载，开始自动下载...")
            
            # 启动下载线程
            self.download_version_thread = VersionDownloadThread(version_id, game_dir)
            self.download_version_thread.download_progress.connect(self.update_download_progress)
            self.download_version_thread.download_complete.connect(lambda msg: self.on_version_download_complete(msg, java_path, game_dir, version_id))
            self.download_version_thread.download_error.connect(self.on_version_download_error)
            
            # 创建下载进度条
            self.download_progress_dialog = QProgressDialog(f"正在下载版本 {version_id}...", "取消", 0, 100, self)
            self.download_progress_dialog.setWindowTitle("版本下载")
            self.download_progress_dialog.setMinimumDuration(0)
            self.download_progress_dialog.setValue(0)
            self.download_progress_dialog.show()
            
            # 开始下载
            self.download_version_thread.start()
            return
        
        # 版本存在，继续启动流程
        self.continue_launch(game_dir, version_id, java_path)
    
    def continue_launch(self, game_dir, version_id, java_path):
        """继续启动流程"""
        version_json_path = os.path.join(game_dir, "versions", version_id, f"{version_id}.json")
        
        # 快速检查登录状态
        if "user_info" not in self.config or not self.config["user_info"]:
            QMessageBox.warning(self, "警告", "请先登录")
            return
        
        # 快速检查游戏所有权（仅对非离线模式）
        account_type = self.config["user_info"].get("account_type")
        if account_type != "offline":
            if not self.config.get("has_minecraft", False):
                QMessageBox.warning(self, "警告", "您的账户未拥有Minecraft游戏")
                return
        
        self.log(f"正在启动Minecraft {version_id}...")
        
        try:
            # 快速读取版本配置
            with open(version_json_path, 'r', encoding='utf-8') as f:
                version_data = json.load(f)
            
            # 获取主类
            main_class = version_data.get("mainClass", "net.minecraft.client.main.Main")
            self.log(f"使用主类: {main_class}")
            
            # 创建库文件检查线程
            self.library_thread = LibraryCheckThread(version_data, game_dir, version_id)
            self.library_thread.progress_updated.connect(self.update_library_progress)
            self.library_thread.check_complete.connect(lambda msg, result: self.on_library_check_complete(msg, result, java_path, game_dir, version_id, main_class, account_type))
            self.library_thread.check_error.connect(self.on_library_check_error)
            
            # 创建并显示进度条窗口
            self.progress_dialog = QProgressDialog("正在检查库文件...", "取消", 0, 100, self)
            self.progress_dialog.setWindowTitle("库文件检查")
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.setValue(0)
            self.progress_dialog.show()
            
            # 立即启动库文件检查线程
            self.library_thread.start()
            
        except Exception as e:
            self.log(f"启动失败: {e}")
            QMessageBox.critical(self, "错误", f"启动失败: {e}")
    
    def update_download_progress(self, progress):
        """更新下载进度"""
        if hasattr(self, 'download_progress_dialog') and self.download_progress_dialog.isVisible():
            self.download_progress_dialog.setValue(progress)
            QApplication.processEvents()
    
    def on_version_download_complete(self, message, java_path, game_dir, version_id):
        """版本下载完成后的处理"""
        # 关闭下载进度条
        if hasattr(self, 'download_progress_dialog'):
            self.download_progress_dialog.close()
        
        self.log(message)
        QMessageBox.information(self, "成功", message)
        
        # 继续启动流程
        self.continue_launch(game_dir, version_id, java_path)
    
    def on_version_download_error(self, error):
        """版本下载错误处理"""
        # 关闭下载进度条
        if hasattr(self, 'download_progress_dialog'):
            self.download_progress_dialog.close()
        
        self.log(f"下载错误: {error}")
        QMessageBox.critical(self, "错误", f"下载失败: {error}")
    
    def update_library_progress(self, progress, status):
        """更新库文件检查进度"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            self.progress_dialog.setValue(progress)
            self.progress_dialog.setLabelText(status)
            QApplication.processEvents()
    
    def on_library_check_complete(self, message, result, java_path, game_dir, version_id, main_class, account_type):
        """库文件检查完成后的处理"""
        # 关闭进度条窗口
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()
        
        self.log(message)
        self.log(f"类路径包含 {len(result['classpath'])} 个文件")
        
        if result['missing_libraries']:
            self.log(f"有 {len(result['missing_libraries'])} 个库文件处理失败")
            for error in result['missing_libraries']:
                self.log(f"错误: {error}")
        
        # 构建启动参数
        username = self.config["user_info"].get("name", "Player")
        uuid = self.config["user_info"].get("id", "")
        access_token = self.config.get("auth_token", "")
        
        # 解决命令行太长的问题，使用类路径文件
        classpath_file = os.path.join(game_dir, "classpath.txt")
        
        # 写入类路径到文件
        with open(classpath_file, 'w', encoding='utf-8') as f:
            f.write(result["classpath_str"])
        
        # 构建JVM参数
        jvm_args = [
            f"-Djava.library.path={os.path.join(game_dir, 'natives')}",
            f"-cp", f"@{classpath_file}",  # 使用@符号引用类路径文件
            main_class
        ]
        
        # 构建游戏参数
        game_args = [
            "--gameDir", game_dir,
            "--username", username,
            "--uuid", uuid,
            "--version", version_id
        ]
        
        # 根据账户类型添加不同的参数
        if account_type == "offline":
            game_args.extend(["--offline"])
        # 无论什么账户类型，都添加accessToken参数
        game_args.extend(["--accessToken", access_token])
        
        # 构建完整命令
        cmd_parts = [f'"{java_path}"'] + jvm_args + game_args
        cmd = " ".join(cmd_parts)
        
        # 启动游戏
        try:
            import subprocess
            subprocess.Popen(cmd, shell=True, cwd=game_dir)
            
            self.log(f"游戏启动成功，账户类型: {account_type}")
            self.log(f"启动命令: {cmd}")
        except Exception as e:
            self.log(f"启动失败: {e}")
            QMessageBox.critical(self, "错误", f"启动失败: {e}")
    
    def on_library_check_error(self, error):
        """库文件检查错误处理"""
        # 关闭进度条窗口
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()
        
        self.log(f"库文件检查失败: {error}")
        QMessageBox.critical(self, "错误", f"库文件检查失败: {error}")
    
    def build_classpath(self, version_data, game_dir, version_id):
        """构建类路径"""
        classpath_parts = []
        
        # 添加客户端jar
        client_jar = os.path.join(game_dir, "versions", version_id, f"{version_id}.jar")
        classpath_parts.append(client_jar)
        
        # 添加库文件
        if "libraries" in version_data:
            libraries = version_data["libraries"]
            self.log(f"发现 {len(libraries)} 个库文件")
            
            for library in libraries:
                try:
                    # 检查是否需要此库
                    if "rules" in library:
                        if not self.should_download_library(library["rules"]):
                            continue
                    
                    # 获取库文件路径
                    artifact = library.get("downloads", {}).get("artifact")
                    if artifact:
                        library_path = os.path.join(game_dir, "libraries", artifact["path"])
                        
                        # 检查文件是否存在
                        if os.path.exists(library_path):
                            classpath_parts.append(library_path)
                            # 检查是否是joptsimple库
                            if "joptsimple" in library_path:
                                self.log(f"添加joptsimple库: {library_path}")
                        else:
                            # 尝试下载缺失的库文件
                            self.log(f"库文件缺失，尝试下载: {library_path}")
                            url = artifact["url"]
                            
                            # 创建目录
                            os.makedirs(os.path.dirname(library_path), exist_ok=True)
                            
                            # 下载库文件
                            response = requests.get(url, verify=get_ssl_verify(), stream=True)
                            response.raise_for_status()
                            
                            with open(library_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                            
                            classpath_parts.append(library_path)
                            self.log(f"成功下载库文件: {library_path}")
                except Exception as e:
                    self.log(f"处理库文件时出错: {e}")
                    continue
        
        # 使用系统路径分隔符
        if os.name == "nt":  # Windows
            classpath = ";".join(classpath_parts)
        else:  # Linux/macOS
            classpath = ":".join(classpath_parts)
        
        self.log(f"构建的类路径包含 {len(classpath_parts)} 个文件")
        return classpath
    
    def should_download_library(self, rules):
        """检查是否应该下载库文件"""
        for rule in rules:
            action = rule.get("action")
            if "os" in rule:
                os_rule = rule["os"]
                if "name" in os_rule:
                    os_name = os_rule["name"]
                    # 简单实现：只检查当前操作系统是否匹配
                    if os_name == "windows" and os.name != "nt":
                        return action == "disallow"
                    elif os_name == "linux" and os.name != "posix":
                        return action == "disallow"
                    elif os_name == "osx" and not sys.platform == "darwin":
                        return action == "disallow"
        return True

if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = Launcher()
    launcher.show()
    sys.exit(app.exec_())