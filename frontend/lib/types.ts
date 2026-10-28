// Mirrors backend/eventproof/{pipeline.py, schemas/*.py}. Coordinates in zones/lines are normalized [0, 1].
export type Pt = [number, number];

export interface Zone { id: string; polygon: Pt[] }
export interface Line { id: string; a: Pt; b: Pt }
export interface Layout {
  zones: { zone: Zone; description: string }[];
  lines: { line: Line; description: string }[];
}

export interface Box { x1: number; y1: number; x2: number; y2: number }
export interface TrackFrame {
  frame_index: number; timestamp_ms: number; object_id: number; label: string;
  box: Box; confidence: number | null; occluded: boolean; mask_ref: string | null;
}
export interface VideoInfo { width: number; height: number; fps: number; frame_count: number }
export interface TrackSet { video: VideoInfo; frames: TrackFrame[]; source: string; source_ref: string | null }

export type Tri = "TRUE" | "FALSE" | "UNKNOWN";
export interface EventTrace { op: string; target: string; status: Tri; frame: number | null; timestamp_ms: number | null; reason: string }
export interface ObjectVerdict {
  object_id: number; verdict: "PASS" | "VIOLATION" | "UNKNOWN";
  first_frame: number; last_frame: number; events: EventTrace[]; explanation: string;
}
export interface RuleReport {
  rule_id: string; rule_version: number; rule_hash: string; track_source: string;
  track_source_ref: string | null; overall: "PASS" | "FAIL" | "UNKNOWN" | "NO_OBJECTS"; objects: ObjectVerdict[];
}

export interface Evidence {
  schema_version: string; run_id: string; created_at: string; eventproof_version: string;
  status: "completed" | "rule_unsupported" | "rule_invalid" | "perception_failed";
  video: { filename: string; sha256: string; original_sha256: string; info: VideoInfo; duration_s: number;
           codec: string; reencoded: boolean; reencode_reasons: string[] };
  rule: { text: string; layout: Layout; model: string; request_ids: string[]; cached: boolean | null; attempts: number | null;
          compiled_rule: Record<string, unknown> | null; rule_hash: string | null; assumptions: string[]; error: string | null };
  perception: { model: string; prompt: string; source_ref: string | null; cached: boolean | null; tracks_sha256: string | null;
                frames_with_detections: number; boxes: number; track_ids: number[]; error: string | null } | null;
  result: RuleReport | null;
  evidence_sha256: string;
}
