/**
 * Records WebSocket events to a JSON structure for later replay.
 *
 * Usage: Enable with NEXT_PUBLIC_RECORD_EVENTS=true
 * Events are collected in memory and can be exported via export().
 */

export interface SystemEvent {
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
}

export interface RecordedEvent {
  timestamp: number; // ms since recording start
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
}

export interface EventRecording {
  recording_id: string;
  started_at: string;
  events: RecordedEvent[];
  metadata: {
    spec_id?: string;
    total_events: number;
    duration_ms: number;
    event_types: string[];
  };
}

export class EventRecorder {
  private events: RecordedEvent[] = [];
  private startTime: number = Date.now();
  private _isRecording: boolean = false;

  get isRecording(): boolean {
    return this._isRecording;
  }

  get eventCount(): number {
    return this.events.length;
  }

  start(): void {
    this._isRecording = true;
    this.startTime = Date.now();
    this.events = [];
  }

  stop(): void {
    this._isRecording = false;
  }

  record(event: SystemEvent): void {
    if (!this._isRecording) return;

    this.events.push({
      timestamp: Date.now() - this.startTime,
      event_type: event.event_type,
      entity_type: event.entity_type,
      entity_id: event.entity_id,
      payload: event.payload,
    });
  }

  export(): EventRecording {
    const eventTypes = [...new Set(this.events.map((e) => e.event_type))];

    return {
      recording_id:
        typeof crypto !== "undefined"
          ? crypto.randomUUID()
          : Math.random().toString(36).slice(2),
      started_at: new Date(this.startTime).toISOString(),
      events: [...this.events],
      metadata: {
        total_events: this.events.length,
        duration_ms: Date.now() - this.startTime,
        event_types: eventTypes,
      },
    };
  }

  /**
   * Download the recording as a JSON file.
   * Works in browser environment only.
   */
  downloadRecording(filename?: string): void {
    const recording = this.export();
    const blob = new Blob([JSON.stringify(recording, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `event-recording-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  clear(): void {
    this.events = [];
    this.startTime = Date.now();
  }
}
