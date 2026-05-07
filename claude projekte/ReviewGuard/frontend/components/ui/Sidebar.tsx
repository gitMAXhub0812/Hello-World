import Link from "next/link";
import { LayoutDashboard, Star, FileText, Bell, Shield } from "lucide-react";

const links = [
  { href: "/",        label: "Dashboard",   icon: LayoutDashboard },
  { href: "/reviews", label: "Bewertungen", icon: Star },
  { href: "/reports", label: "Berichte",    icon: FileText },
];

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-brand text-white flex flex-col">
      <div className="p-6 border-b border-white/10">
        <div className="flex items-center gap-2">
          <Shield className="w-6 h-6 text-indigo-300" />
          <span className="font-bold text-lg">ReviewGuard</span>
        </div>
        <p className="text-xs text-white/50 mt-1">Bewertungs-Monitor</p>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm hover:bg-white/10 transition-colors"
          >
            <Icon className="w-4 h-4 text-white/60" />
            {label}
          </Link>
        ))}
      </nav>

      <div className="p-4 border-t border-white/10 text-xs text-white/40">
        v1.0.0 · ReviewGuard
      </div>
    </aside>
  );
}
