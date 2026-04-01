import { useVotes, useMembers, useMemberVotes } from "@/hooks/useData";
import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from "recharts";
import { Vote, Users, Building2, TrendingUp } from "lucide-react";

const DEM_COLOR = "hsl(213,80%,55%)";
const REP_COLOR = "hsl(0,72%,52%)";

function KPI({ label, value, icon: Icon, sub }: { label: string; value: string | number; icon: any; sub?: string }) {
  return (
    <div data-testid={`kpi-${label.toLowerCase().replace(/\s+/g,"-")}`} className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground uppercase tracking-wide">{label}</span>
        <Icon size={15} className="text-muted-foreground" />
      </div>
      <div className="text-2xl font-bold text-foreground tabular-nums">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

export default function Overview() {
  const { data: votes = [], isLoading: vLoading } = useVotes();
  const { data: members = [], isLoading: mLoading } = useMembers();
  const { data: memberVotes = [] } = useMemberVotes();

  const stats = useMemo(() => {
    const senate = votes.filter(v => v.chamber === "senate").length;
    const house = votes.filter(v => v.chamber === "house").length;
    const passed = votes.filter(v => (v.result || "").toLowerCase().includes("pass") || (v.result || "").toLowerCase().includes("agreed")).length;
    const failed = votes.length - passed;

    const byMonth: Record<string, { month: string; senate: number; house: number }> = {};
    votes.forEach(v => {
      const d = new Date(v.date);
      if (isNaN(d.getTime())) return;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      const label = d.toLocaleString("default", { month: "short", year: "2-digit" });
      if (!byMonth[key]) byMonth[key] = { month: label, senate: 0, house: 0 };
      if (v.chamber === "senate") byMonth[key].senate++;
      else byMonth[key].house++;
    });

    const monthData = Object.entries(byMonth).sort(([a], [b]) => a.localeCompare(b)).map(([, v]) => v);

    const demMembers = members.filter(m => m.party === "D").length;
    const repMembers = members.filter(m => m.party === "R").length;
    const indMembers = members.length - demMembers - repMembers;

    const yea = memberVotes.filter(mv => mv.vote_position === "Yea" || mv.vote_position === "Yes").length;
    const nay = memberVotes.filter(mv => mv.vote_position === "Nay" || mv.vote_position === "No").length;

    return { senate, house, passed, failed, monthData, demMembers, repMembers, indMembers, yea, nay };
  }, [votes, members, memberVotes]);

  const loading = vLoading || mLoading;

  const partyData = [
    { name: "Democrat", value: stats.demMembers, color: DEM_COLOR },
    { name: "Republican", value: stats.repMembers, color: REP_COLOR },
    { name: "Independent", value: stats.indMembers, color: "hsl(142,60%,45%)" },
  ].filter(p => p.value > 0);

  const outcomeData = [
    { name: "Passed / Agreed", value: stats.passed, color: "hsl(142,60%,45%)" },
    { name: "Failed / Rejected", value: stats.failed, color: REP_COLOR },
  ].filter(p => p.value > 0);

  if (loading) {
    return (
      <div className="p-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => <div key={i} className="bg-card border border-border rounded-lg p-4 h-24 animate-pulse" />)}
        </div>
      </div>
    );
  }

  if (votes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-center p-8">
        <Building2 size={48} className="text-muted-foreground" />
        <div>
          <p className="text-lg font-semibold text-foreground">No data loaded yet</p>
          <p className="text-sm text-muted-foreground mt-1">
            Copy your CSV files from <code className="bg-secondary px-1 rounded text-xs">congress-vote-tracker/data/</code> into <code className="bg-secondary px-1 rounded text-xs">dashboard/client/public/data/</code> and refresh.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">Overview</h1>
        <p className="text-sm text-muted-foreground">119th Congress · last 12 months</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI label="Total Votes" value={votes.length.toLocaleString()} icon={Vote} sub={`${stats.senate} Senate · ${stats.house} House`} />
        <KPI label="Members" value={members.length.toLocaleString()} icon={Users} sub={`${stats.demMembers}D · ${stats.repMembers}R`} />
        <KPI label="Passed" value={stats.passed.toLocaleString()} icon={TrendingUp} sub={`${Math.round((stats.passed / (votes.length || 1)) * 100)}% pass rate`} />
        <KPI label="Yea Votes Cast" value={stats.yea.toLocaleString()} icon={Building2} sub={`${stats.nay.toLocaleString()} Nay`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Votes by month */}
        <div className="lg:col-span-2 bg-card border border-border rounded-lg p-4">
          <p className="text-sm font-medium text-foreground mb-4">Votes by Month</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats.monthData} barCategoryGap="30%">
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }} />
              <Bar dataKey="senate" name="Senate" fill={DEM_COLOR} radius={[3, 3, 0, 0]} />
              <Bar dataKey="house" name="House" fill={REP_COLOR} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Party composition */}
        <div className="bg-card border border-border rounded-lg p-4">
          <p className="text-sm font-medium text-foreground mb-4">Party Composition</p>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={partyData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} innerRadius={40}>
                {partyData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Vote outcomes */}
      <div className="bg-card border border-border rounded-lg p-4">
        <p className="text-sm font-medium text-foreground mb-4">Vote Outcomes</p>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={outcomeData} layout="vertical" barCategoryGap="40%">
            <XAxis type="number" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} width={120} />
            <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }} />
            <Bar dataKey="value" name="Votes" radius={[0, 3, 3, 0]}>
              {outcomeData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
