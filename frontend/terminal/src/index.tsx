import React from 'react';
import {render} from 'ink';

import {App} from './App.js';
import type {FrontendConfig} from './types.js';

const config = JSON.parse(process.env.ILLUSION_FRONTEND_CONFIG ?? '{}') as FrontendConfig;

// Restore terminal cursor visibility on exit (Ink hides it by default)
const restoreCursor = (): void => {
	process.stdout.write('\x1B[?25h');
};
process.on('exit', restoreCursor);
// SIGINT 由 App 组件中的 useInput 处理，不再强制退出
// 仅在无法恢复时作为安全网退出
process.on('SIGTERM', () => {
	restoreCursor();
	process.exit(143);
});

render(<App config={config} />);
