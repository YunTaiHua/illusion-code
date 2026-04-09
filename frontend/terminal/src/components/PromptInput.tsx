import React from 'react';
import {Box, Text} from 'ink';
import TextInput from 'ink-text-input';

import type {UiLanguage} from '../i18n.js';
import {t} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';
import {Spinner} from './Spinner.js';

const noop = (): void => {};

export function PromptInput({
	busy,
	input,
	setInput,
	onSubmit,
	toolName,
	suppressSubmit,
	language,
}: {
	busy: boolean;
	input: string;
	setInput: (value: string) => void;
	onSubmit: (value: string) => void;
	toolName?: string;
	suppressSubmit?: boolean;
	language: UiLanguage;
}): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box marginTop={1} flexDirection="column">
			{busy ? (
				<Box marginBottom={1}>
					<Spinner label={toolName ? `${t(language, 'statusToolPrefix')} ${toolName}...` : t(language, 'statusThinking')} />
				</Box>
			) : null}
			<Box>
				<Text color={theme.colors.primary} bold>{theme.icons.user} </Text>
				<TextInput value={input} onChange={setInput} onSubmit={suppressSubmit ? noop : onSubmit} />
			</Box>
			<Box>
				<Text color={theme.colors.muted}>{'─'.repeat(60)}</Text>
			</Box>
			<Text dimColor>{t(language, 'inputHint')}</Text>
		</Box>
	);
}
