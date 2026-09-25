export type AgentName = "resolve" | "grow";

export type MissionStatus =
  | "created"
  | "running"
  | "waiting_approval"
  | "waiting_response"
  | "paused"
  | "needs_attention"
  | "human_takeover"
  | "completed"
  | "failed";

export type RiskLevel = "low" | "medium" | "high";
export type EventLevel = "ok" | "pending" | "warn" | "error" | "info";

export interface MissionEvent {
  id: number;
  mission_id: string;
  timestamp: string;
  event_type: string;
  actor: string;
  message: string;
  level: EventLevel;
  metadata: Record<string, unknown>;
}

export interface ContextRow {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "danger";
}

export interface ContextPanelData {
  title: string;
  rows: ContextRow[];
}

export interface ScoreFactor {
  factor: string;
  points: number;
  max: number;
  detail: string;
}

export interface LeadView {
  id: string;
  merchant_id: string;
  name: string;
  category: string;
  location: string;
  paytm_status: string;
  estimated_volume: number;
  contact: string;
  website: string;
  score: number;
  stage: string;
  opportunity: "High" | "Medium" | "Low";
  reasons: string[];
  breakdown: ScoreFactor[];
  next_action: string;
  outreach_message: string;
  response_message: string;
  qualification_note: string;
  meeting_slot: string;
}

export interface TriggeredRule {
  rule: string;
  detail: string;
  risk: RiskLevel;
}

export interface Decision {
  title: string;
  action_type: string;
  amount: number;
  reason: string;
  evidence: string[];
  risk_level: RiskLevel;
  verdict: "AUTONOMOUS" | "REQUIRES_APPROVAL";
  policy_rule: string;
  policy_detail: string;
  triggered_rules: TriggeredRule[];
  next: string;
  source: string;
  action_id: string;
  /** Set once the action has been executed and verified. */
  resolved?: boolean;
}

export interface MissionContext {
  kind?: "resolve" | "grow";
  panels?: ContextPanelData[];
  memory?: { source: string; detail: string; items: { label: string; value: string }[] };
  stats?: Record<string, number>;
  leads?: LeadView[];
  focus_lead_id?: string | null;
  suggested_replies?: string[];
  territory?: string;
  history?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface MissionAction {
  id: string;
  action_type: string;
  description: string;
  risk_level: RiskLevel;
  requires_approval: boolean;
  approval_id: string | null;
  status: string;
  executed_via: string;
  result: { workflow_code?: string; executed_via?: string } | null;
}

export interface Mission {
  id: string;
  agent: AgentName;
  objective: string;
  status: MissionStatus;
  stage: string;
  progress: number;
  result: string | null;
  result_label: string;
  inputs: Record<string, unknown>;
  context: MissionContext;
  decision: Decision | null;
  summary: {
    headline?: string;
    lines?: string[];
    customer_message?: string;
    approval_id?: string;
    focus_lead_id?: string;
    meeting_slot?: string;
  };
  error: string;
  human_involved: boolean;
  created_at: string | null;
  completed_at: string | null;
  actions: MissionAction[];
  pending_approval_id: string | null;
  events?: MissionEvent[];
  running?: boolean;
}

export interface MissionSummary {
  id: string;
  agent: AgentName;
  objective: string;
  status: MissionStatus;
  stage: string;
  progress: number;
  result: string | null;
  result_label: string;
  human_involved: boolean;
  created_at: string | null;
  completed_at: string | null;
}

export interface Approval {
  id: string;
  mission_id: string;
  action_id: string;
  agent: AgentName;
  title: string;
  subject: string;
  reason: string;
  policy_rule: string;
  policy_detail: string;
  risk_level: RiskLevel;
  evidence: string[];
  triggered_rules: TriggeredRule[];
  ai_recommendation: string;
  impact: string;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string | null;
  mission: {
    id: string;
    agent: AgentName;
    objective: string;
    status: string;
    context: MissionContext;
    decision: Decision | null;
  } | null;
  action: {
    id: string;
    action_type: string;
    description: string;
    status: string;
    payload: Record<string, unknown>;
  } | null;
}

export interface PolicyRuleView {
  rule: string;
  label: string;
  enabled: boolean;
}

export interface Policy {
  refund_threshold: number;
  refund_threshold_label: string;
  disclaimer: string;
  rules: PolicyRuleView[];
  autonomous: string[];
}

export interface Metric {
  value: number;
  label: string;
  basis: string;
}

export interface OutcomeMissionRow {
  id: string;
  agent: AgentName;
  objective: string;
  status: MissionStatus;
  result: string | null;
  result_label: string;
  human_involved: boolean;
  approvals: number;
  created_at: string | null;
  completed_at: string | null;
}

export interface Outcomes {
  resolve: {
    metrics: Metric[];
    autonomy_rate: number | null;
    autonomy_rate_basis: string;
    approvals_rejected: number;
    in_flight: number;
  };
  grow: { metrics: Metric[]; missions: number; in_flight: number };
  missions: OutcomeMissionRow[];
  trace: {
    missions_recorded: number;
    events_recorded: number;
    actions_executed: number;
  };
  note: string;
}

export interface IntegrationState {
  mode: "live" | "fallback" | "simulated";
  detail: string;
}

export interface DemoStatus {
  integrations: Record<string, IntegrationState>;
  policy: Policy;
  permissions: Record<string, Record<string, string[]>>;
  missions: number;
  live_clients: number;
  disclosure: string;
}

export interface ResolveScenario {
  id: string;
  title: string;
  customer_id: string;
  customer_name: string;
  message: string;
  language: string;
  expected: string;
  expected_outcome: string;
}

export interface Scenarios {
  resolve: ResolveScenario[];
  grow: { location: string; target_count: number; objective: string };
  customers: { id: string; name: string; language: string }[];
  dataset: { customers: number; merchants: number; transactions: number };
}
