import { useCallback, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Stack, useLocalSearchParams } from 'expo-router';

import { streamChat, type Source } from '@/lib/api';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  sources?: Source[];
  pending?: boolean;
};

export default function ChatScreen() {
  const { restaurant } = useLocalSearchParams<{ restaurant?: string }>();
  const menu = restaurant ?? null;

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const listRef = useRef<FlatList<Message>>(null);

  const send = useCallback(async () => {
    const question = input.trim();
    if (!question || busy) return;

    setInput('');
    setBusy(true);

    const botId = `a${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: `u${Date.now()}`, role: 'user', text: question },
      { id: botId, role: 'assistant', text: '', pending: true },
    ]);

    const patchBot = (fn: (m: Message) => Message) =>
      setMessages((prev) => prev.map((m) => (m.id === botId ? fn(m) : m)));

    try {
      await streamChat(question, menu, {
        onSources: (sources) => patchBot((m) => ({ ...m, sources })),
        onToken: (token) =>
          patchBot((m) => ({ ...m, text: m.text + token, pending: false })),
        onDone: () => patchBot((m) => ({ ...m, pending: false })),
        onError: (msg) =>
          patchBot((m) => ({ ...m, text: m.text || `⚠️ ${msg}`, pending: false })),
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Request failed';
      patchBot((m) => ({ ...m, text: m.text || `⚠️ ${msg}`, pending: false }));
    } finally {
      setBusy(false);
    }
  }, [input, busy, menu]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      <Stack.Screen options={{ title: menu ?? 'Chat' }} />

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
            ingredients, or dietary options.
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
        <Pressable
          style={[styles.sendBtn, (busy || !input.trim()) && styles.sendBtnOff]}
          onPress={send}
          disabled={busy || !input.trim()}
        >
          <Text style={styles.sendText}>{busy ? '…' : 'Send'}</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

function Bubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  return (
    <View
      style={[styles.bubble, isUser ? styles.userBubble : styles.botBubble]}
    >
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
  sendText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
