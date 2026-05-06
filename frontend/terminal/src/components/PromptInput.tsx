import React from 'react';
import {Box, Text} from 'ink';
import TextInput from 'ink-text-input';

import type {UiLanguage} from '../i18n.js';
import {t} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';
import {Spinner} from './Spinner.js';
import type {TodoItemSnapshot} from '../types.js';

function noop(): void {}

export function PromptInput({
	busy,
	input,
	setInput,
	onSubmit,
	toolName,
	suppressSubmit,
	language,
	todoItems,
}: {
	busy: boolean;
	input: string;
	setInput: (value: string) => void;
	onSubmit: (value: string) => void;
	toolName?: string;
	suppressSubmit?: boolean;
	language: UiLanguage;
	todoItems?: TodoItemSnapshot[];
}): React.JSX.Element {
	const theme = useTheme();

	return (
		<Box flexDirection="column" marginTop={1}>
			{busy ? (
				<Box marginBottom={1}>
					<Spinner todoItems={todoItems} language={language} toolName={toolName} />
				</Box>
			) : null}
			<Box borderStyle="round" borderLeft={false} borderRight={false} borderColor={theme.colors.promptBorder} paddingLeft={1} paddingRight={1}>
				<Text color={theme.colors.illusion} dimColor={busy}>{theme.icons.pointer} </Text>
				<TextInput value={input} onChange={setInput} onSubmit={suppressSubmit ? noop : onSubmit} />
			</Box>
		</Box>
	);
}
