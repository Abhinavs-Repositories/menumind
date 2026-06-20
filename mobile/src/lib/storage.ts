// Per-restaurant conversation persistence (survives navigation & app restarts).
import AsyncStorage from '@react-native-async-storage/async-storage';

import type { ChatMessage } from './api';

const key = (restaurant: string) => `menumind:chat:${restaurant}`;

export async function loadConversation(restaurant: string): Promise<ChatMessage[]> {
  try {
    const raw = await AsyncStorage.getItem(key(restaurant));
    return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

export async function saveConversation(
  restaurant: string,
  messages: ChatMessage[],
): Promise<void> {
  try {
    // Never persist a half-streamed/pending bubble.
    const clean = messages
      .filter((m) => !m.pending)
      .map(({ id, role, text, sources }) => ({ id, role, text, sources }));
    await AsyncStorage.setItem(key(restaurant), JSON.stringify(clean));
  } catch {
    // best-effort; ignore storage failures
  }
}

export async function clearConversation(restaurant: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key(restaurant));
  } catch {
    // ignore
  }
}
