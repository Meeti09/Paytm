import type {
  Approval,
  DemoStatus,
  Mission,
  MissionEvent,
  MissionSummary,
  Outcomes,
  Policy,
  Scenarios,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Cannot reach the Paytm Pulse API. Is the backend running on " +
        `${API_BASE}?`,
      0,
    );
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep the status line */
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  status: () => request<DemoStatus>("/api/demo/status"),
  scenarios: () => request<Scenarios>("/api/demo/scenarios"),

  missions: (agent?: string) =>
    request<{ missions: MissionSummary[] }>(
      `/api/missions${agent ? `?agent=${agent}` : ""}`,
    ).then((r) => r.missions),
  mission: (id: string) => request<Mission>(`/api/missions/${id}`),
  missionEvents: (id: string) =>
    request<{ events: MissionEvent[] }>(`/api/missions/${id}/events`).then(
      (r) => r.events,
    ),

  startMission: (id: string) => post<Mission>(`/api/missions/${id}/start`),
  pauseMission: (id: string) => post<Mission>(`/api/missions/${id}/pause`),
  retryMission: (id: string) => post<Mission>(`/api/missions/${id}/retry`),
  takeoverMission: (id: string, operator = "Ops Lead") =>
    post<Mission>(`/api/missions/${id}/takeover`, { operator }),
  replyToMission: (id: string, leadId: string, text: string) =>
    post<Mission>(`/api/missions/${id}/reply`, { lead_id: leadId, text }),

  approvals: (status = "pending") =>
    request<{ approvals: Approval[]; policy: Policy; pending_count: number }>(
      `/api/approvals?status=${status}`,
    ),
  approve: (id: string, reviewer = "Ops Lead") =>
    post<Approval>(`/api/approvals/${id}/approve`, { reviewer }),
  reject: (id: string, reviewer = "Ops Lead", note = "") =>
    post<Approval>(`/api/approvals/${id}/reject`, { reviewer, note }),
  takeoverApproval: (id: string, reviewer = "Ops Lead") =>
    post<Approval>(`/api/approvals/${id}/takeover`, { reviewer }),

  outcomes: () => request<Outcomes>("/api/outcomes"),

  runResolve: (scenario: string) =>
    post<Mission>("/api/demo/resolve", { scenario }),
  runResolveCustom: (customerId: string, message: string) =>
    post<Mission>("/api/demo/resolve", {
      customer_id: customerId,
      message,
    }),
  runGrow: (location: string, targetCount: number) =>
    post<Mission>("/api/demo/grow", {
      location,
      target_count: targetCount,
    }),
  reset: () => post<{ reset: boolean }>("/api/demo/reset"),
};
