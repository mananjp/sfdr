import { ShieldAlert, ArrowRight, CheckCircle2, FileSearch, GitBranch, Download, TrendingUp, AlertTriangle, Users, ChevronRight, Zap, Database, BookOpen } from "lucide-react";

const FEATURES = [
  {
    icon: <FileSearch size={20} />,
    title: "Evidence-Linked Extraction",
    desc: "Every metric is traced back to a source file, page, and quote. No black-box AI — compliance teams see full provenance for every extracted data point.",
    tag: "Core",
    tagBg: "#eff6ff", tagColor: "#1d4ed8", borderColor: "#bfdbfe",
  },
  {
    icon: <AlertTriangle size={20} />,
    title: "Mandatory-Field Validation",
    desc: "Flags missing fields, unit mismatches, invalid numbers, and out-of-range percentages before a single word reaches the regulator.",
    tag: "Validation",
    tagBg: "#fffbeb", tagColor: "#b45309", borderColor: "#fde68a",
  },
  {
    icon: <Users size={20} />,
    title: "Reviewer Workflow",
    desc: "Approve, reject, and manually edit answers with full audit logging. Compliance officers stay in control of every final output.",
    tag: "Workflow",
    tagBg: "#f5f3ff", tagColor: "#6d28d9", borderColor: "#ddd6fe",
  },
  {
    icon: <Download size={20} />,
    title: "Audit-Ready Exports",
    desc: "Generates Markdown and HTML disclosure packages with evidence citations, summaries, and reviewer sign-off sections baked in.",
    tag: "Export",
    tagBg: "#ecfdf5", tagColor: "#065f46", borderColor: "#a7f3d0",
  },
  {
    icon: <TrendingUp size={20} />,
    title: "Progress Tracking",
    desc: "Project view shows document count and completion progress at a glance — managers always know what's done and what's pending.",
    tag: "Visibility",
    tagBg: "#f0f9ff", tagColor: "#0369a1", borderColor: "#bae6fd",
  },
  {
    icon: <GitBranch size={20} />,
    title: "Duplicate Handling & Traceability",
    desc: "Chunk hashing and uniqueness constraints prevent duplicated evidence. Versioning makes every output fully reproducible.",
    tag: "Integrity",
    tagBg: "#fff1f2", tagColor: "#be123c", borderColor: "#fecdd3",
  },
];

const USE_CASES = [
  {
    title: "PAI Statement Preparation",
    desc: "Assemble principal adverse impact disclosures from dozens of source documents — automatically, with full traceability.",
    icon: <BookOpen size={16} />,
  },
  {
    title: "Article 8 / Article 9 Reporting",
    desc: "AI accelerates drafting and review for product-level SFDR disclosures that are repetitive and template-driven.",
    icon: <FileSearch size={16} />,
  },
  {
    title: "Annual Periodic Report Drafting",
    desc: "Collate ESG metrics, top holdings, and narrative explanations into regulator-ready periodic disclosures.",
    icon: <TrendingUp size={16} />,
  },
  {
    title: "Investor / Regulator Audit Pack",
    desc: "Produce traceable outputs with evidence and reviewer sign-off that stand up to scrutiny.",
    icon: <CheckCircle2 size={16} />,
  },
];

