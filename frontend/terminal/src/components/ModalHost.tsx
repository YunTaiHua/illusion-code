import React, {useEffect, useMemo, useState} from 'react';
import {Box, Text, useInput} from 'ink';
import TextInput from 'ink-text-input';

import type {UiLanguage} from '../i18n.js';
import {t} from '../i18n.js';
import {useTheme} from '../theme/ThemeContext.js';

type QuestionOption = {
	label: string;
	description?: string;
	preview?: string;
};

type QuestionItem = {
	question: string;
	header?: string;
	options?: QuestionOption[];
	multiSelect?: boolean;
};

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
	const theme = useTheme();
	const [extraLines, setExtraLines] = useState<string[]>([]);
	const [optionIndex, setOptionIndex] = useState(0);
	const [isCustomInput, setIsCustomInput] = useState(false);

	const questions: QuestionItem[] = useMemo(() => {
		const raw = modal.questions;
		if (!Array.isArray(raw)) return [];
		return raw as QuestionItem[];
	}, [modal.questions]);

	const firstQuestion = questions.length > 0 ? questions[0] : null;
	const options = firstQuestion?.options ?? [];
	const hasOptions = options.length > 0;

	type OptionEntry = {type: 'option'; label: string; description?: string} | {type: 'other'; label: string; description?: undefined};

	const allOptions = useMemo(() => {
		if (!hasOptions) return [] as OptionEntry[];
		const result: OptionEntry[] = options.map((opt) => ({type: 'option' as const, label: opt.label, description: opt.description}));
		result.push({type: 'other' as const, label: language === 'zh-CN' ? '其他（手动输入）' : 'Other (type your answer)', description: undefined});
		return result;
	}, [options, hasOptions, language]);

	useEffect(() => {
		setOptionIndex(0);
		setIsCustomInput(false);
	}, [hasOptions, allOptions.length]);

	useInput((_chunk, key) => {
		if (isCustomInput) {
			if (key.shift && key.return) {
				setExtraLines((lines) => [...lines, modalInput]);
				setModalInput('');
			}
			if (key.escape) {
				setIsCustomInput(false);
				setModalInput('');
			}
			return;
		}

		if (hasOptions && allOptions.length > 0) {
			if (key.upArrow) {
				setOptionIndex((i) => Math.max(0, i - 1));
				return;
			}
			if (key.downArrow) {
				setOptionIndex((i) => Math.min(allOptions.length - 1, i + 1));
				return;
			}
			if (key.return) {
				const selected = allOptions[optionIndex];
				if (selected?.type === 'other') {
					setIsCustomInput(true);
				} else if (selected) {
					const idx = optionIndex + 1;
					onSubmit(`${idx}. ${selected.label}`);
				}
				return;
			}
			const num = parseInt(_chunk, 10);
			if (num >= 1 && num <= options.length) {
				onSubmit(`${num}. ${options[num - 1].label}`);
				return;
			}
		} else {
			if (key.shift && key.return) {
				setExtraLines((lines) => [...lines, modalInput]);
				setModalInput('');
			}
		}
	});

	const handleSubmit = (value: string): void => {
		if (isCustomInput) {
			const allLines = [...extraLines, value];
			setExtraLines([]);
			setIsCustomInput(false);
			onSubmit(allLines.join('\n'));
			return;
		}
		if (hasOptions) {
			return;
		}
		const allLines = [...extraLines, value];
		setExtraLines([]);
		onSubmit(allLines.join('\n'));
	};

	const toolName = modal.tool_name ? String(modal.tool_name) : null;
	const reason = modal.reason ? String(modal.reason) : null;
	const question = String(modal.question ?? 'Question');
	const header = firstQuestion?.header;

	return (
		<Box flexDirection="column" marginTop={1}>
			<Box>
				<Text color={theme.colors.illusion}>{theme.icons.pointer} </Text>
				{header ? (
					<>
						<Text color={theme.colors.suggestion} bold>[{header}] </Text>
						<Text bold>{firstQuestion?.question ?? question}</Text>
					</>
				) : (
					<Text bold>{firstQuestion?.question ?? question}</Text>
				)}
			</Box>
			{toolName ? (
				<Box>
					<Text dimColor>{`  ${theme.icons.resultPrefix} `}</Text>
					<Text dimColor>Tool: </Text>
					<Text color={theme.colors.info}>{toolName}</Text>
				</Box>
			) : null}
			{reason ? (
				<Box>
					<Text dimColor>{`  ${theme.icons.resultPrefix} `}</Text>
					<Text dimColor>{reason}</Text>
				</Box>
			) : null}

			{hasOptions && !isCustomInput ? (
				<Box flexDirection="column" marginTop={1}>
					{allOptions.map((opt, i) => {
						const isSelected = i === optionIndex;
						return (
							<Box key={i}>
								<Text color={isSelected ? theme.colors.suggestion : theme.colors.muted}>
									{isSelected ? `${theme.icons.pointer} ` : '  '}
								</Text>
								<Text color={isSelected ? theme.colors.suggestion : undefined} bold={isSelected} dimColor={!isSelected}>
									{opt.type === 'option' ? `${i + 1}. ` : '  '}
									{opt.label}
								</Text>
								{opt.description ? (
									<Box marginLeft={1}>
										<Text dimColor>{theme.icons.middleDot} {opt.description}</Text>
									</Box>
								) : null}
								{isSelected ? <Text dimColor>{' [enter]'}</Text> : null}
							</Box>
						);
					})}
					<Box marginTop={0}>
						<Text dimColor>
							<Text color={theme.colors.muted}>↑↓</Text> navigate
							<Text> {theme.icons.middleDot} </Text>
							<Text color={theme.colors.muted}>↵</Text> select
							<Text> {theme.icons.middleDot} </Text>
							<Text color={theme.colors.muted}>1-{options.length}</Text> quick
						</Text>
					</Box>
				</Box>
			) : null}

			{(isCustomInput || !hasOptions) ? (
				<>
					{isCustomInput ? (
						<Box marginTop={1}>
							<Text dimColor>{`  ${theme.icons.resultPrefix} `}</Text>
							<Text dimColor>{language === 'zh-CN' ? '请输入您的回答：' : 'Type your answer:'}</Text>
						</Box>
					) : null}
					{extraLines.length > 0 && (
						<Box flexDirection="column" marginTop={1}>
							{extraLines.map((line, i) => (
								<Box key={i}>
									<Text dimColor>{`  ${theme.icons.resultPrefix} `}</Text>
									<Text dimColor>{line}</Text>
								</Box>
							))}
						</Box>
					)}
					<Box marginTop={1}>
						<Text color={theme.colors.illusion}>{theme.icons.pointer} </Text>
						<TextInput value={modalInput} onChange={setModalInput} onSubmit={handleSubmit} />
					</Box>
				</>
			) : null}
		</Box>
	);
}

