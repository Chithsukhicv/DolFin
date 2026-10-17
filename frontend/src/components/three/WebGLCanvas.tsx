"use client";

import { Suspense, useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";

// Detect WebGL support
function hasWebGL(): boolean {
  if (typeof window === "undefined") return false;
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
  const [webglAvailable, setWebglAvailable] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setWebglAvailable(hasWebGL());
  }, []);

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
