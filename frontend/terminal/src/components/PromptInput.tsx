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
			{busy ? <Spinner label={toolName ? `${t(language, 'statusToolPrefix')} ${toolName}...` : t(language, 'statusThinking')} /> : null}
			<Box>
				<Text color={theme.colors.primary} bold>{'▸  '}</Text>
				<TextInput value={input} onChange={setInput} onSubmit={suppressSubmit ? noop : onSubmit} />
			</Box>
			<Text color={theme.colors.muted}>{'────────────────────────────────────────────────────────────'}</Text>
			<Text dimColor>{t(language, 'inputHint')}</Text>
		</Box>
	);
}