export default function Home() {
  return (
    <div style={{ height: "100vh", overflowY: "auto", overflowX: "hidden", background: "linear-gradient(160deg, #f8fafc 0%, #f1f5ff 50%, #f8fafc 100%)", fontFamily: "'DM Sans', 'Inter', sans-serif", color: "#1e293b" }}>

      {/* Header */}
      <header style={{ background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", borderBottom: "1px solid rgba(148,163,184,0.2)", position: "sticky", top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 24px", height: 64, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 36, height: 36, background: "linear-gradient(135deg, #4f46e5, #7c3aed)", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "white", boxShadow: "0 2px 8px rgba(79,70,229,0.3)" }}>
              <ShieldAlert size={17} strokeWidth={2.5} />
            </div>
            <span style={{ fontWeight: 800, fontSize: 17, letterSpacing: "-0.5px", color: "#1e293b" }}>SFDR<span style={{ color: "#4f46e5" }}>.</span>AI</span>
          </div>
          <nav style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <a href="#features" style={{ fontSize: 13, fontWeight: 600, color: "#64748b", textDecoration: "none", padding: "6px 12px", borderRadius: 8 }}>Features</a>
            <a href="#usecases" style={{ fontSize: 13, fontWeight: 600, color: "#64748b", textDecoration: "none", padding: "6px 12px", borderRadius: 8 }}>Use Cases</a>
            <a href="/login" style={{ fontSize: 13, fontWeight: 700, color: "#475569", textDecoration: "none", padding: "7px 14px" }}>Sign In</a>
            <a href="/signup" style={{ fontSize: 13, fontWeight: 700, background: "linear-gradient(135deg, #4f46e5, #7c3aed)", color: "white", textDecoration: "none", padding: "8px 18px", borderRadius: 10, boxShadow: "0 2px 8px rgba(79,70,229,0.35)" }}>Get Started</a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section style={{ maxWidth: 1100, margin: "0 auto", padding: "80px 24px 60px", textAlign: "center" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 16px", background: "white", border: "1px solid rgba(148,163,184,0.3)", borderRadius: 999, fontSize: 12, fontWeight: 700, color: "#64748b", marginBottom: 28, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981", display: "inline-block", boxShadow: "0 0 0 2px rgba(16,185,129,0.25)", animation: "pulse 2s infinite" }}></span>
          Compliance Operations Platform · SFDR Regulation
        </div>

        <h1 style={{ fontSize: "clamp(36px, 5vw, 56px)", fontWeight: 900, letterSpacing: "-1.5px", lineHeight: 1.1, margin: "0 0 24px", color: "#0f172a" }}>
          Turn scattered ESG documents<br />
          into{" "}
          <span style={{ background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            SFDR-ready disclosures
          </span>
        </h1>

        <p style={{ fontSize: 18, color: "#64748b", fontWeight: 500, maxWidth: 640, margin: "0 auto 36px", lineHeight: 1.7 }}>
          Evidence-linked extraction. Automated rule validation. Reviewer workflows. Audit-ready exports — all in one compliance operations platform.
        </p>

        <div style={{ display: "flex", justifyContent: "center", gap: 12, flexWrap: "wrap", marginBottom: 64 }}>
          <a href="/signup" style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 700, background: "linear-gradient(135deg, #4f46e5, #7c3aed)", color: "white", textDecoration: "none", padding: "13px 28px", borderRadius: 12, boxShadow: "0 4px 16px rgba(79,70,229,0.35)" }}>
            Start Free Trial <ArrowRight size={15} />
          </a>
          <a href="#features" style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 700, background: "white", color: "#4f46e5", textDecoration: "none", padding: "13px 28px", borderRadius: 12, border: "1.5px solid rgba(79,70,229,0.25)", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
            See Features <ChevronRight size={15} />
          </a>
        </div>

        {/* Stat strip */}
        <div style={{ display: "flex", justifyContent: "center", gap: 48, flexWrap: "wrap", padding: "24px 32px", background: "white", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 16, maxWidth: 680, margin: "0 auto", boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
          {[
            { num: "14 PAIs", label: "Indicators tracked" },
            { num: "100%", label: "Evidence traceable" },
            { num: "Art. 8 & 9", label: "Disclosure types" },
            { num: "Audit-ready", label: "Export format" },
          ].map((s, i) => (
            <div key={i} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 20, fontWeight: 900, color: "#4f46e5", letterSpacing: "-0.5px" }}>{s.num}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Pitch callout */}
      <section style={{ maxWidth: 1100, margin: "0 auto 72px", padding: "0 24px" }}>
        <div style={{ background: "linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #4338ca 100%)", borderRadius: 20, padding: "40px 48px", color: "white", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", top: -40, right: -40, width: 200, height: 200, borderRadius: "50%", background: "rgba(255,255,255,0.04)" }}></div>
          <div style={{ position: "absolute", bottom: -60, left: 20, width: 280, height: 280, borderRadius: "50%", background: "rgba(255,255,255,0.03)" }}></div>
          <p style={{ fontSize: "clamp(15px, 2vw, 18px)", fontWeight: 600, lineHeight: 1.8, margin: 0, maxWidth: 780, position: "relative" }}>
            <span style={{ opacity: 0.55, fontSize: 28, fontFamily: "Georgia, serif", lineHeight: 0, verticalAlign: "middle", marginRight: 8 }}>"</span>
            SFDR reporting is still heavily manual, spreadsheet-driven, and audit-sensitive. Our platform ingests ESG documents, extracts the relevant metrics, validates them against rule checks, drafts the disclosures, and keeps a reviewer in the loop with full evidence traceability. That means <strong style={{ color: "#a5b4fc" }}>faster reporting, fewer errors, and a cleaner audit trail.</strong>
            <span style={{ opacity: 0.55, fontSize: 28, fontFamily: "Georgia, serif", lineHeight: 0, verticalAlign: "middle", marginLeft: 8 }}>"</span>
          </p>
        </div>
      </section>

      {/* Features */}
      <section id="features" style={{ maxWidth: 1100, margin: "0 auto 80px", padding: "0 24px" }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: "#4f46e5", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 12 }}>Platform Features</div>
          <h2 style={{ fontSize: "clamp(28px, 3vw, 38px)", fontWeight: 900, letterSpacing: "-1px", margin: 0, color: "#0f172a" }}>Built for compliance teams, not just AI demos</h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 20 }}>
          {FEATURES.map((f, i) => (
            <div key={i} style={{ background: "white", border: `1px solid ${f.borderColor}`, borderRadius: 16, padding: "24px 24px 20px" }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", background: f.tagBg, borderRadius: 6, fontSize: 10, fontWeight: 800, letterSpacing: "0.5px", textTransform: "uppercase", marginBottom: 14, color: f.tagColor }}>
                {f.icon} {f.tag}
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 800, margin: "0 0 10px", color: "#0f172a", letterSpacing: "-0.3px" }}>{f.title}</h3>
              <p style={{ fontSize: 14, color: "#64748b", margin: 0, lineHeight: 1.65 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Use Cases */}
      <section id="usecases" style={{ maxWidth: 1100, margin: "0 auto 80px", padding: "0 24px" }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: "#4f46e5", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 12 }}>Use Cases</div>
          <h2 style={{ fontSize: "clamp(28px, 3vw, 38px)", fontWeight: 900, letterSpacing: "-1px", margin: "0 0 14px", color: "#0f172a" }}>What companies use it for</h2>
          <p style={{ fontSize: 16, color: "#64748b", margin: 0 }}>Frame the value in business outcomes, not in AI buzzwords.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 20 }}>
          {USE_CASES.map((uc, i) => (
            <div key={i} style={{ background: "white", borderRadius: 16, border: "1px solid rgba(148,163,184,0.2)", padding: "24px 22px", boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
              <div style={{ width: 36, height: 36, background: "#f1f5ff", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "#4f46e5", marginBottom: 14 }}>
                {uc.icon}
              </div>
              <h3 style={{ fontSize: 15, fontWeight: 800, margin: "0 0 8px", color: "#0f172a", letterSpacing: "-0.3px" }}>{uc.title}</h3>
              <p style={{ fontSize: 13, color: "#64748b", margin: 0, lineHeight: 1.65 }}>{uc.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Value props */}
      <section style={{ maxWidth: 1100, margin: "0 auto 80px", padding: "0 24px" }}>
        <div style={{ background: "#f8fafc", borderRadius: 20, border: "1px solid rgba(148,163,184,0.2)", padding: "48px 48px 40px" }}>
          <div style={{ textAlign: "center", marginBottom: 40 }}>
            <h2 style={{ fontSize: "clamp(24px, 2.5vw, 32px)", fontWeight: 900, letterSpacing: "-0.8px", margin: "0 0 10px", color: "#0f172a" }}>Why compliance teams choose SFDR.AI</h2>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 24 }}>
            {[
              { title: "Cuts manual reporting time", desc: "Eliminates copy-paste work across documents and templates with AI-assisted extraction.", icon: "⏱" },
              { title: "Reduces compliance risk", desc: "Validation engine and evidence traceability prevent bad disclosures from reaching regulators.", icon: "🛡" },
              { title: "Improves audit readiness", desc: "Every disclosure traces back to a document chunk and a reviewer action — always.", icon: "📋" },
              { title: "Scales across portfolios", desc: "The same workflow reuses across multiple funds and disclosure types without extra setup.", icon: "📈" },
            ].map((v, i) => (
              <div key={i} style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
                <div style={{ fontSize: 24, lineHeight: 1, flexShrink: 0, marginTop: 2 }}>{v.icon}</div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: "#0f172a", marginBottom: 4 }}>{v.title}</div>
                  <div style={{ fontSize: 13, color: "#64748b", lineHeight: 1.6 }}>{v.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section style={{ maxWidth: 1100, margin: "0 auto 80px", padding: "0 24px" }}>
        <div style={{ background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)", borderRadius: 20, padding: "60px 48px", textAlign: "center", color: "white", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", top: -60, right: -60, width: 250, height: 250, borderRadius: "50%", background: "rgba(255,255,255,0.06)" }}></div>
          <h2 style={{ fontSize: "clamp(26px, 3vw, 36px)", fontWeight: 900, letterSpacing: "-1px", margin: "0 0 14px" }}>Ready to automate SFDR reporting?</h2>
          <p style={{ fontSize: 16, opacity: 0.8, margin: "0 0 32px", maxWidth: 520, marginLeft: "auto", marginRight: "auto", lineHeight: 1.7 }}>
            Join compliance teams that use SFDR.AI to produce regulator-ready disclosures — faster, with full evidence traceability.
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: 12, flexWrap: "wrap" }}>
            <a href="/signup" style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 800, background: "white", color: "#4f46e5", textDecoration: "none", padding: "13px 28px", borderRadius: 12 }}>
              Start Free Trial <ArrowRight size={15} />
            </a>
            <a href="#features" style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 700, background: "rgba(255,255,255,0.12)", color: "white", textDecoration: "none", padding: "13px 28px", borderRadius: 12, border: "1.5px solid rgba(255,255,255,0.25)" }}>
              Explore Features
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: "1px solid rgba(148,163,184,0.2)", background: "rgba(255,255,255,0.7)", padding: "28px 24px", textAlign: "center" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 12 }}>
          <div style={{ width: 28, height: 28, background: "linear-gradient(135deg, #4f46e5, #7c3aed)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "white" }}>
            <ShieldAlert size={14} strokeWidth={2.5} />
          </div>
          <span style={{ fontWeight: 800, fontSize: 14, color: "#1e293b" }}>SFDR<span style={{ color: "#4f46e5" }}>.</span>AI</span>
        </div>
        <p style={{ fontSize: 12, color: "#94a3b8", margin: 0, fontWeight: 600 }}>
          © {new Date().getFullYear()} SFDR.AI Compliance. All rights reserved. · Built for Article 8 & 9 Reporting
        </p>
      </footer>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800;900&display=swap');
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        a:hover { opacity: 0.88; }
        * { box-sizing: border-box; }
      `}</style>
    </div>
  );
}