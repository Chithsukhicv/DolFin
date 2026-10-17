"use client";

// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference types="@react-three/fiber" />

import { useRef, useEffect, useState, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Sparkles } from "@react-three/drei";
import * as THREE from "three";

type ScenarioKind = "crash" | "bull" | "correction" | "sideways" | "bear" | null;

const SCENARIO_CONFIG: Record<
  NonNullable<ScenarioKind>,
  {
    primaryColor: string;
    secondaryColor: string;
    lightColor: string;
    rotationSpeed: number;
    sparkleColor: string;
    geometryType: "torusKnot" | "cone" | "torus" | "plane" | "sphere";
  }
> = {
  crash: {
    primaryColor: "#FF4444",
    secondaryColor: "#FF6B6B",
    lightColor: "#FF2200",
    rotationSpeed: 2.8,
    sparkleColor: "#FF6B6B",
    geometryType: "torusKnot",
  },
  bear: {
    primaryColor: "#DC2626",
    secondaryColor: "#991B1B",
    lightColor: "#CC1100",
    rotationSpeed: 0.4,
    sparkleColor: "#DC2626",
    geometryType: "sphere",
  },
  bull: {
    primaryColor: "#00D6A0",
    secondaryColor: "#40D9FF",
    lightColor: "#00FF88",
    rotationSpeed: 1.2,
    sparkleColor: "#00D6A0",
    geometryType: "cone",
  },
  correction: {
    primaryColor: "#FDD663",
    secondaryColor: "#F59E0B",
    lightColor: "#FFAA00",
    rotationSpeed: 0.8,
    sparkleColor: "#FDD663",
    geometryType: "torus",
  },
  sideways: {
    primaryColor: "#40D9FF",
    secondaryColor: "#6C63FF",
    lightColor: "#40D9FF",
    rotationSpeed: 0.3,
    sparkleColor: "#40D9FF",
    geometryType: "plane",
  },
};

function SceneGeometry({
  kind,
  reducedMotion,
}: {
  kind: NonNullable<ScenarioKind>;
  reducedMotion: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const cfg = SCENARIO_CONFIG[kind];

  useFrame((_, delta) => {
    if (reducedMotion || !meshRef.current) return;
    meshRef.current.rotation.x += delta * cfg.rotationSpeed * 0.3;
    meshRef.current.rotation.y += delta * cfg.rotationSpeed;
  });

  const geo = useMemo(() => {
    switch (cfg.geometryType) {
      case "torusKnot": return <torusKnotGeometry args={[0.8, 0.25, 100, 16, 2, 5]} />;
      case "cone": return <coneGeometry args={[0.8, 1.8, 6]} />;
      case "torus": return <torusGeometry args={[0.9, 0.32, 16, 48]} />;
      case "sphere": return <sphereGeometry args={[0.9, 24, 24]} />;
      case "plane": return <torusGeometry args={[1.0, 0.08, 6, 48]} />;
    }
  }, [cfg.geometryType]);

  return (
    <mesh ref={meshRef}>
      {geo}
      <meshStandardMaterial
        color={cfg.primaryColor}
        metalness={0.7}
        roughness={0.2}
        emissive={cfg.primaryColor}
        emissiveIntensity={0.3}
        wireframe={kind === "crash"}
      />
    </mesh>
  );
}

function NeutralScene({ reducedMotion }: { reducedMotion: boolean }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (reducedMotion || !ref.current) return;
    ref.current.rotation.x = Math.sin(clock.elapsedTime * 0.3) * 0.2;
    ref.current.rotation.y += 0.005;
  });
  return (
    <mesh ref={ref}>
      <icosahedronGeometry args={[1.0, 1]} />
      <meshStandardMaterial color="#6C63FF" wireframe metalness={0.5} roughness={0.5} />
    </mesh>
  );
}

export function ScenarioScene({ kind }: { kind: ScenarioKind }) {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const h = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  const cfg = kind ? SCENARIO_CONFIG[kind] : null;

  return (
    <>
      <ambientLight intensity={0.2} />
      <pointLight
        position={[0, 3, 2]}
        color={cfg?.lightColor ?? "#6C63FF"}
        intensity={6}
      />
      <pointLight
        position={[-2, -2, 1]}
        color={cfg?.secondaryColor ?? "#40D9FF"}
        intensity={3}
      />

      {kind ? (
        <SceneGeometry kind={kind} reducedMotion={reducedMotion} />
      ) : (
        <NeutralScene reducedMotion={reducedMotion} />
      )}

      <Sparkles
        count={kind === "crash" ? 80 : 30}
        scale={4}
        size={kind === "crash" ? 2 : 1}
        speed={reducedMotion ? 0 : (kind === "crash" ? 1.2 : 0.3)}
        color={cfg?.sparkleColor ?? "#6C63FF"}
        opacity={0.6}
      />
    </>
  );
}
