import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { KeyboardAvoidingView } from 'react-native-keyboard-controller';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Stack, useLocalSearchParams } from 'expo-router';

import { streamChat, type ChatMessage, type HistoryTurn } from '@/lib/api';
import {
  clearConversation,
  loadConversation,
  saveConversation,
} from '@/lib/storage';

export default function ChatScreen() {
  const { restaurant } = useLocalSearchParams<{ restaurant?: string }>();
  const menu = restaurant ?? null;
  const storeKey = menu ?? 'menu';

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const listRef = useRef<FlatList<ChatMessage>>(null);
  const abortRef = useRef<AbortController | null>(null);
  const insets = useSafeAreaInsets();
  // Offset for the stack header so the input lands just above the keyboard.
  const headerOffset = (Platform.OS === 'ios' ? 44 : 56) + insets.top;

  // Restore any saved conversation for this menu.
  useEffect(() => {
    let active = true;
    loadConversation(storeKey).then((saved) => {
      if (active && saved.length) setMessages(saved);
    });
    return () => {
      active = false;
    };
  }, [storeKey]);

  const persist = useCallback(() => {
    setMessages((prev) => {
      saveConversation(storeKey, prev);
      return prev;
    });
  }, [storeKey]);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    clearConversation(storeKey);
  }, [storeKey]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const send = useCallback(async () => {
    const question = input.trim();
    if (!question || busy) return;

    setInput('');
    setBusy(true);

    // Build multi-turn context from the conversation so far.
    const history: HistoryTurn[] = messages
      .filter((m) => !m.pending && m.text)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.text }));

    const botId = `a${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: `u${Date.now()}`, role: 'user', text: question },
      { id: botId, role: 'assistant', text: '', pending: true },
    ]);

    const patchBot = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => prev.map((m) => (m.id === botId ? fn(m) : m)));

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        question,
        menu,
        {
          onSources: (sources) => patchBot((m) => ({ ...m, sources })),
          onToken: (token) =>
            patchBot((m) => ({ ...m, text: m.text + token, pending: false })),
          onDone: () => patchBot((m) => ({ ...m, pending: false })),
          onError: (msg) =>
            patchBot((m) => ({ ...m, text: m.text || `⚠️ ${msg}`, pending: false })),
        },
        { history, signal: controller.signal },
      );
    } catch (e) {
      const aborted = controller.signal.aborted;
      patchBot((m) => ({
        ...m,
        text: aborted
          ? m.text || '⏹ Stopped.'
          : m.text || `⚠️ ${e instanceof Error ? e.message : 'Request failed'}`,
        pending: false,
      }));
    } finally {
      abortRef.current = null;
      setBusy(false);
      persist();
    }
  }, [input, busy, menu, messages, persist]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior="padding"
      keyboardVerticalOffset={headerOffset}
    >
      <Stack.Screen
        options={{
          title: menu ?? 'Chat',
          headerRight: () =>
            messages.length > 0 ? (
              <Pressable onPress={clear} hitSlop={8}>
                <Text style={styles.clearBtn}>Clear</Text>
              </Pressable>
            ) : null,
        }}
      />

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.messages}
        onContentSizeChange={() =>
          listRef.current?.scrollToEnd({ animated: true })
        }
        ListEmptyComponent={
          <Text style={styles.empty}>
            Ask anything about the {menu ?? 'menu'} — dishes, prices,
            ingredients, or dietary options. Follow-up questions keep context.
          </Text>
        }
        renderItem={({ item }) => <Bubble msg={item} />}
      />

      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder={`Ask about ${menu ?? 'the menu'}…`}
          placeholderTextColor="#a89e98"
          editable={!busy}
          onSubmitEditing={send}
          returnKeyType="send"
          multiline
        />
        {busy ? (
          <Pressable style={[styles.sendBtn, styles.stopBtn]} onPress={stop}>
            <Text style={styles.sendText}>Stop</Text>
          </Pressable>
        ) : (
          <Pressable
            style={[styles.sendBtn, !input.trim() && styles.sendBtnOff]}
            onPress={send}
            disabled={!input.trim()}
          >
            <Text style={styles.sendText}>Send</Text>
          </Pressable>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

function Bubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <View style={[styles.bubble, isUser ? styles.userBubble : styles.botBubble]}>
      {msg.pending && !msg.text ? (
        <ActivityIndicator color="#c0392b" />
      ) : (
        <Text style={[styles.bubbleText, isUser && styles.userText]}>
          {msg.text}
        </Text>
      )}
      {!!msg.sources?.length && (
        <Text style={styles.sources}>
          Sources: {msg.sources.map((s) => `p.${s.page}`).join(', ')}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#faf7f5' },
  messages: { padding: 16, gap: 10, flexGrow: 1 },
  empty: {
    textAlign: 'center',
    color: '#7a6f6a',
    fontSize: 15,
    marginTop: 40,
    paddingHorizontal: 24,
    lineHeight: 22,
  },
  bubble: {
    maxWidth: '85%',
    borderRadius: 16,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  userBubble: { alignSelf: 'flex-end', backgroundColor: '#c0392b' },
  botBubble: {
    alignSelf: 'flex-start',
    backgroundColor: '#fff',
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  bubbleText: { fontSize: 15, color: '#2c2420', lineHeight: 21 },
  userText: { color: '#fff' },
  sources: { fontSize: 11, color: '#9b908a', marginTop: 6 },
  clearBtn: { color: '#c0392b', fontWeight: '600', fontSize: 15 },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    padding: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#e4dcd7',
    backgroundColor: '#fff',
  },
  input: {
    flex: 1,
    maxHeight: 120,
    backgroundColor: '#f1eae7',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    color: '#2c2420',
  },
  sendBtn: {
    backgroundColor: '#c0392b',
    borderRadius: 20,
    paddingHorizontal: 20,
    height: 42,
    justifyContent: 'center',
  },
  sendBtnOff: { backgroundColor: '#d8b3ad' },
  stopBtn: { backgroundColor: '#5a5048' },
  sendText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
