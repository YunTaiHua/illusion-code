import React, {useEffect, useMemo, useState} from 'react';
import {Box, Text, useApp, useInput} from 'ink';

import {CommandPicker} from './components/CommandPicker.js';
import {ConversationView} from './components/ConversationView.js';
import {ModalHost} from './components/ModalHost.js';
import {PromptInput} from './components/PromptInput.js';
import {SelectModal, type SelectOption} from './components/SelectModal.js';
import {StatusBar} from './components/StatusBar.js';
import {SwarmPanel} from './components/SwarmPanel.js';
import {TodoPanel} from './components/TodoPanel.js';
import {useBackendSession} from './hooks/useBackendSession.js';
import {normalizeLanguage, t} from './i18n.js';
import {ThemeProvider, useTheme} from './theme/ThemeContext.js';
import type {FrontendConfig} from './types.js';

const rawReturnSubmit = process.env.ILLUSION_FRONTEND_RAW_RETURN === '1';
const scriptedSteps = (() => {
	const raw = process.env.ILLUSION_FRONTEND_SCRIPT;
	if (!raw) {
		return [] as string[];
	}
	try {
		const parsed = JSON.parse(raw);
		return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
	} catch {
		return [];
	}
})();

const PERMISSION_MODES: SelectOption[] = [
	{value: 'default', label: 'Default', description: 'Ask before write/execute operations'},
	{value: 'full_auto', label: 'Auto', description: 'Allow all tools automatically'},
	{value: 'plan', label: 'Plan Mode', description: 'Block all write operations'},
];

type SelectModalState = {
	title: string;
	options: SelectOption[];
	onSelect: (value: string) => void;
} | null;

const PERMISSION_PROMPT_OPTIONS: SelectOption[] = [
	{value: 'allow', label: 'Allow', description: 'Approve this tool execution'},
	{value: 'always', label: 'Always Allow', description: 'Always allow this tool without asking again'},
	{value: 'deny', label: 'Deny', description: 'Reject this tool execution'},
];

export function App({config}: {config: FrontendConfig}): React.JSX.Element {
	const initialTheme = String((config as Record<string, unknown>).theme ?? 'default');
	return (
		<ThemeProvider initialTheme={initialTheme}>
			<AppInner config={config} />
		</ThemeProvider>
	);
}

