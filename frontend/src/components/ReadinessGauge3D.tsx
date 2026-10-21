"use client";

import { useEffect, useRef } from "react";

interface Props {
  score: number;
  size?: number;
  label?: string;
}

/**
 * A circular SVG readiness gauge with animated neon stroke.
 * Deliberately SVG rather than canvas so it can be Server Component–safe.
 */
export function ReadinessGauge({ score, size = 220, label = "Readiness" }: Props) {
  const fillRef = useRef<SVGCircleElement>(null);

  const r = (size / 2) * 0.72;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  // Arc covers 270° (from 135° to 405° / starting bottom-left, going clockwise to bottom-right)
  const arc = circumference * 0.75;
  const offset = arc - (arc * Math.min(100, Math.max(0, score))) / 100;

  const hue = score >= 70 ? "#10D9A0" : score >= 40 ? "#A855F7" : "#F25767";

  useEffect(() => {
    const el = fillRef.current;
    if (!el) return;
    // Brief delay so the animation is visible on mount
    el.style.strokeDashoffset = String(arc);
    requestAnimationFrame(() => {
      el.style.transition = "stroke-dashoffset 1.4s cubic-bezier(0.16, 1, 0.3, 1)";
      el.style.strokeDashoffset = String(offset);
    });
  }, [offset, arc]);

  // Rotate so arc starts bottom-left
  const rotation = 135;

  return (
    <div className="relative inline-flex flex-col items-center">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-label={`${label}: ${score} out of 100`}
        style={{ overflow: "visible" }}
      >
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#7C3AED" />
            <stop offset="50%" stopColor="#A855F7" />
            <stop offset="100%" stopColor="#22D3EE" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Track */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="rgb(124 58 237 / 0.15)"
          strokeWidth={size * 0.055}
          strokeLinecap="round"
          strokeDasharray={`${arc} ${circumference}`}
          style={{ transform: `rotate(${rotation}deg)`, transformOrigin: `${cx}px ${cy}px` }}
        />

        {/* Animated fill */}
        <circle
          ref={fillRef}
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="url(#gaugeGradient)"
          strokeWidth={size * 0.055}
          strokeLinecap="round"
          strokeDasharray={`${arc} ${circumference}`}
          strokeDashoffset={offset}
          filter="url(#glow)"
          style={{ transform: `rotate(${rotation}deg)`, transformOrigin: `${cx}px ${cy}px` }}
        />

        {/* Centre text */}
        <text
          x={cx}
          y={cy - size * 0.04}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={hue}
          fontSize={size * 0.22}
          fontWeight="700"
          fontFamily="var(--font-mono-stack), monospace"
          letterSpacing="-2"
        >
          {score > 0 ? Math.round(score) : "—"}
        </text>
        <text
          x={cx}
          y={cy + size * 0.14}
          textAnchor="middle"
          fill="rgb(161 161 181)"
          fontSize={size * 0.068}
          fontFamily="var(--font-mono-stack), monospace"
          letterSpacing="2"
        >
          / 100
        </text>

        {/* Label at bottom of arc */}
        <text
          x={cx}
          y={size - size * 0.08}
          textAnchor="middle"
          fill="rgb(107 107 133)"
          fontSize={size * 0.058}
          fontFamily="var(--font-mono-stack), monospace"
          letterSpacing="2"
        >
          {label.toUpperCase()}
        </text>
      </svg>
    </div>
  );
}
