import urllib.request
import urllib.parse
import urllib.error
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Optional

class GitHubIssuesDownloader:
    def __init__(self, token: Optional[str] = None):
        """
        初始化GitHub Issues下载器
        
        Args:
            token: GitHub Personal Access Token (可选，但推荐使用以获得更高的API限制)
        """
        self.token = token
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Issues-Downloader'
        }
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
    
    def _make_request(self, url: str, params: Dict = None) -> Dict:
        """
        发起HTTP请求
        
        Args:
            url: 请求URL
            params: 查询参数
        
        Returns:
            响应数据
        """
        if params:
            url += '?' + urllib.parse.urlencode(params)
        
        req = urllib.request.Request(url)
        
        # 添加请求头
        for key, value in self.headers.items():
            req.add_header(key, value)
        print(req)
        with urllib.request.urlopen(req) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    
    def get_all_issues(self, owner: str, repo: str, state: str = 'all') -> List[Dict]:
        """
        获取指定仓库的所有issues
        
        Args:
            owner: 仓库所有者用户名
            repo: 仓库名称
            state: issues状态 ('open', 'closed', 'all')
        
        Returns:
            包含所有issues的列表
        """
        issues = []
        page = 1
        per_page = 100  # GitHub API允许的最大值
        
        print(f"开始获取仓库 {owner}/{repo} 的 {state} issues...")
        
        while True:
            url = f"https://api.github.com/repos/{owner}/{repo}/issues"
            params = {
                'state': state,
                'page': page,
                'per_page': per_page
            }
            
            page_issues = self._make_request(url, params)
            
            if not page_issues:
                break
            
            # 过滤掉pull requests (GitHub API返回的issues包含PRs)
            actual_issues = [issue for issue in page_issues if 'pull_request' not in issue]
            issues.extend(actual_issues)
            
            print(f"已获取第 {page} 页，共 {len(actual_issues)} 个issues")
            
            # 检查是否还有更多页面
            if len(page_issues) < per_page:
                break
            
            page += 1
            
            # 避免触发API限制
            time.sleep(0.5)
        
        print(f"总共获取到 {len(issues)} 个issues")
        return issues
    
    def save_issues_to_json(self, issues: List[Dict], output_file: str):
        """
        将issues保存为JSON文件
        
        Args:
            issues: issues列表
            output_file: 输出文件路径
        """
        # 确保输出目录存在（如果output_file包含目录路径）
        dir_path = os.path.dirname(output_file)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(issues, f, ensure_ascii=False, indent=2)
        
        print(f"Issues已保存到: {output_file}")


def main():
    """
    主函数 - 使用示例
    """
    # 配置参数
    OWNER = "78"  # 示例：microsoft仓库
    REPO = "xiaozhi-esp32"      # 示例：vscode仓库
    TOKEN = None  # 可选：你的GitHub Personal Access Token
    
    # 创建下载器实例
    downloader = GitHubIssuesDownloader(token=TOKEN)
    
    # 获取所有issues
    issues = downloader.get_all_issues(OWNER, REPO, state='all')
    
    if not issues:
        print("没有找到任何issues")
        return
    
    # 创建输出文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"issues_{OWNER}_{REPO}_{timestamp}.json"
    
    # 保存为JSON格式
    downloader.save_issues_to_json(issues, output_file)
    
    # 打印统计信息
    open_issues = len([i for i in issues if i['state'] == 'open'])
    closed_issues = len([i for i in issues if i['state'] == 'closed'])
    
    print(f"\n=== 统计信息 ===")
    print(f"总issues数: {len(issues)}")
    print(f"开放issues: {open_issues}")
    print(f"已关闭issues: {closed_issues}")
    print(f"输出文件: {output_file}")
        


if __name__ == "__main__":
    main()
