// Minimal, streaming-friendly Markdown renderer for chat answers.
//
// The RAG backend (Groq) replies in Markdown: **bold**, *italic*, `code`,
// bullet / numbered lists, headings and the odd horizontal rule. The model
// streams token by token, so this renderer is a pure function of the current
// text — partial markup (an unclosed `**`) simply renders literally until the
// closing marker arrives, then re-renders formatted on the next token.
//
// A custom renderer (vs. a library) keeps us compatible with the bleeding-edge
// Expo SDK 56 / RN 0.85 / React 19 stack and scoped to exactly what the model
// emits. Parsing is two-pass (text -> block descriptors -> elements) so a
// `trailing` node (e.g. a streaming caret) can be appended inline to the end.
import { memo, type ReactNode } from 'react';
import { StyleSheet, Text, View, type TextStyle } from 'react-native';

export type MarkdownTheme = {
  /** Default body text colour. */
  color: string;
  /** Colour for **bold** / headings. */
  bold: string;
  /** Accent for bullets, list numbers, inline code and rules. */
  accent: string;
  /** Background behind inline `code`. */
  codeBg: string;
  /** Colour of a horizontal rule / divider. */
  rule: string;
};

type Props = {
  content: string;
  /** Base text style (font size, line height, default colour). */
  baseStyle?: TextStyle | TextStyle[];
  theme: MarkdownTheme;
  /** Node appended inline to the final text block (e.g. a streaming caret). */
  trailing?: ReactNode;
};

// ---------------------------------------------------------------------------
// Inline parsing: **bold**, __bold__, *italic*, _italic_, `code`
// ---------------------------------------------------------------------------
type Span = { text: string; bold?: boolean; italic?: boolean; code?: boolean };

// Bold (** / __) is listed first so it wins over italic at the same position.
const INLINE = /(\*\*|__)([\s\S]+?)\1|(\*|_)([\s\S]+?)\3|`([^`]+?)`/g;

function parseInline(text: string): Span[] {
  const spans: Span[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text))) {
    if (m.index > last) spans.push({ text: text.slice(last, m.index) });
    if (m[1] !== undefined) spans.push({ text: m[2], bold: true });
    else if (m[3] !== undefined) spans.push({ text: m[4], italic: true });
    else spans.push({ text: m[5], code: true });
    last = INLINE.lastIndex;
  }
  if (last < text.length) spans.push({ text: text.slice(last) });
  return spans;
}

function Inline({
  text,
  theme,
  trailing,
}: {
  text: string;
  theme: MarkdownTheme;
  trailing?: ReactNode;
}): ReactNode {
  const nodes = parseInline(text).map((s, i) => {
    if (!s.text) return null;
    return (
      <Text
        key={i}
        style={[
          s.bold && { fontWeight: '700', color: theme.bold },
          s.italic && styles.italic,
          s.code && [styles.code, { backgroundColor: theme.codeBg, color: theme.accent }],
        ]}
      >
        {s.text}
      </Text>
    );
  });
  return (
    <>
      {nodes}
      {trailing ? <Text> {trailing}</Text> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Block parsing
// ---------------------------------------------------------------------------
type Block =
  | { kind: 'p'; text: string; mt: number }
  | { kind: 'h'; level: number; text: string; mt: number }
  | { kind: 'li'; marker: string; text: string; mt: number }
  | { kind: 'rule'; mt: number };

const HEADING = /^(#{1,6})\s+(.*)$/;
const BULLET = /^[-*+]\s+(.*)$/;
const NUMBERED = /^(\d+)\.\s+(.*)$/;
const RULE = /^(-{3,}|\*{3,}|_{3,})$/;

function parseBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let first = true;
  let sawBlank = false;

  // Top margin: 0 for the first block, a paragraph gap after a blank line,
  // a tight gap between adjacent lines (e.g. consecutive list items).
  const mt = () => (first ? 0 : sawBlank ? 10 : 4);

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      sawBlank = true;
      continue;
    }

    const heading = HEADING.exec(line);
    const bullet = BULLET.exec(line);
    const numbered = NUMBERED.exec(line);

    if (RULE.test(line)) {
      blocks.push({ kind: 'rule', mt: mt() });
    } else if (heading) {
      blocks.push({
        kind: 'h',
        level: heading[1].length,
        text: heading[2],
        mt: first ? 0 : 12,
      });
    } else if (bullet || numbered) {
      blocks.push({
        kind: 'li',
        marker: bullet ? '•' : `${numbered![1]}.`,
        text: bullet ? bullet[1] : numbered![2],
        mt: mt(),
      });
    } else {
      blocks.push({ kind: 'p', text: line, mt: mt() });
    }
    first = false;
    sawBlank = false;
  }
  return blocks;
}

function MarkdownBase({ content, baseStyle, theme, trailing }: Props) {
  const blocks = parseBlocks(content);
  const lastIdx = blocks.length - 1;

  return (
    <View>
      {blocks.map((b, i) => {
        const tail = i === lastIdx ? trailing : undefined;

        if (b.kind === 'rule') {
          return (
            <View
              key={i}
              style={[styles.rule, { backgroundColor: theme.rule, marginTop: b.mt }]}
            />
          );
        }
        if (b.kind === 'h') {
          return (
            <Text
              key={i}
              style={[
                baseStyle,
                styles.heading,
                b.level <= 2 ? styles.h1 : styles.h3,
                { color: theme.bold, marginTop: b.mt },
              ]}
            >
              <Inline text={b.text} theme={theme} trailing={tail} />
            </Text>
          );
        }
        if (b.kind === 'li') {
          return (
            <View key={i} style={[styles.listRow, { marginTop: b.mt }]}>
              <Text style={[baseStyle, styles.marker, { color: theme.accent }]}>
                {b.marker}
              </Text>
              <Text style={[baseStyle, styles.listText]}>
                <Inline text={b.text} theme={theme} trailing={tail} />
              </Text>
            </View>
          );
        }
        return (
          <Text key={i} style={[baseStyle, { marginTop: b.mt }]}>
            <Inline text={b.text} theme={theme} trailing={tail} />
          </Text>
        );
      })}
      {/* If the model has produced nothing renderable yet, still allow a caret. */}
      {blocks.length === 0 && trailing ? <Text style={baseStyle}>{trailing}</Text> : null}
    </View>
  );
}

export const Markdown = memo(MarkdownBase);

const styles = StyleSheet.create({
  italic: { fontStyle: 'italic' },
  code: {
    fontFamily: 'monospace',
    fontSize: 13.5,
    borderRadius: 4,
    paddingHorizontal: 4,
  },
  heading: { fontWeight: '700' },
  h1: { fontSize: 17 },
  h3: { fontSize: 15.5 },
  listRow: { flexDirection: 'row', alignItems: 'flex-start' },
  marker: { width: 22, fontWeight: '700' },
  listText: { flex: 1 },
  rule: { height: StyleSheet.hairlineWidth, marginVertical: 4 },
});
