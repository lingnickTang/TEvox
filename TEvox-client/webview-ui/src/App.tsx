// src/App.tsx
import React, { useEffect, useRef, useState } from 'react';
import './App.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  type: 'user' | 'assistant';
  content: string;
}

interface Task {
  taskId: string;
  description: string;
  conversations: Message[];
}

const vscode = window.acquireVsCodeApi();

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [showContinueButton, setShowContinueButton] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      switch (message.type) {
        case 'loadTask':
          loadTask(message.task);
          setShowContinueButton(false);
          break;
        case 'result':
          addMessage('assistant', message.content);
          setShowContinueButton(true);
          if (message.taskId) {
            setCurrentTaskId(message.taskId);
          }
          break;
        case 'error':
          showError(message.content);
          setShowContinueButton(false);
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const loadTask = (task: Task) => {
    setCurrentTaskId(task.taskId);
    setMessages(task.conversations);
  };

  const addMessage = (type: 'user' | 'assistant', content: string) => {
    setMessages(prev => [...prev, { type, content }]);
    if (type === 'user') {
      setShowContinueButton(false);
    }
  };

  const showError = (content: string) => {
    setMessages(prev => [...prev, { type: 'assistant', content: `错误: ${content}` }]);
  };

  const handleSend = () => {
    if (!inputValue.trim()) return;

    const messageType = currentTaskId ? 'feedback' : 'newTask';
    vscode.postMessage({
      type: messageType,
      content: inputValue
    });
    addMessage('user', inputValue);
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewTask = () => {
    vscode.postMessage({
      type: 'createNewTask'
    });
    setMessages([]);
    setCurrentTaskId(null);
    setShowContinueButton(false);
  };

  const handleSelectTask = () => {
    vscode.postMessage({
      type: 'showTaskList'
    });
  };

  const handleContinue = () => {
    vscode.postMessage({
      type: 'feedback',
      content: '继续'
    });
    setShowContinueButton(false);
  };

  return (
    <div className="app">
      <div className="header-container">
        <button onClick={handleNewTask}>新建任务</button>
        <button onClick={handleSelectTask}>选择任务</button>
      </div>
      
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.type}`}>
              {msg.type === 'assistant' ? (
                <>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
                {/* 只在最后一条assistant消息后显示继续按钮 */}
                {showContinueButton && index === messages.length - 1 && (
                  <button 
                    onClick={handleContinue}
                    className="continue-button"
                  >
                    继续
                  </button>
                )}
              </>
              ) : (
                msg.content
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        
        <div className="input-container">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={3}
          />
          <button onClick={handleSend}>发送</button>
        </div>
      </div>
    </div>
  );
}

export default App;
