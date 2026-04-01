import { Link, useLocation } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { LayoutDashboard, FileText, Users, BarChart2, Sun, Moon } from "lucide-react";
import { useState, useEffect } from "react";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/bills", label: "Bill Explorer", icon: FileText },
  { href: "/members", label: "Members", icon: Users },
  { href: "/parties", label: "Party Split", icon: BarChart2 },
];

export default function Sidebar() {
  const [location] = useHashLocation();
  const [dark, setDark] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle("light", !dark);
  }, [dark]);

  return (
    <aside className="w-56 flex-shrink-0 border-r border-border bg-card flex flex-col h-screen">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <svg viewBox="0 0 28 28" width="28" height="28" aria-label="Congress Vote Tracker">
            <rect x="3" y="14" width="4" height="11" rx="1" fill="hsl(var(--dem))" />
            <rect x="9" y="9" width="4" height="16" rx="1" fill="hsl(var(--dem) / 0.6)" />
            <rect x="15" y="4" width="4" height="21" rx="1" fill="hsl(var(--rep) / 0.6)" />
            <rect x="21" y="11" width="4" height="14" rx="1" fill="hsl(var(--rep))" />
            <line x1="3" y1="26" x2="25" y2="26" stroke="hsl(var(--border))" strokeWidth="1.5" />
          </svg>
          <div>
            <p className="text-xs font-semibold leading-tight text-foreground">Congress</p>
            <p className="text-xs text-muted-foreground leading-tight">Vote Tracker</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = location === href || (href !== "/" && location.startsWith(href));
          return (
            <Link key={href} href={href}>
              <a
                data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-primary/15 text-primary font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                }`}
              >
                <Icon size={16} />
                {label}
              </a>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border flex items-center justify-between">
        <span className="text-xs text-muted-foreground">119th Congress</span>
        <button
          data-testid="theme-toggle"
          onClick={() => setDark(!dark)}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Toggle theme"
        >
          {dark ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </aside>
  );
}
