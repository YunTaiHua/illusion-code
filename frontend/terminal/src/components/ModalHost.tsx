import React, {useEffect, useState} from 'react';
import {Box, Text, useInput} from 'ink';
import TextInput from 'ink-text-input';

import type {UiLanguage} from '../i18n.js';
import {t} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';

const WAIT_FRAMES = [
	'Waiting for input   ',
	'Waiting for input.  ',
	'Waiting for input.. ',
	'Waiting for input...',
];

function WaitingAnimation(): React.JSX.Element {
	const {theme} = useTheme();
	const [frame, setFrame] = useState(0);
	useEffect(() => {
		const timer = setInterval(() => setFrame((f) => (f + 1) % WAIT_FRAMES.length), 500);
		return () => clearInterval(timer);
	}, []);
	return (
		<Text color={theme.colors.accent} dimColor>
			{WAIT_FRAMES[frame]}
		</Text>
	);
}

function QuestionModal({
	modal,
	modalInput,
	setModalInput,
	onSubmit,
	language,
}: {
	modal: Record<string, unknown>;
	modalInput: string;
	setModalInput: (value: string) => void;
	onSubmit: (value: string) => void;
	language: UiLanguage;
}): React.JSX.Element {
	const {theme} = useTheme();
	const [extraLines, setExtraLines] = useState<string[]>([]);

	useInput((_chunk, key) => {
		if (key.shift && key.return) {
			setExtraLines((lines) => [...lines, modalInput]);
			setModalInput('');
		}
	});

	const handleSubmit = (value: string): void => {
		const allLines = [...extraLines, value];
		setExtraLines([]);
		onSubmit(allLines.join('\n'));
	};

	const toolName = modal.tool_name ? String(modal.tool_name) : null;
	const reason = modal.reason ? String(modal.reason) : null;
	const question = String(modal.question ?? 'Question');

	return (
		<Box flexDirection="column" marginTop={1} borderStyle="round" borderColor={theme.colors.accent} paddingX={1}>
			<Box marginBottom={1}>
				<WaitingAnimation />
			</Box>
			<Box>
				<Text color={theme.colors.accent} bold>{theme.icons.chevron}  </Text>
				<Text bold>{question}</Text>
			</Box>
			{toolName ? (
				<Box marginLeft={3}>
					<Text dimColor>Tool: </Text>
					<Text color={theme.colors.primary}>{toolName}</Text>
				</Box>
			) : null}
			{reason ? (
				<Box marginLeft={3}>
					<Text dimColor>{reason}</Text>
				</Box>
			) : null}
			{extraLines.length > 0 && (
				<Box flexDirection="column" marginTop={1} marginLeft={3}>
					{extraLines.map((line, i) => (
						<Text key={i} dimColor>
							{line}
						</Text>
					))}
				</Box>
			)}
			<Box marginTop={1}>
				<Text color={theme.colors.primary}>{theme.icons.user} </Text>
				<TextInput value={modalInput} onChange={setModalInput} onSubmit={handleSubmit} />
			</Box>
			<Box marginTop={1}>
				<Text dimColor>{'─'.repeat(50)}</Text>
			</Box>
			<Box marginLeft={3}>
				<Text dimColor>{t(language, 'inputHint')}</Text>
			</Box>
		</Box>
	);
}

function PermissionModal({
	modal,
}: {
	modal: Record<string, unknown>;
}): React.JSX.Element {
	const {theme} = useTheme();
	const toolName = String(modal.tool_name ?? 'tool');
	const reason = modal.reason ? String(modal.reason) : null;

	return (
		<Box flexDirection="column" marginTop={1}>
			<Box>
				<Text color={theme.colors.warning} bold>{theme.icons.chevron}  </Text>
				<Text bold>Allow </Text>
				<Text color={theme.colors.primary} bold>{toolName}</Text>
				<Text bold>?</Text>
			</Box>
			{reason ? (
				<Box marginLeft={3}>
					<Text dimColor>{reason}</Text>
				</Box>
			) : null}
			<Box marginLeft={3}>
				<Text dimColor>
					<Text color={theme.colors.muted}>↑↓</Text> navigate
					<Text>  </Text>
					<Text color={theme.colors.muted}>↵</Text> select
				</Text>
			</Box>
		</Box>
	);
}

function McpAuthModal({
	modal,
	modalInput,
	setModalInput,
	onSubmit,
	language,
}: {
	modal: Record<string, unknown>;
	modalInput: string;
	setModalInput: (value: string) => void;
	onSubmit: (value: string) => void;
	language: UiLanguage;
}): React.JSX.Element {
	const {theme} = useTheme();
	const prompt = String(modal.prompt ?? 'Provide auth details');

	return (
		<Box flexDirection="column" marginTop={1} borderStyle="round" borderColor={theme.colors.accent} paddingX={1}>
			<Box>
				<Text color={theme.colors.warning} bold>{theme.icons.chevron}  </Text>
				<Text bold>MCP Authentication</Text>
			</Box>
			<Box marginLeft={3}>
				<Text dimColor>{prompt}</Text>
			</Box>
			<Box marginTop={1}>
				<Text color={theme.colors.primary}>{theme.icons.user} </Text>
				<TextInput value={modalInput} onChange={setModalInput} onSubmit={onSubmit} />
			</Box>
			<Box marginTop={1}>
				<Text dimColor>{'─'.repeat(50)}</Text>
			</Box>
			<Box marginLeft={3}>
				<Text dimColor>{t(language, 'inputHint')}</Text>
			</Box>
		</Box>
	);
}

export function ModalHost({
	modal,
	modalInput,
	setModalInput,
	onSubmit,
	language,
}: {
	modal: Record<string, unknown> | null;
	modalInput: string;
	setModalInput: (value: string) => void;
	onSubmit: (value: string) => void;
	language: UiLanguage;
}): React.JSX.Element | null {
	if (!modal) {
		return null;
	}

	if (modal.kind === 'permission') {
		return <PermissionModal modal={modal} />;
	}

	if (modal.kind === 'question') {
		return (
			<QuestionModal
				modal={modal}
				modalInput={modalInput}
				setModalInput={setModalInput}
				onSubmit={onSubmit}
				language={language}
			/>
		);
	}

	if (modal.kind === 'mcp_auth') {
		return (
			<McpAuthModal
				modal={modal}
				modalInput={modalInput}
				setModalInput={setModalInput}
				onSubmit={onSubmit}
				language={language}
			/>
		);
	}

	return null;
}
