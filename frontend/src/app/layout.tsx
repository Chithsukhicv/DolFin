import type { Metadata, Viewport } from "next";
import { JetBrains_Mono, Sora, Inter } from "next/font/google";
import "./globals.css";
import NavBar from "@/components/NavBar";
import { Footer } from "@/components/Footer";
import { ScenarioBanner } from "@/components/ScenarioBanner";
import { AuthGuard } from "@/components/AuthGuard";

/**
 * Three faces, each doing a specific job.
 *
 * Sora for display: geometric, slightly condensed, and it holds up at the very
 * large sizes the hero uses — which is where a generic UI font starts looking
 * like a slide deck.
 *
 * Inter for body copy, because it is the most legible thing available at 13-15px
 * and this app has a lot of explanatory prose.
 *
 * JetBrains Mono for every number. Money should look like data, and a mono face
 * guarantees the tabular alignment that stops a portfolio total jittering
 * sideways as it updates.
 */
const sora = Sora({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-display-stack",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans-stack",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-mono-stack",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "DolFin — Learn to invest without losing money",
    template: "%s · DolFin",
  },
  description:
    "A behavioural investing simulator for first-time Indian investors. Live NSE prices, "
    + "simulated money, nine risk rules, and an AI coach grounded in your own trade history.",
  keywords: [
    "investing simulator", "NSE", "paper trading", "behavioural finance",
    "investment education", "India", "RAG", "AI coach",
  ],
  openGraph: {
    title: "DolFin — Learn to invest without losing money",
    description:
      "Live market prices, simulated cash, and a coach that catches panic-selling "
      + "before it costs you anything.",
    type: "website",
  },
};

// themeColor belongs on `viewport`, not `metadata` — Next warns if it is on the
// latter. Matches --bg so mobile browser chrome blends into the page.
export const viewport: Viewport = {
  themeColor: "#06070d",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${sora.variable} ${inter.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <body className="flex min-h-screen flex-col antialiased">
        {/* Lets keyboard users jump past the nav on every page. Visible only
            when focused. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-indigo-500 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
        >
          Skip to main content
        </a>

        {/* Fixed blueprint grid behind everything. Fixed rather than scrolling so
            content moves against a stable ground, which reads as depth. */}
        <div
          aria-hidden
          className="grid-bg pointer-events-none fixed inset-0 z-0 opacity-70"
        />
        {/* Vignette, so the grid fades out at the edges instead of stopping. */}
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 z-0"
          style={{
            background:
              "radial-gradient(120% 80% at 50% 0%, transparent 40%, rgb(6 7 13 / 0.85) 100%)",
          }}
        />

        <div className="relative z-10 flex min-h-screen flex-col">
          <AuthGuard />
          <NavBar />
          <ScenarioBanner />
          <main id="main-content" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
            {children}
          </main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
