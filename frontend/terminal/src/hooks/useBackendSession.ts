import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {spawn, type ChildProcessWithoutNullStreams} from 'node:child_process';
import readline from 'node:readline';

import type {
	BackendEvent,
	BridgeSessionSnapshot,
	FrontendConfig,
	McpServerSnapshot,
	SelectRequestPayload,
	SwarmNotificationSnapshot,
	SwarmTeammateSnapshot,
	TaskSnapshot,
	TodoItemSnapshot,
	TranscriptItem,
} from '../types.js';

const PROTOCOL_PREFIX = 'OHJSON:';
const ASSISTANT_DELTA_FLUSH_MS = 33;
const ASSISTANT_DELTA_FLUSH_CHARS = 256;

export function useBackendSession(config: FrontendConfig, onExit: (code?: number | null) => void) {
	const [staticItems, setStaticItems] = useState<TranscriptItem[]>([]);
	const [clearCount, setClearCount] = useState(0);
	const pushStatic = useCallback((item: TranscriptItem): void => {
		setStaticItems((prev) => [...prev, item]);
	}, []);
	const [assistantBuffer, setAssistantBuffer] = useState('');
	const [status, setStatus] = useState<Record<string, unknown>>({});
	const [tasks, setTasks] = useState<TaskSnapshot[]>([]);
	const [commands, setCommands] = useState<string[]>([]);
	const [mcpServers, setMcpServers] = useState<McpServerSnapshot[]>([]);
	const [bridgeSessions, setBridgeSessions] = useState<BridgeSessionSnapshot[]>([]);
	const [modal, setModal] = useState<Record<string, unknown> | null>(null);
	const [selectRequest, setSelectRequest] = useState<SelectRequestPayload | null>(null);
	const [busy, setBusy] = useState(false);
	const [ready, setReady] = useState(false);
	const [todoItems, setTodoItems] = useState<TodoItemSnapshot[]>([]);
	const [swarmTeammates, setSwarmTeammates] = useState<SwarmTeammateSnapshot[]>([]);
	const [swarmNotifications, setSwarmNotifications] = useState<SwarmNotificationSnapshot[]>([]);
	const childRef = useRef<ChildProcessWithoutNullStreams | null>(null);
	const sentInitialPrompt = useRef(false);

	// Streaming deltas can arrive one token at a time; updating Ink state for each
	// delta causes heavy re-rendering/flicker. Buffer and flush at ~30fps.
	const assistantBufferRef = useRef('');
	const pendingAssistantDeltaRef = useRef('');
	const assistantFlushTimerRef = useRef<NodeJS.Timeout | null>(null);

	const flushAssistantDelta = (): void => {
		const pending = pendingAssistantDeltaRef.current;
		if (!pending) {
			return;
		}
		pendingAssistantDeltaRef.current = '';
		assistantBufferRef.current += pending;
		setAssistantBuffer(assistantBufferRef.current);
	};

	const clearAssistantDelta = (): void => {
		pendingAssistantDeltaRef.current = '';
		assistantBufferRef.current = '';
		if (assistantFlushTimerRef.current) {
			clearTimeout(assistantFlushTimerRef.current);
			assistantFlushTimerRef.current = null;
		}
		setAssistantBuffer('');
	};

	const sendRequest = (payload: Record<string, unknown>): void => {
		const child = childRef.current;
		if (!child || child.stdin.destroyed) {
			return;
		}
		child.stdin.write(JSON.stringify(payload) + '\n');
	};

	useEffect(() => {
		const [command, ...args] = config.backend_command;
		const child = spawn(command, args, {
			stdio: ['pipe', 'pipe', 'inherit'],
			env: process.env,
			detached: true,
			windowsHide: true,
		});
		childRef.current = child;

		const reader = readline.createInterface({input: child.stdout});
		reader.on('line', (line) => {
			if (!line.startsWith(PROTOCOL_PREFIX)) {
				pushStatic({role: 'log', text: line});
				return;
			}
			const event = JSON.parse(line.slice(PROTOCOL_PREFIX.length)) as BackendEvent;
			handleEvent(event);
		});

		child.on('exit', (code) => {
			pushStatic({role: 'system', text: `backend exited with code ${code ?? 0}`});
			process.exitCode = code ?? 0;
			onExit(code);
		});

		// Ensure child processes are killed on parent exit (prevents stale processes)
		const killChild = (): void => {
			if (!child.killed) {
				// Kill process group to ensure Python backend and its children all die
				try {
					if (child.pid) {
						process.kill(-child.pid, 'SIGTERM');
					}
				} catch {
					child.kill('SIGTERM');
				}
			}
			if (assistantFlushTimerRef.current) {
				clearTimeout(assistantFlushTimerRef.current);
				assistantFlushTimerRef.current = null;
			}
		};
		process.on('exit', killChild);
		process.on('SIGINT', killChild);
		process.on('SIGTERM', killChild);

		return () => {
			reader.close();
			killChild();
			process.removeListener('exit', killChild);
			process.removeListener('SIGINT', killChild);
			process.removeListener('SIGTERM', killChild);
		};
	}, []);

	const handleEvent = (event: BackendEvent): void => {
		if (event.type === 'ready') {
			setReady(true);
			setStatus(event.state ?? {});
			setTasks(event.tasks ?? []);
			setCommands(event.commands ?? []);
			setMcpServers(event.mcp_servers ?? []);
			setBridgeSessions(event.bridge_sessions ?? []);
			if (config.initial_prompt && !sentInitialPrompt.current) {
				sentInitialPrompt.current = true;
				sendRequest({type: 'submit_line', line: config.initial_prompt});
				setBusy(true);
			}
			return;
		}
		if (event.type === 'state_snapshot') {
			setStatus(event.state ?? {});
			setMcpServers(event.mcp_servers ?? []);
			setBridgeSessions(event.bridge_sessions ?? []);
			return;
		}
		if (event.type === 'tasks_snapshot') {
			setTasks(event.tasks ?? []);
			return;
		}
		if (event.type === 'transcript_item' && event.item) {
			pushStatic(event.item as TranscriptItem);
			return;
		}
		if (event.type === 'assistant_delta') {
			const delta = event.message ?? '';
			if (!delta) {
				return;
			}
			pendingAssistantDeltaRef.current += delta;
			if (pendingAssistantDeltaRef.current.length >= ASSISTANT_DELTA_FLUSH_CHARS) {
				flushAssistantDelta();
				return;
			}
			if (!assistantFlushTimerRef.current) {
				assistantFlushTimerRef.current = setTimeout(() => {
					assistantFlushTimerRef.current = null;
					flushAssistantDelta();
				}, ASSISTANT_DELTA_FLUSH_MS);
			}
			return;
		}
		if (event.type === 'assistant_complete') {
			if (assistantFlushTimerRef.current) {
				clearTimeout(assistantFlushTimerRef.current);
				assistantFlushTimerRef.current = null;
			}
			flushAssistantDelta();
			const text = event.message ?? assistantBufferRef.current;
			pushStatic({role: 'assistant', text});
			clearAssistantDelta();
			return;
		}
		if (event.type === 'line_complete') {
			// If the line ended without an assistant_complete (e.g. errors), make sure we
			// don't leave stale streaming text on screen.
			clearAssistantDelta();
			setBusy(false);
			return;
		}
		if ((event.type === 'tool_started' || event.type === 'tool_completed') && event.item) {
			if (event.type === 'tool_started') {
				setBusy(true);
			}
			const enrichedItem: TranscriptItem = {
				...event.item,
				tool_name: event.item.tool_name ?? event.tool_name ?? undefined,
				tool_input: event.item.tool_input ?? undefined,
				is_error: event.item.is_error ?? event.is_error ?? undefined,
			};
			pushStatic(enrichedItem);
			return;
		}
		if (event.type === 'clear_transcript') {
			setStaticItems([]);
			setClearCount((c) => c + 1);
			clearAssistantDelta();
			return;
		}
		if (event.type === 'select_request') {
			const m = event.modal ?? {};
			setSelectRequest({
				title: String(m.title ?? 'Select'),
				command: String(m.command ?? ''),
				options: event.select_options ?? [],
			});
			return;
		}
		if (event.type === 'modal_request') {
			setModal(event.modal ?? null);
			return;
		}
		if (event.type === 'error') {
			if ((event.message ?? '').includes('No active task to stop')) {
				pushStatic({role: 'system', text: event.message ?? ''});
				return;
			}
			pushStatic({role: 'system', text: `error: ${event.message ?? 'unknown error'}`});
			clearAssistantDelta();
			setBusy(false);
			return;
		}
		if (event.type === 'todo_update') {
			if (event.todo_items != null) {
				setTodoItems(event.todo_items);
			}
			return;
		}
		if (event.type === 'swarm_status') {
			if (event.swarm_teammates != null) {
				setSwarmTeammates(event.swarm_teammates);
			}
			if (event.swarm_notifications != null) {
				setSwarmNotifications((prev) => [...prev, ...event.swarm_notifications!].slice(-20));
			}
			return;
		}
		if (event.type === 'plan_mode_change') {
			if (event.plan_mode != null) {
				setStatus((s) => ({...s, permission_mode: event.plan_mode}));
			}
			return;
		}
		if (event.type === 'shutdown') {
			onExit(0);
		}
	};

	return useMemo(
		() => ({
			staticItems,
			assistantBuffer,
			clearCount,
			status,
			tasks,
			commands,
			mcpServers,
			bridgeSessions,
			modal,
			selectRequest,
			busy,
			ready,
			todoItems,
			swarmTeammates,
			swarmNotifications,
			setModal,
			setSelectRequest,
			setBusy,
			sendRequest,
		}),
		[assistantBuffer, bridgeSessions, busy, clearCount, commands, mcpServers, modal, ready, selectRequest, staticItems, status, swarmNotifications, swarmTeammates, tasks, todoItems]
	);
}
