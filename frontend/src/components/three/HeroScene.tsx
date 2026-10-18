"use client";

import { useRef, useEffect, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Environment, Sparkles } from "@react-three/drei";
import * as THREE from "three";

function TorusKnotMain({ reducedMotion }: { reducedMotion: boolean }) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (reducedMotion || !meshRef.current) return;
    meshRef.current.rotation.x += delta * 0.12;
    meshRef.current.rotation.y += delta * 0.18;
  });

  return (
    <mesh ref={meshRef} position={[0, 0, 0]}>
      <torusKnotGeometry args={[1.1, 0.38, 180, 24, 2, 3]} />
      <meshStandardMaterial
        color="#6C63FF"
        metalness={0.85}
        roughness={0.12}
        envMapIntensity={1.5}
      />
    </mesh>
  );
}

function FloatingOrb({
  position,
  size,
  color,
  speed,
  reducedMotion,
}: {
  position: [number, number, number];
  size: number;
  color: string;
  speed: number;
  reducedMotion: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const startY = position[1];

  useFrame(({ clock }) => {
    if (reducedMotion || !meshRef.current) return;
    meshRef.current.rotation.x += 0.005 * speed;
    meshRef.current.rotation.y += 0.007 * speed;
    meshRef.current.position.y = startY + Math.sin(clock.elapsedTime * speed * 0.4) * 0.25;
  });

  return (
    <mesh ref={meshRef} position={position}>
      <icosahedronGeometry args={[size, 1]} />
      <meshStandardMaterial
        color={color}
        metalness={0.6}
        roughness={0.3}
        wireframe={Math.random() > 0.5}
      />
    </mesh>
  );
}

function CameraRig({ reducedMotion }: { reducedMotion: boolean }) {
  const { camera } = useThree();
  const mouse = useRef({ x: 0, y: 0 });

  useEffect(() => {
    if (reducedMotion) return;
    const onMove = (e: MouseEvent) => {
      mouse.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      mouse.current.y = -(e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [reducedMotion]);

  useFrame(() => {
    if (reducedMotion) return;
    camera.position.x += (mouse.current.x * 0.8 - camera.position.x) * 0.05;
    camera.position.y += (mouse.current.y * 0.5 - camera.position.y) * 0.05;
    camera.lookAt(0, 0, 0);
  });

  return null;
}

export function HeroScene() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const orbs = [
    { position: [-3.2, 1.8, -2] as [number, number, number], size: 0.22, color: "#40D9FF", speed: 1.2 },
    { position: [3.5, -1.5, -3] as [number, number, number], size: 0.18, color: "#6C63FF", speed: 0.8 },
    { position: [-2.8, -2.2, -1.5] as [number, number, number], size: 0.28, color: "#8B5CF6", speed: 1.5 },
    { position: [2.2, 2.5, -2.5] as [number, number, number], size: 0.20, color: "#40D9FF", speed: 0.9 },
    { position: [0.8, -3, -1] as [number, number, number], size: 0.15, color: "#6C63FF", speed: 1.8 },
    { position: [-1.5, 3.2, -3] as [number, number, number], size: 0.25, color: "#00D6A0", speed: 0.7 },
    { position: [4, 0.5, -4] as [number, number, number], size: 0.30, color: "#8B5CF6", speed: 1.1 },
  ];

  return (
    <>
      <ambientLight intensity={0.25} />
      <pointLight position={[-4, 4, 3]} color="#6C63FF" intensity={8} />
      <pointLight position={[4, -3, 2]} color="#40D9FF" intensity={6} />
      <pointLight position={[0, 0, 6]} color="#ffffff" intensity={2} />

      <TorusKnotMain reducedMotion={reducedMotion} />

      {orbs.map((o, i) => (
        <FloatingOrb key={i} {...o} reducedMotion={reducedMotion} />
      ))}

      <Sparkles
        count={60}
        scale={8}
        size={1.2}
        speed={reducedMotion ? 0 : 0.3}
        color="#40D9FF"
        opacity={0.6}
      />

      <Environment preset="night" />
      <CameraRig reducedMotion={reducedMotion} />
    </>
  );
}
