// MenuMind API client. Uses expo/fetch so the response body is a real
// ReadableStream on iOS/Android/web, letting us stream the answer token by token.
import { fetch } from 'expo/fetch';
import { Platform } from 'react-native';

import { API_URL } from '@/config';

export type Source = { page: number; score: number; preview: string };
export type DoneMeta = { retrieval_count: number; time_s: number };
export type Role = 'user' | 'assistant';

/** A chat bubble in the UI (persisted per restaurant). */
export type ChatMessage = {
  id: string;
  role: Role;
  text: string;
  sources?: Source[];
  pending?: boolean;
};

/** A prior turn sent to the backend for multi-turn follow-ups. */
export type HistoryTurn = { role: Role; content: string };

export type ChatHandlers = {
  onSources?: (sources: Source[]) => void;
  onToken?: (token: string) => void;
  onDone?: (meta: DoneMeta) => void;
  onError?: (message: string) => void;
};

/** Fetch the list of restaurants/menus available to chat with. */
export async function fetchMenus(): Promise<string[]> {
  const res = await fetch(`${API_URL}/menus`);
  if (!res.ok) {
    throw new Error(`Could not load menus (HTTP ${res.status})`);
  }
  return (await res.json()) as string[];
}

const INGEST_KEY = process.env.EXPO_PUBLIC_INGEST_KEY;

export type IngestStatus = {
  status: 'processing' | 'done' | 'error';
  restaurant?: string;
  pages?: number;
  chunks?: number;
  error?: string;
};

export type PickedFile = { uri: string; name: string; mimeType?: string };

/** Upload a menu file for ingestion; returns a job id to poll. */
export async function uploadMenu(
  restaurant: string,
  file: PickedFile,
): Promise<string> {
  const form = new FormData();
  form.append('restaurant', restaurant);

  if (Platform.OS === 'web') {
    // Browsers need a real Blob/File, not a { uri } object.
    const blob = await (await globalThis.fetch(file.uri)).blob();
    form.append('file', blob, file.name);
  } else {
    // React Native's XHR understands the { uri, name, type } file part.
    form.append('file', {
      uri: file.uri,
      name: file.name,
      type: file.mimeType ?? 'application/octet-stream',
    } as unknown as Blob);
  }

  // Send via XMLHttpRequest: in Expo SDK 56 the global fetch is expo/fetch,
  // which rejects the { uri } file part with "Unsupported FormDataPart
  // implementation". XHR handles multipart file uploads on every platform.
  const data = await new Promise<{ job_id: string }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_URL}/ingest`);
    if (INGEST_KEY) xhr.setRequestHeader('X-Ingest-Key', INGEST_KEY);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error('Unexpected response from server'));
        }
      } else {
        reject(new Error(`Upload failed (HTTP ${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.send(form);
  });

  return data.job_id;
}

/** Poll the status of an ingestion job. */
export async function getIngestStatus(jobId: string): Promise<IngestStatus> {
  const res = await globalThis.fetch(`${API_URL}/ingest/${jobId}`);
  if (!res.ok) {
    throw new Error(`Status check failed (HTTP ${res.status})`);
  }
  return (await res.json()) as IngestStatus;
}

/**
 * Stream a RAG answer for `question` scoped to one `restaurant`.
 * Resolves when the stream ends; invokes handlers as events arrive.
 */
export async function streamChat(
  question: string,
  restaurant: string | null,
  handlers: ChatHandlers,
  options: { history?: HistoryTurn[]; signal?: AbortSignal } = {},
): Promise<void> {
  const res = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ question, restaurant, history: options.history }),
    signal: options.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed (HTTP ${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let sep: number;
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      dispatchFrame(frame, handlers);
    }
  }
  if (buffer.trim()) dispatchFrame(buffer, handlers);
}

function dispatchFrame(frame: string, h: ChatHandlers): void {
  let event = 'message';
  const dataLines: string[] = [];
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;

  const raw = dataLines.join('\n');
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    data = raw;
  }

  switch (event) {
    case 'sources':
      h.onSources?.(data as Source[]);
      break;
    case 'token':
      h.onToken?.(typeof data === 'string' ? data : String(data));
      break;
    case 'done':
      h.onDone?.(data as DoneMeta);
      break;
    case 'error':
      h.onError?.(typeof data === 'string' ? data : JSON.stringify(data));
      break;
  }
}
