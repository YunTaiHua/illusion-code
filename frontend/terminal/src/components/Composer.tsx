import React from 'react';
import {Box, Text} from 'ink';
import TextInput from 'ink-text-input';

import {useTheme} from '../theme/ThemeContext.js';

export function Composer({
	busy,
	input,
	setInput,
	onSubmit,
	historyIndex,
}: {
	busy: boolean;
	input: string;
	setInput: (value: string) => void;
	onSubmit: (value: string) => void;
	historyIndex: number;
}): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box flexDirection="column" marginTop={1}>
			<Box borderStyle="round" borderColor={busy ? theme.colors.warning : theme.colors.success} paddingX={1}>
				<Text color={busy ? theme.colors.warning : theme.colors.success} bold>
					{busy ? theme.icons.inProgress : theme.icons.completed}{' '}
				</Text>
				<Text color={busy ? theme.colors.warning : theme.colors.success} bold>
					{busy ? 'busy' : 'ready'}
				</Text>
				<Text> </Text>
				<TextInput value={input} onChange={setInput} onSubmit={onSubmit} />
			</Box>
			<Box marginTop={1}>
				<Text dimColor>
					<Text color={theme.colors.muted}>enter</Text>=submit{' '}
					<Text color={theme.colors.muted}>tab</Text>=complete{' '}
					<Text color={theme.colors.muted}>ctrl-p/ctrl-n</Text>=history{' '}
					<Text color={theme.colors.muted}>history_index</Text>={String(historyIndex)}
				</Text>
			</Box>
		</Box>
	);
}
