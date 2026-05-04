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

// --- Suppress resize events ---
// ink's eraseLines(N) + output pattern causes visible flicker on every resize.
// But ink recalculates layout on EVERY React re-render (reading stdout.columns),
// not just on resize events. So we can safely suppress resize events entirely.
//
// Layout still updates correctly when:
// - User types (PromptInput state change → React re-render → layout recalc)
// - Spinner ticks during busy state (32ms interval → React re-render)
// - Backend sends events (status changes → React re-render)
//
// The only effect: terminal content doesn't reflow on resize until the next
// React re-render. This is acceptable because idle content (StatusBar, hints)
// is short and reflows on the next user interaction.
const _origEmit = process.stdout.emit.bind(process.stdout);
process.stdout.emit = function (event: string, ...args: unknown[]) {
	if (event === 'resize') {
		return false;
	}
	return _origEmit(event, ...args);
} as typeof process.stdout.emit;

render(<App config={config} />);
