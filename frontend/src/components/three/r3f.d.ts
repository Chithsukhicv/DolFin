/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Augments React's JSX IntrinsicElements with Three.js element names.
 *
 * IMPORTANT: no top-level import/export — this file must be an ambient script.
 * With isolatedModules:true a file with imports becomes a module and its global
 * augmentations don't propagate to other files. The inline import() expression
 * keeps this file script-scoped while still referencing external types.
 */
declare global {
  namespace React {
    // eslint-disable-next-line @typescript-eslint/no-empty-object-type
    interface IntrinsicElements
      extends import("@react-three/fiber").ThreeElements {}
  }
}
