import type { Metadata } from "next";
import "./globals.css";
import NavBar from "@/components/NavBar";
import { ScenarioBanner } from "@/components/ScenarioBanner";
import { AuthGuard } from "@/components/AuthGuard";

export const metadata: Metadata = {
  title: "DolFin — Practice investing, build confidence",
  description:
    "A gamified investment learning platform with real-time AI coaching for women and teenagers.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {/* Lets keyboard users jump past the nav on every page. Visible only
            when focused. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-indigo-600 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
        >
          Skip to main content
        </a>
        <AuthGuard />
        <NavBar />
        <ScenarioBanner />
        <main id="main-content" className="mx-auto max-w-6xl px-4 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
