import React from 'react';
import {Box, Text} from 'ink';

import type {UiLanguage} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';
import type {TranscriptItem} from '../types.js';
import {ToolCallDisplay} from './ToolCallDisplay.js';
import {WelcomeBanner} from './WelcomeBanner.js';

export function ConversationView({
	items,
	assistantBuffer,
	showWelcome,
	language,
}: {
	items: TranscriptItem[];
	assistantBuffer: string;
	showWelcome: boolean;
	language: UiLanguage;
}): React.JSX.Element {
	const {theme} = useTheme();
	const visible = items.slice(-40);

	return (
		<Box flexDirection="column" flexGrow={1}>
			{showWelcome && items.length === 0 ? <WelcomeBanner language={language} /> : null}

			{visible.map((item, index) => (
				<MessageRow key={index} item={item} theme={theme} language={language} />
			))}

			{assistantBuffer ? (
				<Box flexDirection="row" marginTop={1}>
					<Text color={theme.colors.success} bold>{theme.icons.assistant}</Text>
					<Text>{assistantBuffer}</Text>
				</Box>
			) : null}
		</Box>
	);
}

function MessageRow({
	item,
	theme,
	language,
}: {
	item: TranscriptItem;
	theme: ReturnType<typeof useTheme>['theme'];
	language: UiLanguage;
}): React.JSX.Element {
	switch (item.role) {
		case 'user':
			return (
				<Box marginTop={1} marginBottom={0}>
					<Text>
						<Text color={theme.colors.primary} bold>{theme.icons.user}</Text>
						<Text>{item.text}</Text>
					</Text>
				</Box>
			);

		case 'assistant':
			return (
				<Box marginTop={1} marginBottom={0} flexDirection="column">
					<Text>
						<Text color={theme.colors.success} bold>{theme.icons.assistant}</Text>
						<Text>{item.text}</Text>
					</Text>
				</Box>
			);

		case 'tool':
		case 'tool_result':
			return <ToolCallDisplay item={item} language={language} />;

		case 'system':
			return (
				<Box marginTop={1}>
					<Text>
						<Text color={theme.colors.warning}>{theme.icons.system}</Text>
						<Text color={theme.colors.muted}>{item.text}</Text>
					</Text>
				</Box>
			);

		case 'log':
			return (
				<Box marginTop={0}>
					<Text dimColor>{item.text}</Text>
				</Box>
			);

		default:
			return (
				<Box>
					<Text>{item.text}</Text>
				</Box>
			);
	}
}
