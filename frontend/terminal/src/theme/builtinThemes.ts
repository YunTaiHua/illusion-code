export type ThemeConfig = {
	name: string;
	colors: {
		primary: string;
		secondary: string;
		accent: string;
		foreground: string;
		background: string;
		muted: string;
		success: string;
		warning: string;
		error: string;
		info: string;
		illusion: string;
		illusionShimmer: string;
		text: string;
		subtle: string;
		highlight: string;
		promptBorder: string;
		suggestion: string;
		permission: string;
	};
	icons: {
		spinner: string[];
		tool: string;
		assistant: string;
		user: string;
		system: string;
		success: string;
		error: string;
		pending: string;
		inProgress: string;
		completed: string;
		bullet: string;
		arrow: string;
		check: string;
		cross: string;
		chevron: string;
		dot: string;
		pointer: string;
		middleDot: string;
		resultPrefix: string;
	};
};

export const defaultTheme: ThemeConfig = {
	name: 'default',
	colors: {
		primary: 'cyan',
		secondary: 'white',
		accent: 'magenta',
		foreground: 'white',
		background: 'black',
		muted: 'gray',
		success: 'green',
		warning: 'yellow',
		error: 'red',
		info: '#7dcfff',
		illusion: '#d4a574',
		illusionShimmer: '#e8c49a',
		text: 'white',
		subtle: 'gray',
		highlight: 'cyan',
		promptBorder: 'gray',
		suggestion: '#7aa2f7',
		permission: '#bb9af7',
	},
	icons: {
		spinner: ['✻', '✶', '✢'],
		tool: '●',
		assistant: '●',
		user: '❯',
		system: '⚠',
		success: '✓',
		error: '✗',
		pending: '○',
		inProgress: '◐',
		completed: '●',
		bullet: '•',
		arrow: '→',
		check: '✓',
		cross: '✗',
		chevron: '›',
		dot: '●',
		pointer: '❯',
		middleDot: '·',
		resultPrefix: '⎿',
	},
};

export const darkTheme: ThemeConfig = {
	name: 'dark',
	colors: {
		primary: '#7aa2f7',
		secondary: '#c0caf5',
		accent: '#bb9af7',
		foreground: '#c0caf5',
		background: '#1a1b26',
		muted: '#565f89',
		success: '#9ece6a',
		warning: '#e0af68',
		error: '#f7768e',
		info: '#7dcfff',
		illusion: '#d4a574',
		illusionShimmer: '#e8c49a',
		text: '#c0caf5',
		subtle: '#565f89',
		highlight: '#7aa2f7',
		promptBorder: '#565f89',
		suggestion: '#7aa2f7',
		permission: '#bb9af7',
	},
	icons: {
		spinner: ['✻', '✶', '✢'],
		tool: '●',
		assistant: '●',
		user: '❯',
		system: '⚠',
		success: '✓',
		error: '✗',
		pending: '○',
		inProgress: '◐',
		completed: '●',
		bullet: '•',
		arrow: '→',
		check: '✓',
		cross: '✗',
		chevron: '›',
		dot: '●',
		pointer: '❯',
		middleDot: '·',
		resultPrefix: '⎿',
	},
};

export const minimalTheme: ThemeConfig = {
	name: 'minimal',
	colors: {
		primary: 'white',
		secondary: 'white',
		accent: 'white',
		foreground: 'white',
		background: 'black',
		muted: 'gray',
		success: 'white',
		warning: 'white',
		error: 'white',
		info: 'white',
		illusion: 'white',
		illusionShimmer: 'white',
		text: 'white',
		subtle: 'gray',
		highlight: 'white',
		promptBorder: 'gray',
		suggestion: 'gray',
		permission: 'gray',
	},
	icons: {
		spinner: ['-', '\\', '|', '/'],
		tool: '>',
		assistant: ':',
		user: '>',
		system: '*',
		success: '+',
		error: '!',
		pending: 'o',
		inProgress: '~',
		completed: 'x',
		bullet: '*',
		arrow: '->',
		check: '+',
		cross: '-',
		chevron: '>',
		dot: '*',
		pointer: '>',
		middleDot: '.',
		resultPrefix: '|',
	},
};

export const cyberpunkTheme: ThemeConfig = {
	name: 'cyberpunk',
	colors: {
		primary: '#ff007c',
		secondary: '#00fff9',
		accent: '#ffe600',
		foreground: '#00fff9',
		background: '#0d0d0d',
		muted: '#444444',
		success: '#00ff41',
		warning: '#ffe600',
		error: '#ff003c',
		info: '#00fff9',
		illusion: '#ff007c',
		illusionShimmer: '#ff4da6',
		text: '#00fff9',
		subtle: '#444444',
		highlight: '#ffe600',
		promptBorder: '#444444',
		suggestion: '#00fff9',
		permission: '#ffe600',
	},
	icons: {
		spinner: ['◐', '◓', '◑', '◒'],
		tool: '◈',
		assistant: '◈',
		user: '▸',
		system: '⚡',
		success: '✦',
		error: '✖',
		pending: '○',
		inProgress: '◐',
		completed: '●',
		bullet: '◆',
		arrow: '→',
		check: '✓',
		cross: '✗',
		chevron: '›',
		dot: '●',
		pointer: '▸',
		middleDot: '·',
		resultPrefix: '⎿',
	},
};

export const solarizedTheme: ThemeConfig = {
	name: 'solarized',
	colors: {
		primary: '#268bd2',
		secondary: '#839496',
		accent: '#2aa198',
		foreground: '#839496',
		background: '#002b36',
		muted: '#586e75',
		success: '#859900',
		warning: '#b58900',
		error: '#dc322f',
		info: '#268bd2',
		illusion: '#b58900',
		illusionShimmer: '#cb8e14',
		text: '#839496',
		subtle: '#586e75',
		highlight: '#268bd2',
		promptBorder: '#586e75',
		suggestion: '#268bd2',
		permission: '#2aa198',
	},
	icons: {
		spinner: ['✻', '✶', '✢'],
		tool: '●',
		assistant: '●',
		user: '❯',
		system: '⚠',
		success: '✓',
		error: '✗',
		pending: '○',
		inProgress: '◐',
		completed: '●',
		bullet: '•',
		arrow: '→',
		check: '✓',
		cross: '✗',
		chevron: '›',
		dot: '●',
		pointer: '❯',
		middleDot: '·',
		resultPrefix: '⎿',
	},
};

export const BUILTIN_THEMES: Record<string, ThemeConfig> = {
	default: defaultTheme,
	dark: darkTheme,
	minimal: minimalTheme,
	cyberpunk: cyberpunkTheme,
	solarized: solarizedTheme,
};

export function getTheme(name: string): ThemeConfig {
	return BUILTIN_THEMES[name] ?? defaultTheme;
}
