/**
 * CaptureScreen — Voice recording, photo capture, and text notes
 *
 * Three input modes with a large central action button.
 * Voice: hold-to-record with Whisper STT transcription.
 * Photo: opens camera, attaches to memory.
 * Text: quick note input field.
 */
import React, {useRef, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
  Animated,
  Keyboard,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import AudioRecorderPlayer from 'react-native-audio-recorder-player';
import {launchCamera, CameraOptions} from 'react-native-image-picker';
import MiraApi from '../services/MiraApi';
import {COLORS, SPACING, FONT_SIZES} from '../utils/theme';

type CaptureMode = 'voice' | 'photo' | 'text';

const audioRecorder = new AudioRecorderPlayer();

const CaptureScreen: React.FC = () => {
  const [mode, setMode] = useState<CaptureMode>('voice');
  const [recording, setRecording] = useState(false);
  const [recordDuration, setRecordDuration] = useState('00:00');
  const [noteText, setNoteText] = useState('');
  const [sending, setSending] = useState(false);
  const pulseAnim = useRef(new Animated.Value(1)).current;

  // ── Voice recording ──

  const startRecording = async () => {
    try {
      await audioRecorder.startRecorder();
      setRecording(true);

      // Pulse animation while recording
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.15,
            duration: 600,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 600,
            useNativeDriver: true,
          }),
        ]),
      ).start();

      audioRecorder.addRecordBackListener(e => {
        setRecordDuration(
          audioRecorder.mmssss(Math.floor(e.currentPosition)).slice(0, 5),
        );
      });
    } catch (err) {
      console.warn('Recording failed:', err);
    }
  };

  const stopRecording = async () => {
    try {
      const path = await audioRecorder.stopRecorder();
      audioRecorder.removeRecordBackListener();
      setRecording(false);
      setRecordDuration('00:00');
      pulseAnim.stopAnimation();
      pulseAnim.setValue(1);

      // Send audio file to Mira for transcription + ingestion
      setSending(true);
      await MiraApi.uploadAudio(path);
      setSending(false);
      Alert.alert('Sent', 'Voice memo captured by Mira.');
    } catch (err) {
      setSending(false);
      console.warn('Stop recording failed:', err);
    }
  };

  // ── Photo capture ──

  const takePhoto = async () => {
    const options: CameraOptions = {
      mediaType: 'photo',
      quality: 0.8,
      maxWidth: 1920,
      maxHeight: 1920,
      saveToPhotos: false,
    };

    const result = await launchCamera(options);
    if (result.didCancel || !result.assets?.[0]?.uri) return;

    const uri = result.assets[0].uri;
    setSending(true);
    try {
      await MiraApi.uploadPhoto(uri);
      Alert.alert('Sent', 'Photo captured by Mira.');
    } catch (err) {
      Alert.alert('Error', 'Failed to send photo to Mira.');
    } finally {
      setSending(false);
    }
  };

  // ── Text note ──

  const sendNote = async () => {
    if (!noteText.trim()) return;
    Keyboard.dismiss();
    setSending(true);
    try {
      await MiraApi.sendNote(noteText.trim());
      setNoteText('');
      Alert.alert('Sent', 'Note captured by Mira.');
    } catch (err) {
      Alert.alert('Error', 'Failed to send note to Mira.');
    } finally {
      setSending(false);
    }
  };

  // ── Render ──

  return (
    <View style={styles.container}>
      {/* Mode selector */}
      <View style={styles.modeRow}>
        {(['voice', 'photo', 'text'] as CaptureMode[]).map(m => (
          <TouchableOpacity
            key={m}
            style={[styles.modeBtn, mode === m && styles.modeBtnActive]}
            onPress={() => setMode(m)}>
            <Icon
              name={
                m === 'voice'
                  ? 'microphone'
                  : m === 'photo'
                  ? 'camera'
                  : 'text'
              }
              size={20}
              color={mode === m ? COLORS.primary : COLORS.textMuted}
            />
            <Text
              style={[
                styles.modeBtnLabel,
                mode === m && styles.modeBtnLabelActive,
              ]}>
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Central action area */}
      <View style={styles.actionArea}>
        {mode === 'voice' && (
          <>
            <Text style={styles.hintText}>
              {recording ? 'Recording...' : 'Tap and hold to record'}
            </Text>
            {recording && (
              <Text style={styles.durationText}>{recordDuration}</Text>
            )}
            <Animated.View style={{transform: [{scale: pulseAnim}]}}>
              <TouchableOpacity
                style={[
                  styles.captureBtn,
                  recording && styles.captureBtnRecording,
                ]}
                onPressIn={startRecording}
                onPressOut={stopRecording}
                activeOpacity={0.8}>
                <Icon
                  name={recording ? 'stop' : 'microphone'}
                  size={48}
                  color={COLORS.textPrimary}
                />
              </TouchableOpacity>
            </Animated.View>
          </>
        )}

        {mode === 'photo' && (
          <>
            <Text style={styles.hintText}>Tap to open camera</Text>
            <TouchableOpacity
              style={styles.captureBtn}
              onPress={takePhoto}
              disabled={sending}
              activeOpacity={0.8}>
              <Icon name="camera" size={48} color={COLORS.textPrimary} />
            </TouchableOpacity>
          </>
        )}

        {mode === 'text' && (
          <View style={styles.textInputArea}>
            <TextInput
              style={styles.textInput}
              placeholder="Quick note for Mira..."
              placeholderTextColor={COLORS.textMuted}
              value={noteText}
              onChangeText={setNoteText}
              multiline
              maxLength={2000}
            />
            <TouchableOpacity
              style={[
                styles.sendBtn,
                !noteText.trim() && styles.sendBtnDisabled,
              ]}
              onPress={sendNote}
              disabled={!noteText.trim() || sending}>
              <Icon name="send" size={22} color={COLORS.textPrimary} />
            </TouchableOpacity>
          </View>
        )}
      </View>

      {sending && (
        <Text style={styles.sendingText}>Sending to Mira...</Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.backgroundDark,
    paddingHorizontal: SPACING.md,
  },

  // Mode selector
  modeRow: {
    flexDirection: 'row',
    gap: SPACING.sm,
    marginTop: SPACING.md,
  },
  modeBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: SPACING.xs,
    paddingVertical: SPACING.sm,
    borderRadius: 10,
    backgroundColor: COLORS.backgroundCard,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  modeBtnActive: {
    borderColor: COLORS.primary,
    backgroundColor: COLORS.primary + '15',
  },
  modeBtnLabel: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.sm,
    fontWeight: '600',
  },
  modeBtnLabelActive: {
    color: COLORS.primary,
  },

  // Action area
  actionArea: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  hintText: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.md,
    marginBottom: SPACING.lg,
  },
  durationText: {
    color: COLORS.error,
    fontSize: FONT_SIZES.xxl,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
    marginBottom: SPACING.md,
  },
  captureBtn: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 8,
    shadowColor: COLORS.primary,
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.4,
    shadowRadius: 12,
  },
  captureBtnRecording: {
    backgroundColor: COLORS.error,
  },

  // Text input
  textInputArea: {
    width: '100%',
    gap: SPACING.sm,
  },
  textInput: {
    backgroundColor: COLORS.backgroundInput,
    borderRadius: 12,
    padding: SPACING.md,
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.md,
    minHeight: 120,
    textAlignVertical: 'top',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  sendBtn: {
    backgroundColor: COLORS.primary,
    borderRadius: 12,
    paddingVertical: SPACING.sm + 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },

  sendingText: {
    color: COLORS.primaryLight,
    fontSize: FONT_SIZES.sm,
    textAlign: 'center',
    paddingBottom: SPACING.lg,
  },
});

export default CaptureScreen;
