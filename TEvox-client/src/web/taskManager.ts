// src/taskManager.ts
import * as vscode from 'vscode';
import { ConversationEntry, TaskDetail, TaskMetadata } from './types';

export class TaskManager {
    private metadataUri: vscode.Uri;
    private tasksDirectory: vscode.Uri;
    private taskMetadata: Map<string, TaskMetadata> = new Map();
    private currentTaskId: string | null = null;

    constructor(private context: vscode.ExtensionContext) {
        this.metadataUri = vscode.Uri.joinPath(context.globalStorageUri, 'task-metadata.json');
        this.tasksDirectory = vscode.Uri.joinPath(context.globalStorageUri, 'tasks');
        console.log('Global Storage URI:', context.globalStorageUri.fsPath);
        this.loadMetadata();
    }

    private async loadMetadata() {
        try {
            const data = await vscode.workspace.fs.readFile(this.metadataUri);
            const content = Buffer.from(data).toString('utf8');
            const parsed = JSON.parse(content);
            this.taskMetadata = new Map(Object.entries(parsed));
        } catch (error) {
            this.taskMetadata = new Map();
        }
    }

    private async saveMetadata() {
        try {
            await vscode.workspace.fs.createDirectory(vscode.Uri.joinPath(this.metadataUri, '..'));
            const content = JSON.stringify(Object.fromEntries(this.taskMetadata));
            await vscode.workspace.fs.writeFile(
                this.metadataUri,
                Buffer.from(content, 'utf8')
            );
        } catch (error) {
            console.error('Error saving task metadata:', error);
            throw error;
        }
    }

    private async ensureTasksDirectory() {
        try {
            await vscode.workspace.fs.createDirectory(this.tasksDirectory);
        } catch (error) {
            // 目录可能已存在，忽略错误
        }
    }

    private getTaskFileUri(taskId: string): vscode.Uri {
        return vscode.Uri.joinPath(this.tasksDirectory, `${taskId}.json`);
    }

    private async loadTaskDetail(taskId: string): Promise<TaskDetail | null> {
        try {
            const taskUri = this.getTaskFileUri(taskId);
            const data = await vscode.workspace.fs.readFile(taskUri);
            return JSON.parse(Buffer.from(data).toString('utf8'));
        } catch (error) {
            return null;
        }
    }

    private async saveTaskDetail(taskDetail: TaskDetail) {
        await this.ensureTasksDirectory();
        const taskUri = this.getTaskFileUri(taskDetail.taskId);
        await vscode.workspace.fs.writeFile(
            taskUri,
            Buffer.from(JSON.stringify(taskDetail), 'utf8')
        );
    }

    private generateTaskId(): string {
        const now = new Date();
        
        // 格式化为 YYYY-MM-DD-HHmmss
        const year = now.getFullYear();
        const month = (now.getMonth() + 1).toString().padStart(2, '0');
        const day = now.getDate().toString().padStart(2, '0');
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        const seconds = now.getSeconds().toString().padStart(2, '0');
        
        return `${year}-${month}-${day}-${hours}${minutes}${seconds}`;
    }

    public async createNewTask(description: string): Promise<TaskDetail> {
        const taskId = this.generateTaskId();
        const now = new Date().toISOString();

        const metadata: TaskMetadata = {
            taskId,
            description,
            createdAt: now,
            lastUpdated: now,
            conversationCount: 0
        };

        const taskDetail: TaskDetail = {
            taskId,
            description,
            createdAt: now,
            conversations: []
        };

        this.taskMetadata.set(taskId, metadata);
        await this.saveMetadata();
        await this.saveTaskDetail(taskDetail);

        this.currentTaskId = taskId;
        return taskDetail;
    }

    public async addConversation(type: 'user' | 'assistant', content: string) {
        if (!this.currentTaskId) throw new Error('No active task');

        const metadata = this.taskMetadata.get(this.currentTaskId);
        const taskDetail = await this.loadTaskDetail(this.currentTaskId);

        if (!metadata || !taskDetail) throw new Error('Task not found');

        const newEntry: ConversationEntry = {
            timestamp: new Date().toISOString(),
            type,
            content
        };

        // 更新任务详情
        taskDetail.conversations.push(newEntry);
        await this.saveTaskDetail(taskDetail);

        // 更新元数据
        metadata.lastUpdated = new Date().toISOString();
        metadata.conversationCount = taskDetail.conversations.length;
        await this.saveMetadata();
    }

    public async getCurrentTask(): Promise<TaskDetail | null> {
        if (!this.currentTaskId) return null;
        return await this.loadTaskDetail(this.currentTaskId);
    }

    public getTaskMetadataList(): TaskMetadata[] {
        return Array.from(this.taskMetadata.values());
    }

    public async setCurrentTask(taskId: string | null): Promise<TaskDetail | null> {
        if (taskId === null) {
            this.currentTaskId = null;
            return null;
        }

        if (!this.taskMetadata.has(taskId)) throw new Error('Task not found');
        this.currentTaskId = taskId;
        return await this.loadTaskDetail(taskId);
    }

    public async deleteTask(taskId: string): Promise<void> {
        if (!this.taskMetadata.has(taskId)) return;

        // 删除任务文件
        try {
            await vscode.workspace.fs.delete(this.getTaskFileUri(taskId));
        } catch (error) {
            // 文件可能不存在，忽略错误
        }

        // 删除元数据
        this.taskMetadata.delete(taskId);
        await this.saveMetadata();

        // 如果是当前任务，清除当前任务ID
        if (this.currentTaskId === taskId) {
            this.currentTaskId = null;
        }
    }
}