function AppInner({config}: {config: FrontendConfig}): React.JSX.Element {
	const {exit} = useApp();
	const {theme, setThemeName} = useTheme();
	const [input, setInput] = useState('');
	const [modalInput, setModalInput] = useState('');
	const [history, setHistory] = useState<string[]>([]);
	const [historyIndex, setHistoryIndex] = useState(-1);
	const [scriptIndex, setScriptIndex] = useState(0);
	const [pickerIndex, setPickerIndex] = useState(0);
	const [selectModal, setSelectModal] = useState<SelectModalState>(null);
	const [selectIndex, setSelectIndex] = useState(0);
	const [permissionIndex, setPermissionIndex] = useState(2);
	const [pendingPermissionAck, setPendingPermissionAck] = useState(false);
	const session = useBackendSession(config, () => exit());
	const isPermissionModal = session.modal?.kind === 'permission';
	const language = normalizeLanguage(session.status.ui_language);
	const permissionRequestId =
		isPermissionModal && typeof session.modal?.request_id === 'string' ? String(session.modal.request_id) : '';
	const localizedPermissionOptions = PERMISSION_PROMPT_OPTIONS.map((opt) => {
		if (opt.value === 'allow') {
			return {...opt, label: t(language, 'allow')};
		}
		if (opt.value === 'always') {
			return {...opt, label: t(language, 'alwaysAllow')};
		}
		return {...opt, label: t(language, 'deny')};
	});

	// Current tool name for spinner
	const currentToolName = useMemo(() => {
		for (let i = session.transcript.length - 1; i >= 0; i--) {
			const item = session.transcript[i];
			if (item.role === 'tool') {
				return item.tool_name ?? 'tool';
			}
			if (item.role === 'tool_result' || item.role === 'assistant') {
				break;
			}
		}
		return undefined;
	}, [session.transcript]);

	// Command hints
	const commandHints = useMemo(() => {
		if (!input.startsWith('/')) {
			return [] as string[];
		}
		const value = input.trimEnd();
		if (value === '') {
			return [] as string[];
		}
		const matches = session.commands.filter((cmd) => cmd.startsWith(value));
		if (value === '/') {
			const preferred = ['/stop', '/language'];
			const boosted = preferred.filter((cmd) => matches.includes(cmd));
			const rest = matches.filter((cmd) => !preferred.includes(cmd));
			return [...boosted, ...rest].slice(0, 20);
		}
		return matches.slice(0, 20);
	}, [session.commands, input]);

	const canShowPicker = input.startsWith('/') && commandHints.length > 0;
	const showPicker = canShowPicker && !session.busy && !session.modal && !selectModal;

	useEffect(() => {
		setPickerIndex(0);
	}, [canShowPicker, commandHints.length, input]);

	// Handle backend-initiated select requests (e.g. /resume session list)
	useEffect(() => {
		if (!session.selectRequest) {
			return;
		}
		const req = session.selectRequest;
		if (req.options.length === 0) {
			session.setSelectRequest(null);
			return;
		}
		setSelectIndex(0);
		setSelectModal({
			title: req.title,
			options: req.options.map((o) => ({value: o.value, label: o.label, description: o.description})),
			onSelect: (value) => {
				session.sendRequest({type: 'apply_select_command', command: req.command, value});
				session.setBusy(true);
				setSelectModal(null);
			},
		});
		session.setSelectRequest(null);
	}, [session.selectRequest]);

	useEffect(() => {
		if (!isPermissionModal) {
			setPendingPermissionAck(false);
			return;
		}
		setPermissionIndex(1);
		setPendingPermissionAck(false);
	}, [permissionRequestId, isPermissionModal]);

	// Intercept special commands that need interactive UI
	const handleCommand = (cmd: string): boolean => {
		const trimmed = cmd.trim();

		// /theme set <name> → switch theme locally
		const themeMatch = /^\/theme\s+set\s+(\S+)$/.exec(trimmed);
		if (themeMatch) {
			setThemeName(themeMatch[1]);
			return true;
		}

		// /permissions → show mode picker
		if (trimmed === '/permissions' || trimmed === '/permissions show') {
			const currentMode = String(session.status.permission_mode ?? 'default');
			const options = PERMISSION_MODES.map((opt) => ({
				...opt,
				active: opt.value === currentMode,
			}));
			const initialIndex = options.findIndex((o) => o.active);
			setSelectIndex(initialIndex >= 0 ? initialIndex : 0);
			setSelectModal({
				title: 'Permission Mode',
				options,
				onSelect: (value) => {
					session.sendRequest({type: 'submit_line', line: `/permissions set ${value}`});
					session.setBusy(true);
					setSelectModal(null);
				},
			});
			return true;
		}

		if (trimmed === '/language' || trimmed === '/language show') {
			const current = normalizeLanguage(session.status.ui_language);
			const options: SelectOption[] = [
				{value: 'set zh-CN', label: t(current, 'langZh'), description: '中文界面', active: current === 'zh-CN'},
				{value: 'set en', label: t(current, 'langEn'), description: 'English UI', active: current === 'en'},
			];
			const initialIndex = options.findIndex((o) => o.active);
			setSelectIndex(initialIndex >= 0 ? initialIndex : 0);
			setSelectModal({
				title: t(current, 'language'),
				options,
				onSelect: (value) => {
					session.sendRequest({type: 'submit_line', line: `/language ${value}`});
					session.setBusy(true);
					setSelectModal(null);
				},
			});
			return true;
		}

		// /plan → toggle plan mode
		if (trimmed === '/plan') {
			const currentMode = String(session.status.permission_mode ?? 'default');
			if (currentMode === 'plan') {
				session.sendRequest({type: 'submit_line', line: '/plan off'});
			} else {
				session.sendRequest({type: 'submit_line', line: '/plan on'});
			}
			session.setBusy(true);
			return true;
		}

		// /resume → request session list from backend (will trigger select_request)
		if (trimmed === '/resume') {
			session.sendRequest({type: 'list_sessions'});
			return true;
		}

		return false;
	};

	useInput((chunk, key) => {
		if ((key.backspace || key.delete) && input === '/') {
			setInput('');
			return;
		}

		// Ctrl+C → exit
		if (key.ctrl && chunk === 'c') {
			session.sendRequest({type: 'shutdown'});
			exit();
			return;
		}
		if (key.ctrl && chunk.toLowerCase() === 'x') {
			session.sendRequest({type: 'stop'});
			return;
		}

		// --- Select modal (permissions picker etc.) ---
		if (selectModal) {
			if (key.upArrow) {
				setSelectIndex((i) => Math.max(0, i - 1));
				return;
			}
			if (key.downArrow) {
				setSelectIndex((i) => Math.min(selectModal.options.length - 1, i + 1));
				return;
			}
			if (key.return) {
				const selected = selectModal.options[selectIndex];
				if (selected) {
					selectModal.onSelect(selected.value);
				}
				return;
			}
			if (key.escape) {
				setSelectModal(null);
				return;
			}
			// Number keys for quick selection
			const num = parseInt(chunk, 10);
			if (num >= 1 && num <= selectModal.options.length) {
				const selected = selectModal.options[num - 1];
				if (selected) {
					selectModal.onSelect(selected.value);
				}
				return;
			}
			return;
		}

		// --- Scripted raw return ---
		if (rawReturnSubmit && key.return) {
			if (session.modal?.kind === 'question') {
				session.sendRequest({
					type: 'question_response',
					request_id: session.modal.request_id,
					answer: modalInput,
				});
				session.setModal(null);
				setModalInput('');
				return;
			}
			if (!session.modal && !session.busy && input.trim()) {
				onSubmit(input);
				return;
			}
		}

		// --- Permission modal (MUST be before busy check — modal appears while busy) ---
		if (isPermissionModal) {
			if (pendingPermissionAck) {
				return;
			}
			if (key.upArrow || key.downArrow) {
				setPermissionIndex((i) => {
					if (key.upArrow) return i <= 0 ? 2 : i - 1;
					return i >= 2 ? 0 : i + 1;
				});
				return;
			}
			if (key.return || key.escape) {
				if (!permissionRequestId) {
					return;
				}
				const selected = key.escape ? 'deny' : localizedPermissionOptions[permissionIndex]?.value;
				const allowed = selected === 'allow' || selected === 'always';
				session.sendRequest({
					type: 'permission_response',
					request_id: permissionRequestId,
					allowed,
					always_allow: selected === 'always',
					tool_name: String(session.modal?.tool_name ?? ''),
				});
				setPendingPermissionAck(true);
				return;
			}
			return;
		}

		// --- Question modal (also appears while busy) ---
		if (session.modal?.kind === 'question') {
			return; // Let TextInput in ModalHost handle input
		}

		// --- Ignore input while busy ---
		if (session.busy) {
			return;
		}

		// --- Command picker ---
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
					setInput('');
					if (!handleCommand(selected)) {
						onSubmit(selected);
					}
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

		// --- History navigation ---
		if (!showPicker && key.upArrow) {
			const nextIndex = Math.min(history.length - 1, historyIndex + 1);
			if (nextIndex >= 0) {
				setHistoryIndex(nextIndex);
				setInput(history[history.length - 1 - nextIndex] ?? '');
			}
			return;
		}
		if (!showPicker && key.downArrow) {
			const nextIndex = Math.max(-1, historyIndex - 1);
			setHistoryIndex(nextIndex);
			setInput(nextIndex === -1 ? '' : (history[history.length - 1 - nextIndex] ?? ''));
			return;
		}

		// Note: normal Enter submission is handled by TextInput's onSubmit in
		// PromptInput.  Do NOT duplicate it here — that causes double requests.
	});

	const onSubmit = (value: string): void => {
		if (session.modal?.kind === 'question') {
			session.sendRequest({
				type: 'question_response',
				request_id: session.modal.request_id,
				answer: value,
			});
			session.setModal(null);
			setModalInput('');
			return;
		}
		if (value.trim() === '/stop') {
			session.sendRequest({type: 'stop'});
			setHistory((items) => [...items, value]);
			setHistoryIndex(-1);
			setInput('');
			return;
		}
		if (!value.trim() || session.busy || !session.ready) {
			return;
		}
		// Check if it's an interactive command
		if (handleCommand(value)) {
			setHistory((items) => [...items, value]);
			setHistoryIndex(-1);
			setInput('');
			return;
		}
		session.sendRequest({type: 'submit_line', line: value});
		setHistory((items) => [...items, value]);
		setHistoryIndex(-1);
		setInput('');
		session.setBusy(true);
	};

	// Scripted automation
	useEffect(() => {
		if (scriptIndex >= scriptedSteps.length) {
			return;
		}
		if (session.busy || session.modal || selectModal) {
			return;
		}
		const step = scriptedSteps[scriptIndex];
		const timer = setTimeout(() => {
			onSubmit(step);
			setScriptIndex((index) => index + 1);
		}, 200);
		return () => clearTimeout(timer);
	}, [scriptIndex, session.busy, session.modal, selectModal]);

	return (
		<Box flexDirection="column" paddingX={1} height="100%">
			{/* Conversation area */}
			<Box flexDirection="column" flexGrow={1}>
				<ConversationView
					items={session.transcript}
					assistantBuffer={session.assistantBuffer}
					showWelcome={session.ready}
					language={language}
				/>
			</Box>

			{/* Permission confirm modal */}
			{isPermissionModal ? (
				<SelectModal
					title={`Allow ${String(session.modal?.tool_name ?? 'tool')}?`}
					options={localizedPermissionOptions}
					selectedIndex={permissionIndex}
				/>
			) : null}

			{/* Backend modal (question, mcp auth) */}
			{session.modal && !isPermissionModal ? (
				<ModalHost
					modal={session.modal}
					modalInput={modalInput}
					setModalInput={setModalInput}
					onSubmit={onSubmit}
					language={language}
				/>
			) : null}

			{/* Frontend select modal (permissions picker, etc.) */}
			{selectModal ? (
				<SelectModal
					title={selectModal.title}
					options={selectModal.options}
					selectedIndex={selectIndex}
				/>
			) : null}

			{/* Command picker */}
			{showPicker ? (
				<CommandPicker hints={commandHints} selectedIndex={pickerIndex} />
			) : null}

			{/* Todo panel */}
			{session.ready && session.todoMarkdown ? (
				<TodoPanel markdown={session.todoMarkdown} />
			) : null}

			{/* Swarm panel */}
			{session.ready && (session.swarmTeammates.length > 0 || session.swarmNotifications.length > 0) ? (
				<SwarmPanel teammates={session.swarmTeammates} notifications={session.swarmNotifications} />
			) : null}

			{/* Status bar (only after backend is ready) */}
			{session.ready ? (
				<StatusBar status={session.status} tasks={session.tasks} activeToolName={session.busy ? currentToolName : undefined} />
			) : null}

			{/* Input — show loading indicator until backend is ready */}
			{!session.ready ? (
				<Box>
					<Text color={theme.colors.warning}>{t(language, 'connecting')}</Text>
				</Box>
			) : session.modal || selectModal || pendingPermissionAck ? null : (
				<PromptInput
					busy={session.busy}
					input={input}
					setInput={setInput}
					onSubmit={onSubmit}
					toolName={session.busy ? currentToolName : undefined}
					suppressSubmit={showPicker}
					language={language}
				/>
			)}

			{/* Keyboard hints (only after backend is ready) */}
			{session.ready && !session.modal && !session.busy && !selectModal && !pendingPermissionAck ? (
				<Box>
					<Text dimColor>
						<Text>enter</Text> {t(language, 'send')}
						<Text>{'  ·  '}</Text>
						<Text>/</Text> {t(language, 'commands')}
						<Text>{'  ·  '}</Text>
						<Text>{'↑↓'}</Text> {t(language, 'history')}
						<Text>{'  ·  '}</Text>
						<Text>ctrl+x</Text> /stop
						<Text>{'  ·  '}</Text>
						<Text>ctrl+c</Text> {t(language, 'exit')}
					</Text>
				</Box>
			) : null}
		</Box>
	);
}
