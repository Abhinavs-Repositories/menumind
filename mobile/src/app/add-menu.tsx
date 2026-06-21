import { useCallback, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';

import { getIngestStatus, uploadMenu, type PickedFile } from '@/lib/api';
import { AppText, Button, Screen, haptics } from '@/components/ui';
import { useTheme, type Theme } from '@/theme';

type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

export default function AddMenuScreen() {
  const router = useRouter();
  const t = useTheme();
  const styles = useMemo(() => makeStyles(t), [t]);
  const [name, setName] = useState('');
  const [file, setFile] = useState<PickedFile | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pick = useCallback(async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'image/*'],
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (result.canceled || !result.assets?.length) return;
    const a = result.assets[0];
    setFile({ uri: a.uri, name: a.name, mimeType: a.mimeType });
    setMessage(null);
    haptics.tap();
  }, []);

  const poll = useCallback((jobId: string) => {
    getIngestStatus(jobId)
      .then((s) => {
        if (s.status === 'done') {
          setPhase('done');
          setMessage(`Ingested ${s.chunks ?? 0} items from ${s.pages ?? 0} page(s).`);
          haptics.success();
        } else if (s.status === 'error') {
          setPhase('error');
          setMessage(s.error ?? 'Ingestion failed.');
          haptics.error();
        } else {
          pollRef.current = setTimeout(() => poll(jobId), 2000);
        }
      })
      .catch((e) => {
        setPhase('error');
        setMessage(e instanceof Error ? e.message : 'Status check failed');
        haptics.error();
      });
  }, []);

  const submit = useCallback(async () => {
    const restaurant = name.trim();
    if (!restaurant || !file || phase === 'uploading' || phase === 'processing') {
      return;
    }
    setPhase('uploading');
    setMessage(null);
    try {
      const jobId = await uploadMenu(restaurant, file);
      setPhase('processing');
      poll(jobId);
    } catch (e) {
      setPhase('error');
      setMessage(e instanceof Error ? e.message : 'Upload failed');
      haptics.error();
    }
  }, [name, file, phase, poll]);

  const busy = phase === 'uploading' || phase === 'processing';

  return (
    <Screen style={styles.body}>
      <AppText variant="label" style={styles.label}>
        Restaurant name
      </AppText>
      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder="e.g. Blue Tokai"
        placeholderTextColor={t.colors.placeholder}
        editable={!busy}
      />

      <AppText variant="label" style={styles.label}>
        Menu file (PDF or image)
      </AppText>
      <Pressable
        style={({ pressed }) => [
          styles.dropZone,
          file && styles.dropZoneActive,
          (busy || pressed) && styles.dim,
        ]}
        onPress={pick}
        disabled={busy}
      >
        <AppText style={styles.dropIcon}>{file ? '📄' : '⬆️'}</AppText>
        <AppText variant={file ? 'heading' : 'muted'} center numberOfLines={1}>
          {file ? file.name : 'Choose a file…'}
        </AppText>
        {!file && (
          <AppText variant="caption" center>
            PDF or image of the menu
          </AppText>
        )}
      </Pressable>

      {phase === 'done' ? (
        <View style={styles.resultOk}>
          <AppText variant="heading" color={t.colors.success}>
            ✅ {message}
          </AppText>
          <Button title="Back to menus" onPress={() => router.replace('/')} style={styles.cta} />
        </View>
      ) : (
        <Button
          title="Upload & ingest"
          loadingTitle={phase === 'uploading' ? 'Uploading…' : 'Reading menu…'}
          loading={busy}
          disabled={!name.trim() || !file}
          onPress={submit}
          style={styles.cta}
        />
      )}

      {phase === 'processing' && (
        <AppText variant="muted" style={styles.hint}>
          Parsing the menu with AI and embedding it — this can take up to a minute
          for multi-page PDFs.
        </AppText>
      )}
      {phase === 'error' && (
        <AppText variant="heading" color={t.colors.brand} style={styles.hint}>
          ⚠️ {message}
        </AppText>
      )}
    </Screen>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    body: { padding: 20, gap: 10 },
    label: { marginTop: 10 },
    input: {
      backgroundColor: t.colors.surface,
      borderRadius: t.radius.md,
      paddingHorizontal: 16,
      paddingVertical: 14,
      fontSize: t.fontSize.lg,
      color: t.colors.text,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.colors.border,
    },
    dropZone: {
      backgroundColor: t.colors.surface,
      borderRadius: t.radius.lg,
      paddingVertical: 28,
      paddingHorizontal: 16,
      alignItems: 'center',
      gap: 6,
      borderWidth: 1.5,
      borderStyle: 'dashed',
      borderColor: t.colors.border,
    },
    dropZoneActive: { borderColor: t.colors.brand, borderStyle: 'solid' },
    dropIcon: { fontSize: 28 },
    dim: { opacity: 0.6 },
    cta: { marginTop: 16 },
    resultOk: { gap: 4, marginTop: 12 },
    hint: { marginTop: 12, lineHeight: 19 },
  });
}