function PermissionModal({
	modal,
}: {
	modal: Record<string, unknown>;
}): React.JSX.Element {
	const theme = useTheme();
	const toolName = String(modal.tool_name ?? 'tool');
	const reason = modal.reason ? String(modal.reason) : null;

	return (
		<Box flexDirection="column" marginTop={1}>
			<Box>
				<Text color={theme.colors.warning}>{theme.icons.pointer} </Text>
				<Text bold>Allow </Text>
				<Text color={theme.colors.info} bold>{toolName}</Text>
				<Text bold>?</Text>
			</Box>
			{reason ? (
				<Box>
					<Text dimColor>{`  ${theme.icons.resultPrefix} `}</Text>
					<Text dimColor>{reason}</Text>
				</Box>
			) : null}
			<Box>
				<Text dimColor>{`  ${theme.icons.resultPrefix} `}</Text>
				<Text dimColor>
					<Text color={theme.colors.muted}>↑↓</Text> navigate
					<Text> {theme.icons.middleDot} </Text>
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
	const theme = useTheme();
	const prompt = String(modal.prompt ?? 'Provide auth details');

	return (
		<Box flexDirection="column" marginTop={1}>
			<Box>
				<Text color={theme.colors.warning}>{theme.icons.pointer} </Text>
				<Text bold>MCP Authentication</Text>
			</Box>
			<Box>
				<Text dimColor>{`  ${theme.icons.resultPrefix} `}</Text>
				<Text dimColor>{prompt}</Text>
			</Box>
			<Box marginTop={1}>
				<Text color={theme.colors.illusion}>{theme.icons.pointer} </Text>
				<TextInput value={modalInput} onChange={setModalInput} onSubmit={onSubmit} />
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
