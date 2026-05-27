export interface TaskMetadata {
    taskId: string;
    description: string;
    createdAt: string;
    lastUpdated: string;
    conversationCount: number;
}

export interface TaskDetail {
    taskId: string;
    description: string;
    createdAt: string;
    conversations: ConversationEntry[];
}

export interface ConversationEntry {
    timestamp: string;
    type: 'user' | 'assistant';
    content: string;
}

export interface TaskMessage {
    type: 'newTask' | 'feedback';
    content: string;
}

export interface TaskResponse {
    task_id: string;
    result: string;
}
