import React, {useEffect, useMemo, useState} from 'react';
import {useInput} from 'ink';

import type {UiLanguage} from '../i18n.js';
import type {TodoItemSnapshot} from '../types.js';
import {CommandPicker} from './CommandPicker.js';
import {PromptInput} from './PromptInput.js';

export function ComposerController({
	commands,
	busy,
	disabled,
	language,
	todoItems,
	toolName,
	onSubmit,
}: {
	commands: string[];
	busy: boolean;
	disabled: boolean;
	language: UiLanguage;
	todoItems: TodoItemSnapshot[];
	toolName?: string;
	onSubmit: (value: string) => void;
}): React.JSX.Element | null {
	const [input, setInput] = useState('');
	const [pickerIndex, setPickerIndex] = useState(0);
	const [localBusy, setLocalBusy] = useState(false);

	const commandHints = useMemo(() => {
		if (!input.startsWith('/')) {
			return [] as string[];
		}
		const value = input.trimEnd();
		if (!value) {
			return [] as string[];
		}
		const matches = commands.filter((cmd) => cmd.startsWith(value));
		if (value === '/') {
			const preferred = ['/language'];
			const boosted = preferred.filter((cmd) => matches.includes(cmd));
			const rest = matches.filter((cmd) => !preferred.includes(cmd));
			return [...boosted, ...rest];
		}
		return matches;
	}, [commands, input]);

	const showPicker = !disabled && input.startsWith('/') && commandHints.length > 0;
    const effectiveBusy = busy || localBusy;

	useEffect(() => {
		setPickerIndex(0);
	}, [showPicker, commandHints.length, input]);

	useEffect(() => {
		if (!busy) {
			setLocalBusy(false);
		}
	}, [busy]);

	useInput((chunk, key) => {
		if (disabled) {
			return;
		}

		if (showPicker) {
			if (key.upArrow) {
				setPickerIndex((i) => Math.max(0, i - 1));
				return;
			}
			if (key.downArrow) {
				setPickerIndex((i) => Math.min(commandHints.length - 1, i + 1));
				return;
			}
			if (key.return) {
				const selected = commandHints[pickerIndex];
				if (selected) {
					setLocalBusy(true);
					setInput('');
					onSubmit(selected);
				}
				return;
			}
			if (key.tab) {
				const selected = commandHints[pickerIndex];
				if (selected) {
					setInput(selected + ' ');
				}
				return;
			}
			if (key.escape) {
				setInput('');
				return;
			}
		}

		if (!showPicker && (key.upArrow || key.downArrow)) {
			return;
		}
	});

	if (disabled || effectiveBusy) {
		return null;
	}

	return (
		<>
			{showPicker ? <CommandPicker hints={commandHints} selectedIndex={pickerIndex} totalCommands={commands.length} /> : null}
			<PromptInput
				busy={effectiveBusy}
				input={input}
				setInput={setInput}
				onSubmit={(value) => {
					if (!value.trim() || disabled) {
						return;
					}
					setLocalBusy(true);
					onSubmit(value);
					setInput('');
				}}
				toolName={toolName}
				suppressSubmit={showPicker}
				language={language}
				todoItems={todoItems}
			/>
		</>
	);
}
