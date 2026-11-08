/**
 * Augments React's JSX IntrinsicElements with Three.js element names from
 * React Three Fiber.
 *
 * This file must remain an ambient script (no top-level import/export).
 * With isolatedModules:true a file with imports becomes a module and its
 * global augmentations don't propagate. We use a local type alias to resolve
 * the external type while keeping the file script-scoped — ESLint's parser
 * accepts `extends` on a qualified identifier, not on an import() expression.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type R3FThreeElements = import("@react-three/fiber").ThreeElements;

declare global {
  namespace React {
    // eslint-disable-next-line @typescript-eslint/no-empty-object-type
    interface IntrinsicElements extends R3FThreeElements {}
  }
}
