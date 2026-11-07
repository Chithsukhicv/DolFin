"use client";

import { useEffect, useRef, useCallback } from "react";

/**
 * A genuine Three.js 3D composition:
 * - Metallic icosphere with subdivisions
 * - Three orbital rings at different tilts
 * - Floating particle cloud
 * - Purple + cyan ambient lighting
 * - Pointer-reactive camera rotation
 * - Continuous auto-rotate
 */
export function FinancialSphere({ className }: { className?: string }) {
  const mountRef = useRef<HTMLDivElement>(null);
  const mouseRef = useRef({ x: 0, y: 0 });

  const handleMouseMove = useCallback((e: MouseEvent) => {
    const el = mountRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    mouseRef.current = {
      x: ((e.clientX - rect.left) / rect.width - 0.5) * 2,
      y: ((e.clientY - rect.top) / rect.height - 0.5) * 2,
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const el = mountRef.current;
    if (!el) return;
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const container: HTMLDivElement = el!;

    let THREE: typeof import("three");
    let renderer: import("three").WebGLRenderer;
    let animId: number;
    let scene: import("three").Scene;
    let camera: import("three").PerspectiveCamera;
    let sphere: import("three").Mesh;
    let rings: import("three").Mesh[];
    let ringSpeeds: number[] = [];
    let particles: import("three").Points;
    let clock: import("three").Clock;

    async function init() {
      THREE = await import("three");

      const W = container.clientWidth;
      const H = container.clientHeight;

      /* ----- Scene ----- */
      scene = new THREE.Scene();
      scene.fog = new THREE.FogExp2(0x050510, 0.04);

      /* ----- Camera ----- */
      camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 200);
      camera.position.set(0, 0, 7);

      /* ----- Renderer ----- */
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(W, H);
      renderer.setClearColor(0x000000, 0);
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.2;
      container.appendChild(renderer.domElement);

      /* ----- Lights ----- */
      const ambient = new THREE.AmbientLight(0x1a0a3a, 0.6);
      scene.add(ambient);

      const purpleLight = new THREE.PointLight(0x7c3aed, 80, 30);
      purpleLight.position.set(-4, 3, 5);
      scene.add(purpleLight);

      const cyanLight = new THREE.PointLight(0x22d3ee, 60, 25);
      cyanLight.position.set(5, -2, 4);
      scene.add(cyanLight);

      const backLight = new THREE.PointLight(0xa855f7, 40, 20);
      backLight.position.set(0, -5, -4);
      scene.add(backLight);

      /* ----- Main Sphere ----- */
      const sphereGeo = new THREE.IcosahedronGeometry(1.6, 4);
      const sphereMat = new THREE.MeshStandardMaterial({
        color: 0x1a1040,
        metalness: 0.95,
        roughness: 0.08,
        envMapIntensity: 1.0,
      });
      sphere = new THREE.Mesh(sphereGeo, sphereMat);
      scene.add(sphere);

      /* Wireframe overlay */
      const wireGeo = new THREE.IcosahedronGeometry(1.62, 2);
      const wireMat = new THREE.MeshBasicMaterial({
        color: 0x7c3aed,
        wireframe: true,
        opacity: 0.18,
        transparent: true,
      });
      const wire = new THREE.Mesh(wireGeo, wireMat);
      scene.add(wire);

      /* ----- Orbital Rings ----- */
      rings = [];
      ringSpeeds = [];

      const ringConfigs = [
        { radius: 2.4, tube: 0.018, color: 0xa855f7, rotX: Math.PI / 3, rotZ: 0.2, speed: 0.003 },
        { radius: 2.9, tube: 0.012, color: 0x22d3ee, rotX: Math.PI / 6, rotZ: Math.PI / 4, speed: -0.002 },
        { radius: 3.4, tube: 0.008, color: 0x4f7cff, rotX: Math.PI / 2, rotZ: -0.3, speed: 0.0015 },
      ];

      for (const cfg of ringConfigs) {
        const geo = new THREE.TorusGeometry(cfg.radius, cfg.tube, 8, 120);
        const mat = new THREE.MeshBasicMaterial({
          color: cfg.color,
          transparent: true,
          opacity: 0.7,
        });
        const ring = new THREE.Mesh(geo, mat);
        ring.rotation.x = cfg.rotX;
        ring.rotation.z = cfg.rotZ;
        ringSpeeds.push(cfg.speed);
        rings.push(ring);
        scene.add(ring);
      }

      /* Ring glow halos */
      for (const cfg of ringConfigs) {
        const geo = new THREE.TorusGeometry(cfg.radius, cfg.tube * 4, 4, 120);
        const mat = new THREE.MeshBasicMaterial({
          color: cfg.color,
          transparent: true,
          opacity: 0.08,
        });
        const halo = new THREE.Mesh(geo, mat);
        halo.rotation.x = cfg.rotX;
        halo.rotation.z = cfg.rotZ;
        scene.add(halo);
      }

      /* ----- Particles ----- */
      const count = 700;
      const positions = new Float32Array(count * 3);
      const colours = new Float32Array(count * 3);
      const purpleCol = new THREE.Color(0xa855f7);
      const cyanCol = new THREE.Color(0x22d3ee);

      for (let i = 0; i < count; i++) {
        const r = 2.0 + Math.random() * 6.0;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        positions[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = r * Math.cos(phi);

        const c = Math.random() > 0.5 ? purpleCol : cyanCol;
        colours[i * 3]     = c.r;
        colours[i * 3 + 1] = c.g;
        colours[i * 3 + 2] = c.b;
      }

      const partGeo = new THREE.BufferGeometry();
      partGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      partGeo.setAttribute("color", new THREE.BufferAttribute(colours, 3));

      const partMat = new THREE.PointsMaterial({
        size: 0.03,
        vertexColors: true,
        transparent: true,
        opacity: 0.6,
        sizeAttenuation: true,
      });
      particles = new THREE.Points(partGeo, partMat);
      scene.add(particles);

      /* ----- Clock ----- */
      clock = new THREE.Clock();

      /* ----- Animate ----- */
      function animate() {
        animId = requestAnimationFrame(animate);

        const t = clock.getElapsedTime();

        /* Sphere rotate */
        sphere.rotation.y = t * 0.18;
        sphere.rotation.x = Math.sin(t * 0.12) * 0.08;
        wire.rotation.y = t * 0.22;

        /* Rings */
        rings.forEach((ring, idx) => {
          ring.rotation.y += ringSpeeds[idx] ?? 0;
        });

        /* Particles drift */
        particles.rotation.y = t * 0.04;
        particles.rotation.x = t * 0.02;

        /* Pointer-reactive camera */
        const targetX = mouseRef.current.x * 0.5;
        const targetY = -mouseRef.current.y * 0.3;
        camera.position.x += (targetX - camera.position.x) * 0.04;
        camera.position.y += (targetY - camera.position.y) * 0.04;
        camera.lookAt(0, 0, 0);

        /* Light pulse */
        purpleLight.intensity = 70 + Math.sin(t * 0.8) * 20;
        cyanLight.intensity = 50 + Math.sin(t * 1.1 + 1) * 15;

        renderer.render(scene, camera);
      }
      animate();

      /* Resize */
      const ro = new ResizeObserver(() => {
        const w = container.clientWidth;
        const h = container.clientHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      });
      ro.observe(container);
    }

    init();
    window.addEventListener("mousemove", handleMouseMove);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("mousemove", handleMouseMove);
      if (renderer) {
        renderer.dispose();
        renderer.domElement.remove();
      }
    };
  }, [handleMouseMove]);

  return (
    <div
      ref={mountRef}
      className={className}
      style={{ background: "transparent" }}
      aria-hidden
    />
  );
}
