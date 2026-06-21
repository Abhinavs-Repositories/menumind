import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
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
import Animated, { FadeInDown } from 'react-native-reanimated';
import { Stack, useLocalSearchParams } from 'expo-router';

import { streamChat, type ChatMessage, type HistoryTurn } from '@/lib/api';
import { Markdown, type MarkdownTheme } from '@/components/Markdown';
import { AppText, Caret, Pill, TypingDots, haptics } from '@/components/ui';
import { useTheme, type Theme } from '@/theme';
import {
  clearConversation,
  loadConversation,
  saveConversation,
} from '@/lib/storage';

const SUGGESTIONS = [
  'What are the vegetarian options?',
  'Show me the desserts',
  "What's the most popular dish?",
  'Any spicy dishes?',
];

export default function ChatScreen() {
  const { restaurant } = useLocalSearchParams<{ restaurant?: string }>();
  const menu = restaurant ?? null;
  const storeKey = menu ?? 'menu';
  const t = useTheme();

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

  const send = useCallback(
    async (override?: string) => {
      const question = (override ?? input).trim();
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

      // Coalesce streamed tokens to one state update per frame: tokens can
      // arrive far faster than 60fps, and a setState per token would re-render
      // the list on every token. Buffer in a ref, flush on rAF.
      let buffer = '';
      let scheduled = false;
      const flush = () => {
        scheduled = false;
        if (!buffer) return;
        const chunk = buffer;
        buffer = '';
        patchBot((m) => ({ ...m, text: m.text + chunk }));
      };

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(
          question,
          menu,
          {
            onSources: (sources) => patchBot((m) => ({ ...m, sources })),
            // Keep `pending` true through streaming so the caret blinks; cleared
            // on done / error / in finally.
            onToken: (token) => {
              buffer += token;
              if (!scheduled) {
                scheduled = true;
                requestAnimationFrame(flush);
              }
            },
            onDone: () => {
              flush();
              patchBot((m) => ({ ...m, pending: false }));
            },
            onError: (msg) =>
              patchBot((m) => ({ ...m, text: m.text || `⚠️ ${msg}`, pending: false })),
          },
          { history, signal: controller.signal },
        );
      } catch (e) {
        flush(); // commit any buffered tokens before falling back
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
        // Guarantee buffered text lands and the streaming caret stops, even if
        // the stream ended abnormally.
        flush();
        patchBot((m) => ({ ...m, pending: false }));
        persist();
      }
    },
    [input, busy, menu, messages, persist],
  );

  const styles = useMemo(() => makeStyles(t), [t]);

  const renderItem = useCallback(
    ({ item }: { item: ChatMessage }) => <Bubble msg={item} theme={t} />,
    [t],
  );

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
                <AppText variant="heading" color={t.colors.brand} style={styles.clearBtn}>
                  Clear
                </AppText>
              </Pressable>
            ) : null,
        }}
      />

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.messages}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        keyboardDismissMode="interactive"
        maxToRenderPerBatch={8}
        windowSize={11}
        initialNumToRender={10}
        ListEmptyComponent={
          <View style={styles.emptyWrap}>
            <AppText variant="muted" center style={styles.empty}>
              Ask anything about {menu ?? 'the menu'} — dishes, prices,
              ingredients or dietary options. Follow-ups keep context.
            </AppText>
            <View style={styles.suggestions}>
              {SUGGESTIONS.map((q) => (
                <Pill
                  key={q}
                  label={q}
                  tone="brand"
                  onPress={() => {
                    haptics.tap();
                    send(q);
                  }}
                />
              ))}
            </View>
          </View>
        }
        renderItem={renderItem}
      />

      <View style={[styles.inputBar, { paddingBottom: Math.max(insets.bottom, 10) }]}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder={`Ask about ${menu ?? 'the menu'}…`}
          placeholderTextColor={t.colors.placeholder}
          editable={!busy}
          onSubmitEditing={() => send()}
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
            onPress={() => send()}
            disabled={!input.trim()}
          >
            <Text style={styles.sendText}>Send</Text>
          </Pressable>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const Bubble = memo(function Bubble({ msg, theme: t }: { msg: ChatMessage; theme: Theme }) {
  const isUser = msg.role === 'user';
  const styles = useMemo(() => makeStyles(t), [t]);
  const md = useMemo<MarkdownTheme>(
    () => ({
      color: t.colors.text,
      bold: t.colors.text,
      accent: t.colors.brand,
      codeBg: t.colors.surfaceAlt,
      rule: t.colors.border,
    }),
    [t],
  );

  return (
    <Animated.View
      entering={FadeInDown.duration(220)}
      style={[styles.bubble, isUser ? styles.userBubble : styles.botBubble]}
    >
      {msg.pending && !msg.text ? (
        <TypingDots />
      ) : isUser ? (
        <Text style={[styles.bubbleText, styles.userText]}>{msg.text}</Text>
      ) : (
        <Markdown
          content={msg.text}
          baseStyle={styles.bubbleText}
          theme={md}
          trailing={msg.pending ? <Caret /> : undefined}
        />
      )}
      {!!msg.sources?.length && (
        <View style={styles.sourcesRow}>
          {msg.sources.map((s, i) => (
            <Pill key={`${s.page}-${i}`} label={`p.${s.page}`} tone="brand" />
          ))}
        </View>
      )}
    </Animated.View>
  );
});

function makeStyles(t: Theme) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: t.colors.bg },
    messages: { padding: 16, gap: 10, flexGrow: 1 },
    emptyWrap: { flex: 1, justifyContent: 'center', paddingHorizontal: 8, marginTop: 40 },
    empty: { paddingHorizontal: 16, lineHeight: 22 },
    suggestions: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      justifyContent: 'center',
      gap: 8,
      marginTop: 20,
      paddingHorizontal: 16,
    },
    bubble: {
      maxWidth: '85%',
      borderRadius: 18,
      paddingVertical: 10,
      paddingHorizontal: 14,
    },
    userBubble: {
      alignSelf: 'flex-end',
      backgroundColor: t.colors.brand,
      borderBottomRightRadius: 6,
    },
    botBubble: {
      alignSelf: 'flex-start',
      backgroundColor: t.colors.surface,
      borderBottomLeftRadius: 6,
      borderWidth: t.mode === 'dark' ? StyleSheet.hairlineWidth : 0,
      borderColor: t.colors.border,
      ...t.shadow.card,
    },
    bubbleText: {
      fontFamily: t.fonts.body,
      fontSize: t.fontSize.md,
      color: t.colors.text,
      lineHeight: 21,
    },
    userText: { color: t.colors.onBrand },
    sourcesRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 },
    clearBtn: { fontSize: 15 },
    inputBar: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      gap: 8,
      paddingHorizontal: 10,
      paddingTop: 10,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.colors.border,
      backgroundColor: t.colors.surface,
    },
    input: {
      flex: 1,
      maxHeight: 120,
      backgroundColor: t.colors.surfaceAlt,
      borderRadius: 20,
      paddingHorizontal: 16,
      paddingVertical: 10,
      fontSize: t.fontSize.md,
      color: t.colors.text,
    },
    sendBtn: {
      backgroundColor: t.colors.brand,
      borderRadius: 20,
      paddingHorizontal: 20,
      height: 42,
      justifyContent: 'center',
    },
    sendBtnOff: { backgroundColor: t.colors.brandSoft },
    stopBtn: { backgroundColor: t.colors.neutral },
    sendText: { color: t.colors.onBrand, fontWeight: '700', fontSize: t.fontSize.md },
  });
}
