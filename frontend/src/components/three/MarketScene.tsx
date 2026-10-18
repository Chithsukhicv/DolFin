"use client";

import { useRef, useEffect, useState, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const GRID = 10;
const SPACING = 0.45;

function Bar({
  x,
  z,
  phase,
  reducedMotion,
}: {
  x: number;
  z: number;
  phase: number;
  reducedMotion: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const matRef = useRef<THREE.MeshStandardMaterial>(null);

  useFrame(({ clock }) => {
    if (!meshRef.current || !matRef.current) return;
    const t = reducedMotion ? 0 : clock.elapsedTime;
    const h = 0.1 + (Math.sin(t * 0.8 + phase) * 0.5 + 0.5) * 0.8;
    meshRef.current.scale.y = h;
    meshRef.current.position.y = h * 0.5;
    const up = Math.sin(t * 0.8 + phase) > 0;
    matRef.current.color.set(up ? "#00D6A0" : "#FF6B6B");
    matRef.current.emissive.set(up ? "#00D6A0" : "#FF6B6B");
    matRef.current.emissiveIntensity = 0.15;
  });

  return (
    <mesh ref={meshRef} position={[x, 0, z]} castShadow>
      <boxGeometry args={[0.32, 1, 0.32]} />
      <meshStandardMaterial ref={matRef} metalness={0.3} roughness={0.5} />
    </mesh>
  );
}

export function MarketScene() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const h = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  const bars = useMemo(() => {
    const result = [];
    for (let i = 0; i < GRID; i++) {
      for (let j = 0; j < GRID; j++) {
        result.push({
          x: (i - GRID / 2 + 0.5) * SPACING,
          z: (j - GRID / 2 + 0.5) * SPACING,
          phase: (i * GRID + j) * 0.63,
        });
      }
    }
    return result;
  }, []);

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[0, 4, 2]} color="#ffffff" intensity={4} />
      <pointLight position={[-3, 2, 1]} color="#40D9FF" intensity={2} />
      <pointLight position={[3, 2, 1]} color="#6C63FF" intensity={2} />

      {bars.map((b, i) => (
        <Bar key={i} {...b} reducedMotion={reducedMotion} />
      ))}

      {/* Ground plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[GRID * SPACING + 1, GRID * SPACING + 1]} />
        <meshStandardMaterial color="#0D1220" metalness={0.1} roughness={0.9} transparent opacity={0.6} />
      </mesh>
    </>
  );
}
