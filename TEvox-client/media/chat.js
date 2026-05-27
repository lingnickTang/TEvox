(function () {
    const vscode = acquireVsCodeApi();
    let currentTaskId = null;

    // 初始化UI元素
    const messagesContainer = document.getElementById('messages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const newTaskButton = document.getElementById('newTaskButton');
    const selectTaskButton = document.getElementById('selectTaskButton');

    // 事件监听
    newTaskButton.addEventListener('click', () => {
        vscode.postMessage({
            type: 'createNewTask'
        });
        // 清空消息框
        messagesContainer.innerHTML = '';
        currentTaskId = null;
    });

    selectTaskButton.addEventListener('click', () => {
        vscode.postMessage({
            type: 'showTaskList'
        });
    });

    sendButton.addEventListener('click', sendMessage);

    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // 阻止默认换行行为
            sendMessage();
        }
    });

    function sendMessage() {
        const content = userInput.value.trim();
        if (!content && currentTaskId === null) return;

        const messageType = currentTaskId ? 'feedback' : 'newTask';
        vscode.postMessage({
            type: messageType,
            content: content
        });
        addMessage('user', content);

        userInput.value = '';
    }

    // 接收来自扩展的消息
    window.addEventListener('message', event => {
        const message = event.data;

        switch (message.type) {
            case 'loadTask':
                loadTask(message.task);
                break;
            case 'result':
                addMessage('assistant', message.content);
                if (message.taskId) {
                    currentTaskId = message.taskId;
                }
                break;
            case 'error':
                showError(message.content);
                break;
        }
    });

    function loadTask(task) {
        currentTaskId = task.taskId;
        messagesContainer.innerHTML = '';
        task.conversations.forEach(conv => {
            addMessage(conv.type, conv.content);
        });
    }

    function addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = content;
        messagesContainer.appendChild(messageDiv);
        messageDiv.scrollIntoView({ behavior: 'smooth' });
    }

    function showError(content) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message error';
        errorDiv.textContent = `错误: ${content}`;
        messagesContainer.appendChild(errorDiv);
        errorDiv.scrollIntoView({ behavior: 'smooth' });
    }
})();
