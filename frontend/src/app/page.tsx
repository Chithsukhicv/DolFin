"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, type GoalTemplate, type User } from "@/lib/api";
import { getUserId, setUserId } from "@/lib/session";
import { Hero } from "@/components/Hero";

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
        setShowRecover(true);
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
    <div className="-my-8 py-10">
      <Hero />

      <div className="hairline-gradient my-16" />

      <div className="mx-auto grid max-w-4xl gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div className="animate-rise">
          <h2 className="font-display text-3xl font-extrabold tracking-tight text-white">
            Set up in
            <br />
            thirty seconds
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-muted">
            Your answers here aren&apos;t a formality. The risk appetite you pick is what
            the engine compares every trade against, and the goal you choose is what your
            Readiness Score gets measured toward.
          </p>
          <ul className="mt-6 space-y-3">
            {[
              "₹1,00,000 practice portfolio, live prices",
              "9 risk rules active from your first trade",
              "AI coach grounded in your own history",
            ].map((t) => (
              <li key={t} className="flex items-start gap-2.5 text-sm text-muted">
                <span
                  aria-hidden
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded bg-emerald-500/15 text-emerald-400"
                >
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                    <path
                      d="M2.5 6.5l2.5 2.5 4.5-5.5"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                {t}
              </li>
            ))}
          </ul>
        </div>

        <section
          id="get-started"
          className="card card-sheen animate-rise rounded-2xl p-6 sm:p-7"
          style={{ animationDelay: "100ms" }}
        >
          <div className="mb-5">
            <span className="label">new account</span>
            <h2 className="mt-2 font-display text-xl font-bold text-white">
              Create your practice account
            </h2>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <Field label="Email" htmlFor="signup-email">
              <input
                id="signup-email"
                required
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
                placeholder="you@example.com"
              />
            </Field>

            <Field label="Name" htmlFor="signup-name" optional>
              <input
                id="signup-name"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputClass}
                placeholder="What should the coach call you?"
              />
            </Field>

            <Field label="Who's learning?">
              <Choice
                options={[
                  { value: "woman", label: "Woman" },
                  { value: "teen", label: "Teenager" },
                ]}
                value={persona}
                onChange={(v) => setPersona(v as "woman" | "teen")}
                columns={2}
              />
            </Field>

            <Field
              label="Risk appetite"
              hint="Be honest — the coach uses this to flag mismatched trades."
            >
              <Choice
                options={[
                  { value: "low", label: "Low" },
                  { value: "medium", label: "Medium" },
                  { value: "high", label: "High" },
                ]}
                value={risk}
                onChange={(v) => setRisk(v as "low" | "medium" | "high")}
                columns={3}
              />
            </Field>

            <Field label="Language">
              <Choice
                options={[
                  { value: "en", label: "English" },
                  { value: "hi", label: "हिन्दी" },
                ]}
                value={language}
                onChange={(v) => setLanguage(v as "en" | "hi")}
                columns={2}
              />
            </Field>

            <Field
              label="First goal"
              htmlFor="signup-goal"
              hint="Every later decision gets measured against this."
            >
              <select
                id="signup-goal"
                value={goalKey}
                onChange={(e) => setGoalKey(e.target.value)}
                className={inputClass}
              >
                {templates.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.label} — ₹{t.suggested_amount.toLocaleString("en-IN")} in{" "}
                    {Math.round(t.suggested_horizon_months / 12)} yr
                  </option>
                ))}
              </select>
            </Field>

            {error && (
              <p
                role="alert"
                className="rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-sm text-rose-300"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="btn-primary w-full rounded-xl px-4 py-3 text-sm font-semibold"
            >
              {busy ? "Setting up your portfolio…" : "Start practising"}
            </button>
          </form>

          {/* Recovery path. Without this, clearing browser data permanently
              orphans the portfolio and all of its learning history. */}
          <div className="mt-6 border-t border-hairline pt-5">
            {!showRecover ? (
              <p className="text-sm text-muted">
                Practised here before?{" "}
                <button
                  type="button"
                  onClick={() => setShowRecover(true)}
                  className="font-semibold text-indigo-400 underline decoration-indigo-500/40 underline-offset-2 hover:text-indigo-300"
                >
                  Recover your account
                </button>
              </p>
            ) : (
              <form onSubmit={recover} className="space-y-2">
                <label htmlFor="recover-email" className="label block">
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
                    className={`${inputClass} flex-1`}
                  />
                  <button
                    type="submit"
                    disabled={recovering}
                    className="btn-ghost shrink-0 rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-50"
                  >
                    {recovering ? "Looking…" : "Continue"}
                  </button>
                </div>
                {recoverError && (
                  <p role="alert" className="text-sm text-rose-400">
                    {recoverError}
                  </p>
                )}
                <p className="text-xs text-subtle">
                  Restores your portfolio on this device. There&apos;s no password —
                  everything here is practice money.
                </p>
              </form>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

const inputClass =
  "w-full rounded-xl border border-hairline-strong bg-surface-muted px-3.5 py-2.5 text-sm " +
  "text-fg placeholder:text-subtle transition focus:border-indigo-500 focus:outline-none " +
  "focus:ring-4 focus:ring-indigo-500/15";

function Field({
  label,
  htmlFor,
  hint,
  optional,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <label htmlFor={htmlFor} className="label">
          {label}
        </label>
        {optional && <span className="text-[10px] text-subtle">optional</span>}
      </div>
      {children}
      {hint && <p className="mt-1.5 text-[11px] leading-snug text-subtle">{hint}</p>}
    </div>
  );
}

/** Segmented control. Buttons rather than radios because the visual treatment is
 *  the whole point; `aria-pressed` keeps it announced correctly. */
function Choice({
  options,
  value,
  onChange,
  columns,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  columns: 2 | 3;
}) {
  return (
    <div
      className={`grid gap-2 ${columns === 2 ? "grid-cols-2" : "grid-cols-3"}`}
      role="group"
    >
      {options.map((o) => {
        const selected = value === o.value;
        return (
          <button
            type="button"
            key={o.value}
            aria-pressed={selected}
            onClick={() => onChange(o.value)}
            className={`rounded-xl border px-3 py-2 text-sm font-medium transition ${
              selected
                ? "border-indigo-500 bg-indigo-500/15 text-indigo-200 shadow-[0_0_20px_-6px_rgb(99_102_241_/_0.5)]"
                : "border-hairline-strong text-muted hover:border-hairline-strong hover:bg-surface-hover hover:text-fg"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
