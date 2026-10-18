"use client";

/**
 * LazyCanvas — a dynamic wrapper around WebGLCanvas so that NOTHING from
 * @react-three/fiber is ever evaluated during server-side rendering or
 * Next.js static pre-rendering. Import this instead of WebGLCanvas directly.
 *
 * Usage is identical to WebGLCanvas.
 */
import dynamic from "next/dynamic";

export const LazyCanvas = dynamic(
  () => import("./WebGLCanvas").then((m) => m.WebGLCanvas),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center rounded-xl bg-[#0D1220]">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-[#6C63FF] border-t-transparent" />
      </div>
    ),
  }
);
