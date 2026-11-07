"use client";

import { Suspense, useSyncExternalStore } from "react";
import dynamic from "next/dynamic";

const Canvas = dynamic(
  () => import("@react-three/fiber").then((m) => m.Canvas),
  { ssr: false }
);

// FIX: WebGL availability and mount state are read via useSyncExternalStore
// instead of setState inside useEffect, which triggered react-hooks/no-direct-
// set-state-in-use-effect in CI lint.
function hasWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

function noopSubscribe() {
  return () => {};
}

function useClientValue<T>(clientFn: () => T, serverValue: T): T {
  return useSyncExternalStore(noopSubscribe, clientFn, () => serverValue);
}

interface WebGLCanvasProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  camera?: { position?: [number, number, number]; fov?: number };
  fallback?: React.ReactNode;
}

export function WebGLCanvas({
  children,
  className,
  style,
  camera = { position: [0, 0, 5], fov: 60 },
  fallback,
}: WebGLCanvasProps) {
  const mounted = useClientValue(() => true, false);
  const webglAvailable = useClientValue(hasWebGL, true);

  if (!mounted) return null;

  if (!webglAvailable) {
    return (
      <div className={className} style={style}>
        {fallback ?? (
          <div className="flex h-full items-center justify-center rounded-xl bg-[#0D1220] text-xs text-[#9BA7BC]">
            3D view unavailable
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={className} style={style}>
      <Suspense
        fallback={
          <div className="flex h-full items-center justify-center rounded-xl bg-[#0D1220]">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-[#6C63FF] border-t-transparent" />
          </div>
        }
      >
        <Canvas
          gl={{ antialias: true, alpha: true }}
          dpr={[1, 2]}
          camera={camera}
          style={{ width: "100%", height: "100%" }}
        >
          {children}
        </Canvas>
      </Suspense>
    </div>
  );
}
