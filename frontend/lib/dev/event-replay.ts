/**
 * Replays recorded event sequences through the same interface
 * the frontend uses for live WebSocket events.
 *
 * Usage: Set NEXT_PUBLIC_EVENT_REPLAY=path/to/recording.json
 */

import type {
  SystemEvent,
  EventRecording,
  RecordedEvent,
} from "./event-recorder";

export type EventHandler = (event: SystemEvent) => void;

export class EventReplayProvider {
  private recording: EventRecording;
  private eventHandlers: Map<string, Set<EventHandler>> = new Map();
  private playbackSpeed: number = 1.0;
  private isPlaying: boolean = false;
  private isPaused: boolean = false;
  private currentIndex: number = 0;
  private timeoutId: ReturnType<typeof setTimeout> | null = null;

  constructor(recording: EventRecording) {
    this.recording = recording;
  }

  get totalEvents(): number {
    return this.recording.events.length;
  }

  get progress(): number {
    if (this.recording.events.length === 0) return 0;
    return this.currentIndex / this.recording.events.length;
  }

  get playing(): boolean {
    return this.isPlaying;
  }

  /**
   * Subscribe to events — same interface as the real WebSocket provider.
   * Existing hooks work unchanged.
   */
  subscribe(eventType: string, handler: EventHandler): () => void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(handler);
    return () => {
      this.eventHandlers.get(eventType)?.delete(handler);
    };
  }

  /**
   * Start replaying events with timing preserved.
   */
  async play(speed: number = 1.0): Promise<void> {
    this.playbackSpeed = speed;
    this.isPlaying = true;
    this.isPaused = false;

    const events = this.recording.events;
    let prevTimestamp = 0;

    for (let i = this.currentIndex; i < events.length; i++) {
      if (!this.isPlaying || this.isPaused) {
        this.currentIndex = i;
        return;
      }

      const event = events[i];
      const delay = (event.timestamp - prevTimestamp) / this.playbackSpeed;
      prevTimestamp = event.timestamp;

      if (delay > 0) {
        await new Promise<void>((resolve) => {
          this.timeoutId = setTimeout(resolve, delay);
        });
      }

      if (!this.isPlaying) {
        this.currentIndex = i;
        return;
      }

      this._emit(event);
      this.currentIndex = i + 1;
    }

    this.isPlaying = false;
  }

  /**
   * Replay all events instantly (for tests or quick state hydration).
   */
  replayInstant(): void {
    for (const event of this.recording.events) {
      this._emit(event);
    }
    this.currentIndex = this.recording.events.length;
  }

  pause(): void {
    this.isPaused = true;
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
  }

  resume(): void {
    if (this.isPaused) {
      this.isPaused = false;
      this.play(this.playbackSpeed);
    }
  }

  stop(): void {
    this.isPlaying = false;
    this.isPaused = false;
    this.currentIndex = 0;
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
  }

  reset(): void {
    this.stop();
    this.currentIndex = 0;
  }

  private _emit(event: RecordedEvent): void {
    const systemEvent: SystemEvent = {
      event_type: event.event_type,
      entity_type: event.entity_type,
      entity_id: event.entity_id,
      payload: event.payload,
    };

    // Emit to specific type subscribers
    this.eventHandlers.get(event.event_type)?.forEach((h) => h(systemEvent));
    // Emit to wildcard subscribers
    this.eventHandlers.get("*")?.forEach((h) => h(systemEvent));
  }
}

/**
 * Load a recording from a URL or path.
 */
export async function loadRecording(path: string): Promise<EventRecording> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load recording: ${response.statusText}`);
  }
  return response.json();
}
