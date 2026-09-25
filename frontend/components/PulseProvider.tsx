"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { API_BASE, api } from "@/lib/api";
import type { DemoStatus, Mission, MissionEvent } from "@/lib/types";

export type StreamStatus = "connecting" | "live" | "offline";

export interface StreamListener {
  onMissionEvent?: (event: MissionEvent) => void;
  onMissionUpdate?: (mission: Mission) => void;
  onApprovalsChanged?: () => void;
  onOutcomesChanged?: () => void;
  onDemoReset?: () => void;
}

interface PulseValue {
  streamStatus: StreamStatus;
  pendingApprovals: number;
  status: DemoStatus | null;
  apiOnline: boolean;
  subscribe: (listener: StreamListener) => () => void;
  refreshPending: () => void;
  resetDemo: () => Promise<void>;
  resetting: boolean;
}

const PulseContext = createContext<PulseValue | null>(null);

/**
 * Owns the single Server-Sent Events connection for the whole app and fans
 * updates out to whichever screen is mounted. One connection, one source of
 * truth: every screen reacts to the same backend events.
 */
export function PulseProvider({ children }: { children: ReactNode }) {
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("connecting");
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [apiOnline, setApiOnline] = useState(true);
  const [resetting, setResetting] = useState(false);
  const listeners = useRef<Set<StreamListener>>(new Set());

  const subscribe = useCallback((listener: StreamListener) => {
    listeners.current.add(listener);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  const each = useCallback((fn: (l: StreamListener) => void) => {
    listeners.current.forEach(fn);
  }, []);

  const refreshPending = useCallback(() => {
    api
      .approvals("pending")
      .then((data) => {
        setPendingApprovals(data.pending_count);
        setApiOnline(true);
      })
      .catch(() => setApiOnline(false));
  }, []);

  useEffect(() => {
    refreshPending();
    api
      .status()
      .then((data) => {
        setStatus(data);
        setApiOnline(true);
      })
      .catch(() => setApiOnline(false));
  }, [refreshPending]);

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/api/stream`);

    const parse = <T,>(event: Event): T | null => {
      try {
        return JSON.parse((event as MessageEvent).data) as T;
      } catch {
        return null;
      }
    };

    const onOpen = () => {
      setStreamStatus("live");
      setApiOnline(true);
    };
    source.addEventListener("connected", onOpen);
    source.onopen = onOpen;
    source.onerror = () => setStreamStatus("offline");

    source.addEventListener("mission_event", (event) => {
      const data = parse<MissionEvent>(event);
      if (data) each((l) => l.onMissionEvent?.(data));
    });
    source.addEventListener("mission_update", (event) => {
      const data = parse<Mission>(event);
      if (data) each((l) => l.onMissionUpdate?.(data));
    });
    source.addEventListener("approvals_changed", () => {
      refreshPending();
      each((l) => l.onApprovalsChanged?.());
    });
    source.addEventListener("outcomes_changed", () => {
      each((l) => l.onOutcomesChanged?.());
    });
    source.addEventListener("demo_reset", () => {
      setPendingApprovals(0);
      each((l) => l.onDemoReset?.());
    });

    return () => source.close();
  }, [each, refreshPending]);

  const resetDemo = useCallback(async () => {
    setResetting(true);
    try {
      await api.reset();
      setPendingApprovals(0);
      each((l) => l.onDemoReset?.());
    } finally {
      setResetting(false);
    }
  }, [each]);

  const value = useMemo<PulseValue>(
    () => ({
      streamStatus,
      pendingApprovals,
      status,
      apiOnline,
      subscribe,
      refreshPending,
      resetDemo,
      resetting,
    }),
    [
      streamStatus,
      pendingApprovals,
      status,
      apiOnline,
      subscribe,
      refreshPending,
      resetDemo,
      resetting,
    ],
  );

  return <PulseContext.Provider value={value}>{children}</PulseContext.Provider>;
}

export function usePulse(): PulseValue {
  const value = useContext(PulseContext);
  if (!value) throw new Error("usePulse must be used inside PulseProvider");
  return value;
}

/** Register stream handlers for the lifetime of a component. */
export function usePulseStream(listener: StreamListener) {
  const { subscribe } = usePulse();
  const ref = useRef(listener);

  // Keep the handlers fresh without resubscribing, and without writing to a ref
  // during render.
  useEffect(() => {
    ref.current = listener;
  });

  useEffect(
    () =>
      subscribe({
        onMissionEvent: (e) => ref.current.onMissionEvent?.(e),
        onMissionUpdate: (m) => ref.current.onMissionUpdate?.(m),
        onApprovalsChanged: () => ref.current.onApprovalsChanged?.(),
        onOutcomesChanged: () => ref.current.onOutcomesChanged?.(),
        onDemoReset: () => ref.current.onDemoReset?.(),
      }),
    [subscribe],
  );
}
