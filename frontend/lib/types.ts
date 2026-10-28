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

export interface Truth { object_id: number; label: string; station_stop_ms: number; crosses_packing_frame: number | null; intended: string }
export interface ChallengeReport {
  run_id: string; rule_hash: string; world: string; perception: string;
  suite: Record<string, Record<string, number>>; suite_cases: number; failures: number; files: string[];
  counterexample: null | {
    family: string; seed: number; outcome: string; detector_verdict: string; intended: string; oracle_verdict: string;
    truths: Truth[]; notes: string; reduction: string[]; evaluations: number;
    knob?: string; t_fail?: number; t_pass?: number; pass_verdict?: string; decisive_frames?: number[];
    scene_difference?: { frames_compared: number; frames_differing: number; max_pixels_differing_in_a_frame: number };
  };
}
export interface SamConfirm {
  scene_sha256: string; mock_outcome: string; still_fails_with_sam: boolean; live_sam_calls: number;
  sam: { perception_source: string; detector_verdict: string; intended: string; oracle_verdict: string; outcome: string };
}
export interface HoldoutMetrics { n: number; correct: number; false_pass: number; false_alarm: number; abstained: number }
export interface RepairDecision {
  proposal: { proposal_id: string; proposer: string; rationale: string;
              expected_effect: { round?: number; dev_screen?: { dev_regressions: number; dev_fixed: number; dev_cases: number }; model_claim?: string } };
  patch_description: string; accepted: boolean; reasons: string[]; regressions: string[]; fixed_cases: string[];
  holdout_name: string; holdout_before: HoldoutMetrics; holdout_after: HoldoutMetrics | null; origin_outcomes_after: string[];
}
export interface RepairRun {
  run_id: string; proposer: string; decisions: RepairDecision[]; holdout_note: string;
  trace: { rounds?: { round: number; diagnosis: string; cached: boolean; request_id: string }[] };
}

export interface CounterStep { frame: number; in_zone: boolean; still: boolean | null; counted_ms: number }
export interface BeforeAfterSide {
  rule_hash: string; plain: string; threshold_ms: number | null; verdict: string; intended: string; outcome: string;
  correct: boolean; series: Record<string, CounterStep[]>;
}
export interface FamilyCounts { [outcome: string]: number }
export interface HoldoutFull extends HoldoutMetrics { by_family: Record<string, FamilyCounts> }
export interface BeforeAfter {
  run_id: string; proposer: string; accepted: number; proposals: number; choice: string; perception: string;
  scene: { family: string; seed: number; scene_sha256: string; fps: number; n_frames: number; width: number; height: number;
           notes: string; zones: Zone[]; lines: Line[] };
  boxes: { frame_index: number; object_id: number; box: Box }[];
  truths: Truth[];
  before: BeforeAfterSide;
  after: BeforeAfterSide | null;
  decision: null | {
    proposal_id: string; patch_description: string; rationale: string; reasons: string[]; holdout_name: string;
    holdout_manifest_sha256: string; holdout_before: HoldoutFull; holdout_after: HoldoutFull | null;
    fixed_cases: string[]; regressions: string[]; previous_rule_hash: string; patched_rule_hash: string | null;
  };
}
export interface FinalSplit { n: number; correct: number; accuracy_ci95: [number, number]; false_pass: number; false_alarm: number; abstained: number }
export interface FinalReport {
  final_set: string; manifest_sha256: string; perception: string; code_commit: string;
  inputs: Record<string, { file: string; sha256: string; proposals: number }>;
  baselines: Record<string, Record<string, FinalSplit>>;
  patches: { source: string; proposal_id: string; patch_description: string; grader_accepted: boolean;
             splits: Record<string, FinalSplit>; fixed: Record<string, number>; regressed: Record<string, number>;
             sign_test_p: Record<string, number> }[];
}
