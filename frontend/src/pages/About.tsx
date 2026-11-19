import { Card, PageHeader } from "../components/ui";

export const AUTHOR = {
  name: "Akash Saha",
  headline: "MS-R CSE, IIT Kanpur · AI/ML & HPC",
  repo: "https://github.com/akashsaha477/F1",
};

export const SOCIALS = [
  { name: "GitHub", handle: "akashsaha477", url: "https://github.com/akashsaha477", note: "Code for ApexLens and my other projects" },
  { name: "LinkedIn", handle: "akashsaha477", url: "https://www.linkedin.com/in/akashsaha477/", note: "Work, research and project updates" },
  { name: "X", handle: "@Saha477Saha", url: "https://x.com/Saha477Saha", note: "F1 takes and model predictions" },
  { name: "Instagram", handle: "@a_visionary_shutterbug", url: "https://www.instagram.com/a_visionary_shutterbug/", note: "Photography" },
  { name: "Facebook", handle: "akash.saha.9085", url: "https://www.facebook.com/akash.saha.9085/", note: "Say hi" },
];

const BUILT_WITH = ["Python", "pandas", "LightGBM", "SHAP", "statsmodels", "FastAPI", "React", "TypeScript", "ECharts", "Docker", "Azure"];

export default function AboutPage() {
  return (
    <div className="space-y-5">
      <PageHeader title="About"
        description="ApexLens is a personal project: explainable Formula 1 analytics on real timing data, and a prediction game where you can try to beat the model." />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2" title={`Built by ${AUTHOR.name}`} subtitle={AUTHOR.headline}>
          <p className="text-sm text-ink-2">
            I started with one question — how much of a lap time is the driver and how much is the car — and kept going:
            driver profiles, lap-pace models with honest evaluation, a race week planner, and the prediction game. Everything is
            open source, including the data sources and every evaluation.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <a href={AUTHOR.repo} target="_blank" rel="noreferrer"
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:brightness-110">
              View the code on GitHub ↗
            </a>
            <span className="text-xs text-ink-muted">Issues and pull requests welcome.</span>
          </div>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {BUILT_WITH.map((t) => (
              <span key={t} className="rounded border border-line bg-surface-2 px-1.5 py-0.5 text-[11px] text-ink-2">{t}</span>
            ))}
          </div>
        </Card>

        <Card title="Find me">
          <ul className="space-y-2">
            {SOCIALS.map((s) => (
              <li key={s.name}>
                <a href={s.url} target="_blank" rel="noreferrer"
                  className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2 hover:bg-surface-2">
                  <span>
                    <span className="block text-sm font-medium text-ink">{s.name}</span>
                    <span className="block text-xs text-ink-muted">{s.note}</span>
                  </span>
                  <span className="text-xs text-ink-2">{s.handle} ↗</span>
                </a>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Data and credits">
        <p className="text-sm text-ink-2">
          Results and identities from <a className="text-accent hover:underline" href="https://github.com/f1db/f1db" target="_blank" rel="noreferrer">F1DB</a> (CC BY 4.0);
          lap timing, tyres, weather and telemetry from the public FastF1 exports by{" "}
          <a className="text-accent hover:underline" href="https://github.com/TracingInsights" target="_blank" rel="noreferrer">TracingInsights</a>;
          forecasts from Open-Meteo. Hosted on Azure for Students through the GitHub Student Developer Pack.
        </p>
        <p className="mt-2 text-xs text-ink-muted">
          Unofficial research project. Not associated with Formula 1, the FIA or any team. F1 and FORMULA ONE are trademarks of
          Formula One Licensing B.V.
        </p>
      </Card>
    </div>
  );
}
