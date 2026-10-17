"use client";

// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference types="@react-three/fiber" />

import { useRef, useState, useMemo, useEffect } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";

interface Sector {
  name: string;
  value: number;
  color: string;
}

function ExtrudedSlice({
  startAngle,
  endAngle,
  color,
  label,
  percent,
  isHovered,
  onHover,
  onUnhover,
  reducedMotion,
}: {
  startAngle: number;
  endAngle: number;
  color: string;
  label: string;
  percent: number;
  isHovered: boolean;
  onHover: () => void;
  onUnhover: () => void;
  reducedMotion: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const targetY = useRef(0);

  // Build 2D shape (arc wedge) then extrude
  const geometry = useMemo(() => {
    const shape = new THREE.Shape();
    const innerR = 0.8;
    const outerR = 2.2;
    const segments = 40;
    const step = (endAngle - startAngle) / segments;

    // Outer arc forward
    shape.moveTo(Math.cos(startAngle) * outerR, Math.sin(startAngle) * outerR);
    for (let i = 1; i <= segments; i++) {
      const a = startAngle + step * i;
      shape.lineTo(Math.cos(a) * outerR, Math.sin(a) * outerR);
    }
    // Inner arc backward
    for (let i = segments; i >= 0; i--) {
      const a = startAngle + step * i;
      shape.lineTo(Math.cos(a) * innerR, Math.sin(a) * innerR);
    }
    shape.closePath();

    return new THREE.ExtrudeGeometry(shape, {
      depth: 0.42,
      bevelEnabled: true,
      bevelThickness: 0.04,
      bevelSize: 0.03,
      bevelSegments: 4,
    });
  }, [startAngle, endAngle]);

  useEffect(() => {
    return () => geometry.dispose();
  }, [geometry]);

  useFrame((_, delta) => {
    if (!meshRef.current) return;
    targetY.current = isHovered ? 0.35 : 0;
    meshRef.current.position.y +=
      (targetY.current - meshRef.current.position.y) * (reducedMotion ? 1 : 8 * delta);
  });

  const midAngle = (startAngle + endAngle) / 2;
  const labelR = 2.8;

  return (
    <group>
      <mesh
        ref={meshRef}
        geometry={geometry}
        position={[0, 0, -0.21]}
        rotation={[-Math.PI / 2, 0, 0]}
        onPointerEnter={(e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); onHover(); }}
        onPointerLeave={() => onUnhover()}
      >
        <meshStandardMaterial
          color={color}
          metalness={0.5}
          roughness={0.3}
          emissive={color}
          emissiveIntensity={isHovered ? 0.3 : 0.05}
        />
      </mesh>

      {isHovered && (
        <Html
          position={[
            Math.cos(midAngle) * labelR,
            0.5,
            Math.sin(midAngle) * labelR,
          ]}
          center
        >
          <div
            className="rounded-xl border px-3 py-1.5 text-center text-sm"
            style={{
              background: "rgba(13,18,32,0.92)",
              borderColor: color,
              color: "#F5F7FF",
              boxShadow: `0 0 16px ${color}40`,
              pointerEvents: "none",
              whiteSpace: "nowrap",
            }}
          >
            <div className="font-bold">{label}</div>
            <div className="font-mono text-lg" style={{ color }}>
              {percent.toFixed(1)}%
            </div>
          </div>
        </Html>
      )}
    </group>
  );
}

function AutoRotate({ reducedMotion }: { reducedMotion: boolean }) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (reducedMotion || !groupRef.current) return;
    // Slow auto-rotate when nothing hovered
    groupRef.current.rotation.y += 0.003;
  });

  return <group ref={groupRef} />;
}

export function PortfolioScene({
  sectors,
}: {
  sectors: Sector[];
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const h = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  const total = sectors.reduce((s, x) => s + x.value, 0);

  // Build angle ranges
  const slices = useMemo(() => {
    let angle = 0;
    return sectors.map((s) => {
      const frac = s.value / (total || 1);
      const start = angle;
      const end = angle + frac * Math.PI * 2;
      angle = end;
      return { ...s, startAngle: start, endAngle: end, percent: frac * 100 };
    });
  }, [sectors, total]);

  if (sectors.length === 0) {
    return (
      <>
        <ambientLight intensity={0.4} />
        <Html center>
          <p className="text-sm text-[#9BA7BC]">No holdings yet</p>
        </Html>
      </>
    );
  }

  return (
    <>
      <ambientLight intensity={0.3} />
      <pointLight position={[0, 5, 3]} color="#ffffff" intensity={5} />
      <pointLight position={[3, 2, 2]} color="#6C63FF" intensity={4} />
      <pointLight position={[-3, -2, 2]} color="#40D9FF" intensity={3} />

      <group>
        {slices.map((s) => (
          <ExtrudedSlice
            key={s.name}
            startAngle={s.startAngle}
            endAngle={s.endAngle}
            color={s.color}
            label={s.name}
            percent={s.percent}
            isHovered={hovered === s.name}
            onHover={() => setHovered(s.name)}
            onUnhover={() => setHovered(null)}
            reducedMotion={reducedMotion}
          />
        ))}
      </group>
    </>
  );
}
