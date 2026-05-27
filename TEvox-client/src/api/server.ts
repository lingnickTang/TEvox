import express from 'express';
import debugRouter from './debugger';
import navigationRouter from './navigation';
import pioRouter from './platformio';
import terminalRouter from './terminal';
import workspaceRouter from './workspace';
import symbolsRouter from './symbols';
import environmentRouter from './environment';

const server = express();

server.use(express.json());
server.use('/platformio', pioRouter);
server.use('/workspace', workspaceRouter);
server.use('/terminal', terminalRouter);
server.use('/debugger', debugRouter);
server.use('/navigation', navigationRouter);
server.use('/symbols', symbolsRouter);

// 添加调试：打印所有注册的路由
console.log('=== Registered Symbols Routes ===');
symbolsRouter.stack?.forEach((layer: any) => {
    if (layer.route) {
        console.log(`${Object.keys(layer.route.methods).join(', ').toUpperCase()} ${layer.route.path}`);
    }
});
console.log('================================');

server.use('/environment', environmentRouter);

export default server;

