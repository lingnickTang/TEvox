// extension.ts
import * as vscode from 'vscode';
import * as fs from 'fs';
import axios from 'axios';
import { TaskManager } from './taskManager';
import { TaskResponse, TaskMetadata } from './types';

class TaskQuickPickItem implements vscode.QuickPickItem {
    label: string;
    description: string;
    taskId: string;
    buttons: vscode.QuickInputButton[];

    constructor(task: TaskMetadata) {
        this.label = task.description;
        this.description = task.taskId;
        this.taskId = task.taskId;
        this.buttons = [
            {
                iconPath: new vscode.ThemeIcon('trash'),
                tooltip: '删除任务'
            }
        ];
    }
}


export class AgentChatViewProvider implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;
    private readonly _extensionUri: vscode.Uri;
    private taskManager: TaskManager;

    constructor(private context: vscode.ExtensionContext) {
        this._extensionUri = context.extensionUri;
        this.taskManager = new TaskManager(context);
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        token: vscode.CancellationToken
    ): void | Thenable<void> {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlContent(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (message: any) => {
            switch (message.type) {
                case 'createNewTask':
                    await this.taskManager.setCurrentTask(null);
                    break;
                case 'showTaskList':
                    await this.showTaskQuickPick();
                    break;
                case 'newTask':
                    await this.handleNewTask(message.content);
                    break;
                case 'feedback':
                    await this.handleFeedback(message.content);
                    break;
            }
        });

        // 初始化时发送所有任务列表
        this.sendTaskList();
    }

    private async showTaskQuickPick() {
        const tasks = this.taskManager.getTaskMetadataList();
        const quickPick = vscode.window.createQuickPick<TaskQuickPickItem>();
        
        quickPick.items = tasks.map(task => new TaskQuickPickItem(task));
        quickPick.placeholder = '选择一个任务';
        
        quickPick.onDidTriggerItemButton(async ({item, button}) => {
            // 处理删除按钮点击
            if (button === item.buttons[0]) {
                const confirm = await vscode.window.showWarningMessage(
                    `确定要删除任务 "${item.label}" 吗？`,
                    '确定',
                    '取消'
                );
                
                if (confirm === '确定') {
                    await this.taskManager.deleteTask(item.taskId);
                    quickPick.items = quickPick.items.filter(i => i.taskId !== item.taskId);
                    if (quickPick.items.length === 0) {
                        quickPick.dispose();
                    }
                }
            }
        });

        quickPick.onDidAccept(async () => {
            const selectedItem = quickPick.selectedItems[0];
            if (selectedItem) {
                const taskDetail = await this.taskManager.setCurrentTask(selectedItem.taskId);
                if (taskDetail) {
                    this.sendMessageToWebview({
                        type: 'loadTask',
                        task: taskDetail
                    });
                }
            }
            quickPick.dispose();
        });

        quickPick.show();
    }
    private async handleNewTask(description: string): Promise<void> {
        try {
            const task = await this.taskManager.createNewTask(description);
            await this.taskManager.addConversation('user', description);
            
            const response = await axios.post<TaskResponse>('http://localhost:8000/process-task', {
                task_id: task.taskId,
                task_spec: description
            });
    
            await this.taskManager.addConversation('assistant', response.data.result);
            
            this.sendMessageToWebview({
                type: 'result',
                content: response.data.result,
                taskId: task.taskId
            });
    
            this.sendTaskList();
        } catch (error) {
            this.sendMessageToWebview({
                type: 'error',
                content: error instanceof Error ? error.message : 'Unknown error'
            });
        }
    }
    
    private async handleFeedback(feedback: string): Promise<void> {
        try {
            const currentTask = await this.taskManager.getCurrentTask();
            if (!currentTask) {
                throw new Error('No active task');
            }
    
            // 先添加用户的反馈到对话中
            await this.taskManager.addConversation('user', feedback);
    
            // 准备发送给服务器的对话历史
            const conversations = currentTask.conversations.map(conv => ({
                role: conv.type,
                content: conv.content
            }));
    
            // 发送请求到服务器
            const response = await axios.post<TaskResponse>('http://localhost:8000/process-task', {
                task_id: currentTask.taskId,
                task_spec: currentTask.description,
                feedback: feedback,
                conversation_history: conversations // 添加对话历史
            });
    
            // 添加助手的回复到对话中
            await this.taskManager.addConversation('assistant', response.data.result);
    
            // 重新获取更新后的任务详情
            const updatedTask = await this.taskManager.getCurrentTask();
    
            // 发送更新后的结果到 webview
            this.sendMessageToWebview({
                type: 'result',
                content: response.data.result,
                task: updatedTask // 发送完整的更新后的任务信息
            });
    
            // 更新任务列表
            await this.sendTaskList();
        } catch (error) {
            console.error('Feedback handling error:', error);
            this.sendMessageToWebview({
                type: 'error',
                content: error instanceof Error ? error.message : 'Unknown error'
            });
        }
    }
    private async sendTaskList(): Promise<void> {
        const tasks = this.taskManager.getTaskMetadataList();
        this.sendMessageToWebview({
            type: 'taskList',
            tasks: tasks
        });
    }

    private sendMessageToWebview(message: any): void {
        if (this._view) {
            this._view.webview.postMessage(message);
        }
    }

    private _getHtmlContent(webview: vscode.Webview): string {
        try {
            // 获取构建后的文件路径
            const distPath = vscode.Uri.joinPath(this._extensionUri, 'webview-ui', 'dist');
            const indexHtml = vscode.Uri.joinPath(distPath, 'index.html');
            
            // 检查文件是否存在
            if (!fs.existsSync(indexHtml.fsPath)) {
                throw new Error(`找不到文件: ${indexHtml.fsPath}`);
            }
    
            // 读取 index.html 内容
            let htmlContent = fs.readFileSync(indexHtml.fsPath, 'utf8');
            
            // 生成 nonce
            const nonce = this.getNonce();
            
            // 添加 CSP
            const csp = `
                <meta http-equiv="Content-Security-Policy" 
                      content="default-src 'none'; 
                              style-src ${webview.cspSource} 'unsafe-inline';
                              script-src ${webview.cspSource} 'nonce-${nonce}';
                              img-src ${webview.cspSource} https:;">
            `;
            
            // 在 head 标签后插入 CSP
            htmlContent = htmlContent.replace('</head>', `${csp}</head>`);
            
            // 替换资源路径
            const assetsPath = vscode.Uri.joinPath(distPath, 'assets');
            
            // 替换所有 /assets/ 开头的路径
            htmlContent = htmlContent.replace(
                /(href|src)="\/assets\//g,
                (match, p1) => `${p1}="${webview.asWebviewUri(assetsPath)}/`
            );
            
            // 添加 nonce 到脚本标签
            htmlContent = htmlContent.replace(
                /<script/g,
                `<script nonce="${nonce}"`
            );
            
            // 替换其他绝对路径（如果有的话）
            htmlContent = htmlContent.replace(
                /(href|src)="\/(?!http)/g,
                `$1="${webview.asWebviewUri(distPath)}/`
            );
    
            console.log('处理后的 HTML:', htmlContent);
            
            return htmlContent;
        } catch (error) {
            console.error('Error in _getHtmlContent:', error);
            throw error;
        }
    }

    private getNonce(): string {
        let text = '';
        const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }
    
    
}

export function registerAgentChat(context: vscode.ExtensionContext): vscode.Disposable[] {
    const provider = new AgentChatViewProvider(context);
    const disposables: vscode.Disposable[] = [];
    
    // 注册 WebviewViewProvider
    disposables.push(
        vscode.window.registerWebviewViewProvider('agentChat', 
            provider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true,
                },
            })
    );

    // 注册显示命令
    disposables.push(
        vscode.commands.registerCommand('agent-chat.show', () => {
            vscode.commands.executeCommand('workbench.view.extension.agent-chat');
        })
    );

    return disposables;
}
