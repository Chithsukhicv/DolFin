"use client";

// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference types="@react-three/fiber" />

import { useRef, useEffect, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Sparkles } from "@react-three/drei";
import * as THREE from "three";

function CoreSphere({
  isThinking,
  reducedMotion,
}: {
  isThinking: boolean;
  reducedMotion: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const scaleRef = useRef(1);

  useFrame(({ clock }, delta) => {
    if (!meshRef.current) return;
    const speed = isThinking ? 2.5 : 0.6;
    if (!reducedMotion) {
      meshRef.current.rotation.y += delta * speed;
      meshRef.current.rotation.x += delta * speed * 0.4;
    }
    // Pulse scale when thinking
    const pulse = isThinking
      ? 1 + Math.sin(clock.elapsedTime * 6) * 0.06
      : 1 + Math.sin(clock.elapsedTime * 1.5) * 0.02;
    scaleRef.current += (pulse - scaleRef.current) * 0.1;
    meshRef.current.scale.setScalar(scaleRef.current);
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.7, 32, 32]} />
      <meshStandardMaterial
        color="#6C63FF"
        metalness={0.4}
        roughness={0.5}
        emissive="#6C63FF"
        emissiveIntensity={isThinking ? 0.5 : 0.15}
      />
    </mesh>
  );
}

function OrbitRing({
  radius,
  tube,
  tilt,
  speed,
  color,
  reducedMotion,
}: {
  radius: number;
  tube: number;
  tilt: [number, number, number];
  speed: number;
  color: string;
  reducedMotion: boolean;
}) {
  const ref = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (reducedMotion || !ref.current) return;
    ref.current.rotation.z += delta * speed;
  });

  return (
    <mesh ref={ref} rotation={tilt}>
      <torusGeometry args={[radius, tube, 8, 64]} />
      <meshStandardMaterial
        color={color}
        wireframe
        metalness={0.8}
        roughness={0.2}
        emissive={color}
        emissiveIntensity={0.3}
      />
    </mesh>
  );
}

export function CoachOrbScene({ isThinking = false }: { isThinking?: boolean }) {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const h = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  return (
    <>
      <ambientLight intensity={0.2} />
      <pointLight position={[0, 2, 2]} color="#40D9FF" intensity={5} />
      <pointLight position={[0, -2, 1]} color="#8B5CF6" intensity={4} />

      <CoreSphere isThinking={isThinking} reducedMotion={reducedMotion} />

      <OrbitRing
        radius={1.1} tube={0.025}
        tilt={[Math.PI / 4, 0, 0]}
        speed={0.8} color="#40D9FF"
        reducedMotion={reducedMotion}
      />
      <OrbitRing
        radius={1.3} tube={0.02}
        tilt={[-Math.PI / 4, Math.PI / 6, 0]}
        speed={-0.6} color="#8B5CF6"
        reducedMotion={reducedMotion}
      />
      <OrbitRing
        radius={0.95} tube={0.018}
        tilt={[0, Math.PI / 3, Math.PI / 4]}
        speed={1.1} color="#6C63FF"
        reducedMotion={reducedMotion}
      />

      <Sparkles
        count={isThinking ? 60 : 25}
        scale={3.5}
        size={isThinking ? 1.5 : 0.8}
        speed={reducedMotion ? 0 : (isThinking ? 0.8 : 0.25)}
        color="#40D9FF"
        opacity={0.7}
      />
    </>
  );
}
