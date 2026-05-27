import * as vscode from 'vscode';
import server from './api/server';
import { registerCommands, startBackendService, stopBackendService } from './backend_server';
import { initializeEnvironment } from './tools/environment';
import { registerAgentChat } from './web/myChatView';

const PORT = 6789;

export function activate(context: vscode.ExtensionContext) {
	// Initialize environment
	initializeEnvironment(context.extensionPath)
		.catch(error => {
			console.error('Failed to initialize environment:', error);
		});

	server.listen(PORT, () => {
		console.log(`Server is running on http://localhost:${PORT}`);
	});

	registerCommands(context); 
	startBackendService()
		.then(() => {
			console.log('Backend service started successfully.');
		})
		.catch(error => {
			console.error('Failed to start backend service:', error);
		});

	// context.subscriptions.push(
	//     vscode.workspace.onDidCloseTextDocument(async () => {
	//         if (vscode.window.visibleTextEditors.length === 0) {
	//             stopBackendService();
	//         }
	//     })
	// );

	const chatDisposables = registerAgentChat(context);
	context.subscriptions.push(...chatDisposables);
}

export function deactivate() {
	// if (vscode.window.visibleTextEditors.length === 0) {
	stopBackendService();
	// }
}