"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Environment, Sparkles } from "@react-three/drei";
import * as THREE from "three";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

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

// FIX: wireframe is now a stable prop — no Math.random() during render
function FloatingOrb({
  position,
  size,
  color,
  speed,
  wireframe,
  reducedMotion,
}: {
  position: [number, number, number];
  size: number;
  color: string;
  speed: number;
  wireframe: boolean;
  reducedMotion: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const startY = position[1];

  useFrame(({ clock }) => {
    if (reducedMotion || !meshRef.current) return;
    meshRef.current.rotation.x += 0.005 * speed;
    meshRef.current.rotation.y += 0.007 * speed;
    meshRef.current.position.y =
      startY + Math.sin(clock.elapsedTime * speed * 0.4) * 0.25;
  });

  return (
    <mesh ref={meshRef} position={position}>
      <icosahedronGeometry args={[size, 1]} />
      <meshStandardMaterial
        color={color}
        metalness={0.6}
        roughness={0.3}
        wireframe={wireframe}
      />
    </mesh>
  );
}

// FIX: rotate a scene group instead of mutating camera.position directly
function PointerParallax({ reducedMotion }: { reducedMotion: boolean }) {
  const groupRef = useRef<THREE.Group>(null);
  const mouse = useRef({ x: 0, y: 0 });
  const target = useRef({ x: 0, y: 0 });
  const attached = useRef(false);

  useFrame(() => {
    if (!attached.current && !reducedMotion) {
      attached.current = true;
      const onMove = (e: MouseEvent) => {
        mouse.current.x = (e.clientX / window.innerWidth - 0.5) * 0.6;
        mouse.current.y = -(e.clientY / window.innerHeight - 0.5) * 0.4;
      };
      window.addEventListener("mousemove", onMove);
    }
    if (reducedMotion || !groupRef.current) return;
    target.current.x += (mouse.current.x - target.current.x) * 0.05;
    target.current.y += (mouse.current.y - target.current.y) * 0.05;
    groupRef.current.rotation.y = target.current.x;
    groupRef.current.rotation.x = target.current.y;
  });

  return <group ref={groupRef} />;
}

// FIX: wireframe values are predetermined constants — not Math.random() at render
const ORB_CONFIGS: {
  position: [number, number, number];
  size: number;
  color: string;
  speed: number;
  wireframe: boolean;
}[] = [
  { position: [-3.2,  1.8, -2  ], size: 0.22, color: "#40D9FF", speed: 1.2, wireframe: false },
  { position: [ 3.5, -1.5, -3  ], size: 0.18, color: "#6C63FF", speed: 0.8, wireframe: true  },
  { position: [-2.8, -2.2, -1.5], size: 0.28, color: "#8B5CF6", speed: 1.5, wireframe: false },
  { position: [ 2.2,  2.5, -2.5], size: 0.20, color: "#40D9FF", speed: 0.9, wireframe: true  },
  { position: [ 0.8, -3.0, -1  ], size: 0.15, color: "#6C63FF", speed: 1.8, wireframe: false },
  { position: [-1.5,  3.2, -3  ], size: 0.25, color: "#00D6A0", speed: 0.7, wireframe: true  },
  { position: [ 4.0,  0.5, -4  ], size: 0.30, color: "#8B5CF6", speed: 1.1, wireframe: false },
];

export function HeroScene() {
  // FIX: useSyncExternalStore-based hook — no setState inside useEffect
  const reducedMotion = usePrefersReducedMotion();

  return (
    <>
      <ambientLight intensity={0.25} />
      <pointLight position={[-4, 4, 3]} color="#6C63FF" intensity={8} />
      <pointLight position={[4, -3, 2]} color="#40D9FF" intensity={6} />
      <pointLight position={[0, 0, 6]} color="#ffffff" intensity={2} />

      <TorusKnotMain reducedMotion={reducedMotion} />

      {ORB_CONFIGS.map((o, i) => (
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
      <PointerParallax reducedMotion={reducedMotion} />
    </>
  );
}
