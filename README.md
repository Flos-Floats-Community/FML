# Float Minecraft Launcher

一个功能强大的Minecraft启动器，支持Microsoft账户认证、版本管理、快速下载等功能。

## 功能特点

### 核心功能
- ✅ **GUI界面**：美观易用的PyQt5图形界面
- ✅ **Microsoft账户认证**：支持官方微软账户登录
- ✅ **离线登录**：无需网络即可登录的离线模式
- ✅ **版本管理**：支持多个Minecraft版本的选择和下载
- ✅ **自动下载**：启动游戏时自动下载缺失的版本
- ✅ **下载加速**：集成BMCLAPI加速源，提供更快的下载速度
- ✅ **速度显示**：实时显示下载速度和进度
- ✅ **自定义Java路径**：可选择自定义Java可执行文件路径

### 技术特性
- ✅ **SSL证书绕过**：支持FastGit加速网络
- ✅ **多线程下载**：并行下载库文件和资源文件
- ✅ **命令行长度优化**：使用类路径文件解决命令行过长问题
- ✅ **容错处理**：遇到认证错误时自动重试
- ✅ **详细错误信息**：提供清晰的错误提示和解决方案

## 系统要求

- **操作系统**：Windows 7/8/10/11
- **Python**：3.6或更高版本
- **Java**：Java 8或更高版本（用于运行Minecraft）
- **依赖库**：PyQt5、requests、urllib3

## 本地编译方法

### 1. 克隆或下载项目
```bash
git clone https://github.com/Flos-Floats-Community/FML
cd FML
```

### 2. 安装依赖
```bash
pip install PyQt5 requests pyinstaller
```

### 3.编译
```bash
pyinstaller --onefile --noconsole launcher.py #如果需要调试信息请去掉--noconsole
```

### 登录方式

#### Microsoft账户登录
1. 点击 "Microsoft 登录 (正版)" 按钮
2. 在打开的浏览器中登录您的Microsoft账户
3. 授权应用程序访问Xbox Live
4. 浏览器会自动重定向回启动器，完成登录

#### 离线登录
1. 在离线登录表单中输入用户名
2. 点击 "登录" 按钮
3. 直接进入游戏启动界面

### 启动游戏
1. 选择您想要启动的Minecraft版本
2. 确保已登录（Microsoft或离线模式）
3. 点击 "启动游戏" 按钮
4. 启动器会自动下载缺失的版本和库文件
5. 游戏启动后，启动器会显示启动命令和状态

## 配置说明

### Java路径配置
1. 点击 "设置" 标签页
2. 在 "Java 设置" 部分点击 "浏览" 按钮
3. 选择您的Java可执行文件（通常位于 `C:\Program Files\Java\jdk1.x.x_xxx\bin\java.exe`）
4. 点击 "保存设置" 按钮

### 游戏目录配置
1. 点击 "设置" 标签页
2. 在 "游戏目录设置" 部分点击 "浏览" 按钮
3. 选择您想要使用的游戏目录
4. 点击 "保存设置" 按钮

## 常见问题与解决方案

### 1. Microsoft认证失败 (403错误)

**可能原因**：
- Mojang API暂时维护
- 网络连接问题
- IP地址被限制
- FastGit加速服务影响
- Microsoft账户未拥有Minecraft游戏
- 官方暂停了我们的AppID服务并且开始审查我们的服务

**解决方案**：
- 等待一段时间后重试
- 暂时禁用FastGit加速
- 检查网络连接和防火墙设置
- 确认Microsoft账户已购买Minecraft

### 2. 找不到或无法加载主类错误

**可能原因**：
- 客户端JAR文件下载不完整
- 库文件缺失
- 类路径配置错误

**解决方案**：
- 删除不完整的客户端JAR文件，重新下载
- 确保所有库文件已正确下载
- 检查Java路径配置

### 3. 命令行太长错误

**解决方案**：
- 已内置解决方案，使用类路径文件解决此问题
- 无需手动操作

### 4. 下载速度慢

**解决方案**：
- 启动器已集成BMCLAPI加速源，自动提供更快的下载速度
- 确保网络连接稳定

## 技术实现

### 认证流程
1. **Microsoft OAuth 2.0认证**：使用本地HTTP服务器接收授权码
2. **Xbox Live认证**：获取XBL令牌和XSTS令牌
3. **Minecraft认证**：使用XSTS令牌获取Minecraft访问令牌
4. **游戏所有权验证**：检查账户是否拥有Minecraft游戏

### 下载系统
1. **版本管理**：从Mojang API获取版本清单
2. **加速下载**：使用BMCLAPI加速源
3. **多线程下载**：并行下载库文件和资源文件
4. **自动验证**：检查文件大小和完整性

### 启动系统
1. **类路径构建**：生成包含所有必要库文件的类路径
2. **命令行优化**：使用类路径文件解决命令行过长问题
3. **参数构建**：根据账户类型和版本生成正确的启动参数

## 开发说明

### 项目结构
- `launcher.py`：主启动器文件，包含所有功能实现
- `config.json`：配置文件，存储Java路径、游戏目录等信息

### 核心类
- `AuthThread`：处理Microsoft账户认证
- `TokenThread`：获取访问令牌
- `XboxAuthThread`：处理Xbox Live认证
- `MinecraftAuthThread`：处理Minecraft认证
- `VersionDownloadThread`：处理版本下载
- `LibraryCheckThread`：检查和下载库文件

### 核心函数
- `get_download_url()`：获取加速下载链接
- `launch_game()`：启动游戏，包含自动下载功能
- `on_library_check_complete()`：使用类路径文件解决命令行长度问题

## 许可证

MIT License

## 致谢

- [Mojang](https://www.mojang.com/) - Minecraft游戏和API
- [BMCLAPI](https://bmclapi2.bangbang93.com/) - 提供Minecraft下载加速服务
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - 提供GUI框架

## 联系方式

如有问题或建议，欢迎联系：
- GitHub Issues：[Submit Issue](https://github.com//Flos-Floats-Community/FML/issues)

---

**注意**：本启动器仅用于个人使用，请勿用于商业目的。使用本启动器即表示您同意遵守Minecraft的最终用户许可协议。
