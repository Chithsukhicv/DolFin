"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, type GoalTemplate, type User } from "@/lib/api";
import { getUserId, setUserId } from "@/lib/session";

export default function OnboardingPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Account recovery state
  const [showRecover, setShowRecover] = useState(false);
  const [recoverEmail, setRecoverEmail] = useState("");
  const [recovering, setRecovering] = useState(false);
  const [recoverError, setRecoverError] = useState<string | null>(null);

  // form state
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [persona, setPersona] = useState<"woman" | "teen">("woman");
  const [risk, setRisk] = useState<"low" | "medium" | "high">("medium");
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const [goalKey, setGoalKey] = useState<string>("");
  const [templates, setTemplates] = useState<GoalTemplate[]>([]);

  // redirect if already onboarded
  useEffect(() => {
    if (getUserId()) router.replace("/dashboard");
  }, [router]);

  // load goals on persona change
  useEffect(() => {
    let alive = true;
    api
      .get<GoalTemplate[]>(`/goals/templates?persona=${persona}`)
      .then((tpl) => {
        if (!alive) return;
        setTemplates(tpl);
        setGoalKey(tpl[0]?.key ?? "");
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [persona]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await api.post<User>("/users", {
        email,
        display_name: name || null,
        persona,
        risk_appetite: risk,
        language,
      });
      setUserId(user.id);
      if (goalKey) {
        await api.post("/goals", { user_id: user.id, template_key: goalKey });
      }
      router.replace("/dashboard");
    } catch (err) {
      // A duplicate email means the account exists but this browser has lost
      // the session, so offer recovery instead of a dead end.
      if (err instanceof ApiError && err.status === 409) {
        setError(
          "An account already uses that email. Use the recover link below to sign back in.",
        );
        setRecoverEmail(email);
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong");
      }
    } finally {
      setBusy(false);
    }
  }

  /**
   * Sign back in from an email address.
   *
   * Identity lives in localStorage, so clearing browser data used to orphan the
   * portfolio with no route back in — all of the learner's history simply became
   * unreachable. This is the recovery path until real auth is wired up.
   */
  async function recover(e: React.FormEvent) {
    e.preventDefault();
    setRecovering(true);
    setRecoverError(null);
    try {
      const user = await api.get<User>(
        `/users/by-email/${encodeURIComponent(recoverEmail.trim().toLowerCase())}`,
      );
      setUserId(user.id);
      router.replace("/dashboard");
    } catch (err) {
      setRecoverError(
        err instanceof ApiError && err.status === 404
          ? "No account found with that email."
          : err instanceof Error
          ? err.message
          : "Couldn't recover that account.",
      );
    } finally {
      setRecovering(false);
    }
  }

  return (
    <div className="grid gap-10 md:grid-cols-2">
      <section>
        <h1 className="mb-3 text-4xl font-semibold tracking-tight">
          Practice investing.
          <br />
          <span className="text-indigo-600">Build the confidence to start.</span>
        </h1>
        <p className="mb-6 text-slate-600">
          DolFin gives you a virtual <strong>₹1L</strong> portfolio with real NSE prices,
          a coach that explains every decision in plain language, and a panic-sell
          training scenario so you stay calm when markets fall.
        </p>

        <ul className="space-y-3 text-sm text-slate-700">
          <li className="flex gap-2">
            <span className="text-indigo-600">●</span>
            <span><strong>Behavioural Intervention Engine</strong> — warnings before risky trades.</span>
          </li>
          <li className="flex gap-2">
            <span className="text-indigo-600">●</span>
            <span>
              <strong>Investment Readiness Score</strong> — a 0-100 grade for when
              you&apos;re ready for real money.
            </span>
          </li>
          <li className="flex gap-2">
            <span className="text-indigo-600">●</span>
            <span><strong>Crash simulator</strong> — practise patience during a -30% drop.</span>
          </li>
        </ul>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-xl font-semibold">Get started</h2>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Email</label>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-indigo-500 focus:ring-2"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Name (optional)</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-indigo-500 focus:ring-2"
              placeholder="Your name"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Who are you?</label>
            <div className="grid grid-cols-2 gap-2">
              {(["woman", "teen"] as const).map((p) => (
                <button
                  type="button"
                  key={p}
                  onClick={() => setPersona(p)}
                  className={`rounded-lg border px-3 py-2 text-sm capitalize transition ${
                    persona === p
                      ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                      : "border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Risk appetite</label>
            <div className="grid grid-cols-3 gap-2">
              {(["low", "medium", "high"] as const).map((r) => (
                <button
                  type="button"
                  key={r}
                  onClick={() => setRisk(r)}
                  className={`rounded-lg border px-3 py-2 text-sm capitalize ${
                    risk === r
                      ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                      : "border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Language</label>
            <div className="grid grid-cols-2 gap-2">
              {(["en", "hi"] as const).map((l) => (
                <button
                  type="button"
                  key={l}
                  onClick={() => setLanguage(l)}
                  className={`rounded-lg border px-3 py-2 text-sm ${
                    language === l
                      ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                      : "border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {l === "en" ? "English" : "हिन्दी (Hindi)"}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Pick your first goal</label>
            <select
              value={goalKey}
              onChange={(e) => setGoalKey(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none ring-indigo-500 focus:ring-2"
            >
              {templates.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label} — ₹{t.suggested_amount.toLocaleString("en-IN")} in {Math.round(t.suggested_horizon_months / 12)} yr
                </option>
              ))}
            </select>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 font-medium text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy ? "Setting up..." : "Start practising"}
          </button>
        </form>

        {/* Recovery path. Without this, clearing browser data permanently
            orphans the portfolio and all of its learning history. */}
        <div className="mt-6 border-t border-slate-200 pt-5">
          {!showRecover ? (
            <p className="text-sm text-slate-600">
              Already practised here before?{" "}
              <button
                type="button"
                onClick={() => setShowRecover(true)}
                className="font-medium text-indigo-600 underline hover:text-indigo-700"
              >
                Recover it
              </button>
            </p>
          ) : (
            <form onSubmit={recover} className="space-y-2">
              <label
                htmlFor="recover-email"
                className="block text-xs font-medium text-slate-600"
              >
                Email you signed up with
              </label>
              <div className="flex gap-2">
                <input
                  id="recover-email"
                  type="email"
                  required
                  value={recoverEmail}
                  onChange={(e) => setRecoverEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-indigo-500 focus:ring-2"
                />
                <button
                  type="submit"
                  disabled={recovering}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {recovering ? "Looking..." : "Continue"}
                </button>
              </div>
              {recoverError && (
                <p role="alert" className="text-sm text-red-600">
                  {recoverError}
                </p>
              )}
              <p className="text-xs text-slate-500">
                This restores your portfolio on this device. There&apos;s no password yet —
                everything here is practice money.
              </p>
            </form>
          )}
        </div>
      </section>
    </div>
  );
}
