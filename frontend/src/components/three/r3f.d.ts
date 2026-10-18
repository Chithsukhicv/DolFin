/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Augments React's JSX IntrinsicElements with the full set of Three.js
 * element names that React Three Fiber exposes. These are registered by
 * @react-three/fiber at runtime but need to be declared here for TypeScript
 * to accept them in JSX.
 *
 * We derive from ThreeElements when the package supports it, or fall back to
 * an explicit list of the elements actually used in this project.
 */
import type { ThreeElements } from "@react-three/fiber";

declare global {
  namespace React {
    // eslint-disable-next-line @typescript-eslint/no-empty-object-type
    interface IntrinsicElements extends ThreeElements {}
  }
}
