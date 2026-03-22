/**
 * AudioService — Persistent foreground service for continuous audio capture.
 *
 * Uses react-native-foreground-service to keep the app alive in the background.
 * Audio is recorded in short chunks (configurable interval) and sent to Mira
 * for transcription and ingestion.
 *
 * The foreground notification is required by Android for long-running services.
 */
import VIForegroundService from 'react-native-foreground-service';
import AudioRecorderPlayer from 'react-native-audio-recorder-player';
import RNFS from 'react-native-fs';
import AsyncStorage from '@react-native-async-storage/async-storage';
import MiraApi from './MiraApi';

const NOTIFICATION_CHANNEL_ID = 'mira_audio_capture';
const NOTIFICATION_ID = 1001;
const CHUNK_DURATION_MS = 30_000; // 30-second chunks
const AUDIO_DIR = `${RNFS.CachesDirectoryPath}/mira_audio`;

class AudioServiceManager {
  private recorder: AudioRecorderPlayer;
  private chunkTimer: ReturnType<typeof setInterval> | null = null;
  private running = false;
  private chunkIndex = 0;

  constructor() {
    this.recorder = new AudioRecorderPlayer();
  }

  /**
   * Start the foreground service and begin continuous audio capture.
   */
  async start(): Promise<void> {
    const enabled = await AsyncStorage.getItem('@audio_enabled');
    if (enabled === 'false') {
      console.log('AudioService: disabled by user setting');
      return;
    }

    // Ensure audio cache directory exists
    const dirExists = await RNFS.exists(AUDIO_DIR);
    if (!dirExists) {
      await RNFS.mkdir(AUDIO_DIR);
    }

    // Create notification channel (Android 8+)
    await VIForegroundService.createNotificationChannel({
      id: NOTIFICATION_CHANNEL_ID,
      name: 'Mira Audio Capture',
      description: 'Continuous audio capture for Mira',
      importance: 2, // LOW — no sound
      enableVibration: false,
    });

    // Start foreground service with persistent notification
    await VIForegroundService.startService({
      id: NOTIFICATION_ID,
      channelId: NOTIFICATION_CHANNEL_ID,
      title: 'Mira Listening',
      text: 'Capturing ambient audio for memory ingestion',
      icon: 'ic_notification',
      importance: 2,
    });

    this.running = true;
    this.chunkIndex = 0;

    // Start recording first chunk
    await this.startChunk();

    // Rotate chunks on interval
    this.chunkTimer = setInterval(async () => {
      await this.rotateChunk();
    }, CHUNK_DURATION_MS);

    console.log('AudioService: started');
  }

  /**
   * Stop the foreground service and audio capture.
   */
  async stop(): Promise<void> {
    this.running = false;

    if (this.chunkTimer) {
      clearInterval(this.chunkTimer);
      this.chunkTimer = null;
    }

    try {
      await this.recorder.stopRecorder();
    } catch {
      // May not be recording
    }

    try {
      await VIForegroundService.stopService();
    } catch {
      // May not be running
    }

    console.log('AudioService: stopped');
  }

  /**
   * Pause/resume (triggered by shake gesture).
   */
  async toggle(): Promise<void> {
    if (this.running) {
      await this.stop();
    } else {
      await this.start();
    }
  }

  isRunning(): boolean {
    return this.running;
  }

  // ── Internal ──

  private chunkPath(): string {
    return `${AUDIO_DIR}/chunk_${this.chunkIndex}.aac`;
  }

  private async startChunk(): Promise<void> {
    try {
      await this.recorder.startRecorder(this.chunkPath());
    } catch (err) {
      console.warn('AudioService: failed to start chunk', err);
    }
  }

  private async rotateChunk(): Promise<void> {
    if (!this.running) return;

    try {
      // Stop current recording
      const finishedPath = await this.recorder.stopRecorder();

      // Upload finished chunk to Mira in background
      this.uploadChunk(finishedPath).catch(err =>
        console.warn('AudioService: upload failed', err),
      );

      // Start next chunk
      this.chunkIndex = (this.chunkIndex + 1) % 100; // wrap at 100
      await this.startChunk();
    } catch (err) {
      console.warn('AudioService: chunk rotation failed', err);
    }
  }

  private async uploadChunk(filePath: string): Promise<void> {
    try {
      await MiraApi.uploadAudio(filePath);
      // Clean up after successful upload
      await RNFS.unlink(filePath);
    } catch (err) {
      console.warn('AudioService: failed to upload chunk', err);
      // Keep file for retry — TODO: implement retry queue
    }
  }
}

const AudioService = new AudioServiceManager();
export default AudioService;
