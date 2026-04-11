export type UiLanguage = 'zh-CN' | 'en';

type Dict = Record<string, string>;

const ZH: Dict = {
	connecting: '正在连接后端...',
	send: '发送',
	commands: '命令',
	history: '历史',
	exit: '退出',
	permissionMode: '权限模式',
	language: '语言',
	langZh: '简体中文',
	langEn: 'English',
	inputHint: 'shift+enter: 换行 | enter: 提交',
	allow: '允许',
	alwaysAllow: '总是允许',
	deny: '拒绝',
	welcomeSub: 'AI 编码助手',
	statusReady: '就绪',
	statusThinking: '思考中...',
	statusExecuting: '执行指令中...',
	statusToolPrefix: '执行工具',
	stopTask: '停止任务',
	showThinking: '显示思考',
	hideThinking: '隐藏思考',
};

const EN: Dict = {
	connecting: 'Connecting to backend...',
	send: 'send',
	commands: 'commands',
	history: 'history',
	exit: 'exit',
	permissionMode: 'Permission Mode',
	language: 'Language',
	langZh: '简体中文',
	langEn: 'English',
	inputHint: 'shift+enter: newline | enter: submit',
	allow: 'Allow',
	alwaysAllow: 'Always Allow',
	deny: 'Deny',
	welcomeSub: 'An AI-powered coding assistant',
	statusReady: 'Ready',
	statusThinking: 'Thinking...',
	statusExecuting: 'Executing command...',
	statusToolPrefix: 'Running tool',
	stopTask: 'stop task',
	showThinking: 'show thinking',
	hideThinking: 'hide thinking',
};

const ALL: Record<UiLanguage, Dict> = {
	'zh-CN': ZH,
	en: EN,
};

export function normalizeLanguage(raw: unknown): UiLanguage {
	return raw === 'en' ? 'en' : 'zh-CN';
}

export function t(lang: UiLanguage, key: keyof typeof ZH): string {
	return ALL[lang][key] ?? ZH[key];
}
