import { NavLink, Outlet } from "react-router-dom";

export const IMPLEMENTED = new Set(["/", "/drivers", "/explain"]);

export const NAV = [
  { to: "/", label: "Overview" },
  { to: "/drivers", label: "Driver explorer" },
  { to: "/compare", label: "Driver comparison" },
  { to: "/tracks", label: "Track explorer" },
  { to: "/tyres-weather", label: "Tyre & weather lab" },
  { to: "/races", label: "Race & lap explorer" },
  { to: "/explain", label: "Explain a prediction" },
  { to: "/scenarios", label: "Scenario laboratory" },
  { to: "/methodology", label: "Data & methodology" },
];

export function Layout({ nav = NAV.filter((n) => IMPLEMENTED.has(n.to)) }: { nav?: typeof NAV }) {
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-line bg-surface-1 px-3 py-4 md:flex">
        <div className="mb-6 flex items-center gap-2 px-2">
          <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
            <circle cx="16" cy="16" r="12" fill="none" stroke="#3987e5" strokeWidth="4" />
            <circle cx="16" cy="16" r="4" fill="#d95926" />
          </svg>
          <div>
            <div className="text-sm font-semibold tracking-tight">ApexLens</div>
            <div className="text-[10px] uppercase tracking-wider text-ink-muted">Performance intelligence</div>
          </div>
        </div>
        <nav aria-label="Main" className="flex flex-col gap-0.5">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}
              className={({ isActive }) =>
                `rounded-md px-2 py-1.5 text-sm ${isActive ? "bg-surface-3 text-ink" : "text-ink-2 hover:bg-surface-2"}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <p className="mt-auto px-2 text-[10px] leading-relaxed text-ink-muted">
          Unofficial research tool. Not associated with Formula 1, the FIA or any team. Data: F1DB (CC BY 4.0) and FastF1
          timing exports.
        </p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 overflow-x-auto border-b border-line bg-surface-1 px-4 py-2 md:hidden">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}
              className={({ isActive }) => `whitespace-nowrap rounded px-2 py-1 text-xs ${isActive ? "bg-surface-3" : "text-ink-2"}`}>
              {n.label}
            </NavLink>
          ))}
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
