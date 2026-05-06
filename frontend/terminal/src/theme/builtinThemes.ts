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
		primary: '#56d4dd',
		secondary: 'white',
		accent: 'magenta',
		foreground: 'white',
		background: 'black',
		muted: '#9ca3af',
		success: 'green',
		warning: 'yellow',
		error: 'red',
		info: '#89ddff',
		illusion: '#d4a574',
		illusionShimmer: '#e8c49a',
		text: 'white',
		subtle: '#a8b2c1',
		highlight: '#56d4dd',
		promptBorder: '#8b949e',
		suggestion: '#89ddff',
		permission: '#bb9af7',
	},
	icons: {
		spinner: ['✻', '✶', '✢'],
		tool: '●',
		assistant: '●',
		user: '❯',
		system: '※',
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
