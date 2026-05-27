# GitHub Issues下载器

这个模块提供了从GitHub仓库下载所有issues并保存为JSON格式的功能。

## 文件说明

- `github_issues_downloader.py` - 主要的GitHub Issues下载器类
- `test_limited.py` - 限制页数的测试脚本（推荐用于测试）
- `test_downloader.py` - 完整的测试脚本
- `simple_test.py` - 基本功能测试脚本
- `requirements.txt` - Python依赖包列表
- `__init__.py` - Python包初始化文件

## 使用方法

### 1. 基本使用

```python
from github_issues_downloader import GitHubIssuesDownloader

# 创建下载器实例
downloader = GitHubIssuesDownloader(token=None)  # 可选：提供GitHub token

# 获取issues
issues = downloader.get_all_issues("owner", "repository", state="all")

# 保存为JSON
downloader.save_issues_to_json(issues, "output.json")
```

### 2. 运行测试

```bash
# 运行限制页数的测试（推荐）
python test_limited.py

# 运行完整测试
python github_issues_downloader.py
```

### 3. 自定义配置

在脚本中修改以下参数：

```python
OWNER = "your-username"     # 仓库所有者
REPO = "your-repository"    # 仓库名称
TOKEN = "your-token"        # GitHub Personal Access Token（可选）
```

## 功能特点

1. **自动分页处理**：自动处理GitHub API的分页限制
2. **错误处理**：包含完善的错误处理和重试机制
3. **API限制友好**：包含适当的延迟以避免触发GitHub API限制
4. **过滤Pull Requests**：自动过滤掉GitHub API返回的Pull Requests
5. **JSON输出**：以结构化的JSON格式保存所有issues信息

## 输出格式

生成的JSON文件包含每个issue的完整信息：

```json
[
  {
    "number": 1234,
    "title": "Issue标题",
    "state": "open",
    "body": "Issue描述",
    "user": {
      "login": "username"
    },
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "html_url": "https://github.com/owner/repo/issues/1234",
    "labels": [...],
    "assignee": {...}
  }
]
```

## 注意事项

- 没有token的情况下，GitHub API每小时限制60次请求
- 使用token后，每小时可以请求5000次
- 对于大型仓库，建议使用token以获得更好的性能
- 脚本会自动创建输出文件，文件名包含时间戳

## 依赖

- Python 3.6+
- 内置模块：urllib, json, os, time, datetime, typing

无需安装额外的Python包，使用Python标准库即可运行。
