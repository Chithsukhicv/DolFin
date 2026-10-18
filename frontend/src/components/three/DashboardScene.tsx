"use client";

import { useRef, useEffect, useState, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, Sparkles } from "@react-three/drei";
import * as THREE from "three";

function ScoreRing({
  radius,
  tube,
  color,
  fillFraction,
  rotationSpeed,
  tiltX,
  reducedMotion,
}: {
  radius: number;
  tube: number;
  color: string;
  fillFraction: number;
  rotationSpeed: number;
  tiltX: number;
  reducedMotion: boolean;
}) {
  const trackRef = useRef<THREE.Mesh>(null);
  const fillRef = useRef<THREE.Mesh>(null);

  // Build fill arc geometry
  const fillGeo = useMemo(() => {
    const curve = new THREE.TorusGeometry(radius, tube, 16, 100, fillFraction * Math.PI * 2);
    return curve;
  }, [radius, tube, fillFraction]);

  useFrame((_, delta) => {
    if (reducedMotion) return;
    if (trackRef.current) trackRef.current.rotation.z += delta * rotationSpeed;
    if (fillRef.current) fillRef.current.rotation.z += delta * rotationSpeed;
  });

  return (
    <group rotation={[tiltX, 0, 0]}>
      {/* Track ring */}
      <mesh ref={trackRef}>
        <torusGeometry args={[radius, tube * 0.4, 16, 100]} />
        <meshStandardMaterial color="#1a1d23" metalness={0.3} roughness={0.7} transparent opacity={0.6} />
      </mesh>
      {/* Fill arc */}
      <mesh ref={fillRef} geometry={fillGeo}>
        <meshStandardMaterial
          color={color}
          metalness={0.7}
          roughness={0.15}
          emissive={color}
          emissiveIntensity={0.4}
        />
      </mesh>
    </group>
  );
}

function OrbitingCube({
  orbitRadius,
  orbitSpeed,
  orbitOffset,
  color,
  size,
  reducedMotion,
}: {
  orbitRadius: number;
  orbitSpeed: number;
  orbitOffset: number;
  color: string;
  size: number;
  reducedMotion: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (reducedMotion || !groupRef.current) return;
    const t = clock.elapsedTime * orbitSpeed + orbitOffset;
    groupRef.current.position.x = Math.cos(t) * orbitRadius;
    groupRef.current.position.z = Math.sin(t) * orbitRadius;
    groupRef.current.rotation.x += 0.02;
    groupRef.current.rotation.y += 0.015;
  });

  return (
    <group ref={groupRef}>
      <mesh>
        <boxGeometry args={[size, size, size]} />
        <meshStandardMaterial color={color} metalness={0.8} roughness={0.2} />
      </mesh>
    </group>
  );
}

export function DashboardScene({ score = 0 }: { score: number }) {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const h = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  const clampedScore = Math.max(0, Math.min(100, score));
  const ringColor =
    clampedScore >= 80 ? "#00D6A0" : clampedScore >= 50 ? "#6C63FF" : "#FF6B6B";

  return (
    <>
      <ambientLight intensity={0.3} />
      <pointLight position={[0, 4, 3]} color="#6C63FF" intensity={6} />
      <pointLight position={[3, -2, 2]} color="#40D9FF" intensity={4} />

      {/* Three concentric score rings */}
      <ScoreRing
        radius={2.2} tube={0.08} color={ringColor}
        fillFraction={clampedScore / 100} rotationSpeed={0.15}
        tiltX={0.2} reducedMotion={reducedMotion}
      />
      <ScoreRing
        radius={1.7} tube={0.06} color="#6C63FF"
        fillFraction={Math.min(1, clampedScore / 80)} rotationSpeed={-0.2}
        tiltX={-0.3} reducedMotion={reducedMotion}
      />
      <ScoreRing
        radius={1.2} tube={0.05} color="#40D9FF"
        fillFraction={Math.min(1, clampedScore / 60)} rotationSpeed={0.3}
        tiltX={0.5} reducedMotion={reducedMotion}
      />

      {/* Score label in centre */}
      <Html center distanceFactor={6}>
        <div className="text-center select-none pointer-events-none">
          <div
            className="font-mono text-4xl font-black"
            style={{ color: ringColor, textShadow: `0 0 20px ${ringColor}80` }}
          >
            {clampedScore.toFixed(0)}
          </div>
          <div className="text-xs font-semibold uppercase tracking-widest text-[#9BA7BC]">
            Readiness
          </div>
        </div>
      </Html>

      {/* Orbiting cubes */}
      {[
        { orbitRadius: 3.0, orbitSpeed: 0.4, orbitOffset: 0, color: "#6C63FF", size: 0.14 },
        { orbitRadius: 2.8, orbitSpeed: -0.3, orbitOffset: 2.1, color: "#40D9FF", size: 0.10 },
        { orbitRadius: 3.3, orbitSpeed: 0.25, orbitOffset: 4.2, color: "#00D6A0", size: 0.12 },
        { orbitRadius: 2.5, orbitSpeed: -0.5, orbitOffset: 1.0, color: "#8B5CF6", size: 0.09 },
      ].map((o, i) => (
        <OrbitingCube key={i} {...o} reducedMotion={reducedMotion} />
      ))}

      <Sparkles
        count={30}
        scale={5}
        size={0.8}
        speed={reducedMotion ? 0 : 0.2}
        color="#6C63FF"
        opacity={0.5}
      />
    </>
  );
}
