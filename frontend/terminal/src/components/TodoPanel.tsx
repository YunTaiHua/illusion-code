import React, {useState} from 'react';
import {Box, Text, useInput} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';

export type TodoItem = {
	text: string;
	checked: boolean;
};

function parseTodoItems(markdown: string): TodoItem[] {
	const lines = markdown.split('\n');
	const items: TodoItem[] = [];
	for (const line of lines) {
		const m = line.match(/^\s*-\s+\[([ xX])\]\s+(.+)/);
		if (m) {
			items.push({checked: m[1].toLowerCase() === 'x', text: m[2].trim()});
		}
	}
	return items;
}

export function TodoPanel({
	markdown,
	compact: initialCompact = false,
}: {
	markdown: string;
	compact?: boolean;
}): React.JSX.Element | null {
	const [compact, setCompact] = useState(initialCompact);
	const items = parseTodoItems(markdown);
	const {theme} = useTheme();

	useInput((chunk, key) => {
		if (key.ctrl && chunk === 't') {
			setCompact((c) => !c);
		}
	});

	if (items.length === 0) {
		return null;
	}

	const done = items.filter((i) => i.checked).length;
	const total = items.length;

	if (compact) {
		return (
			<Box>
				<Text color={theme.colors.warning} bold>
					{theme.icons.check}{' '}
				</Text>
				<Text dimColor>
					Todos: {done}/{total} done
				</Text>
				<Text dimColor> [ctrl+t to expand]</Text>
			</Box>
		);
	}

	return (
		<Box flexDirection="column" borderStyle="round" borderColor={theme.colors.warning} paddingX={1} marginTop={1}>
			<Box>
				<Text color={theme.colors.warning} bold>
					{theme.icons.check}{' '}
				</Text>
				<Text bold>
					Todo List{' '}
				</Text>
				<Text dimColor>
					({done}/{total})
				</Text>
				<Text dimColor> [ctrl+t to compact]</Text>
			</Box>
			{items.map((item, i) => (
				<Box key={i}>
					<Text color={item.checked ? theme.colors.success : theme.colors.text}>
						{item.checked ? `  ${theme.icons.completed} ` : `  ${theme.icons.pending} `}
					</Text>
					<Text
						color={item.checked ? theme.colors.success : undefined}
						dimColor={item.checked}
					>
						{item.text}
					</Text>
				</Box>
			))}
		</Box>
	);
}

export {parseTodoItems};
