import { useVotes, useBillContext } from "@/hooks/useData";
import { useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const DEM = "hsl(213,80%,55%)";
const REP = "hsl(0,72%,52%)";

export default function BillExplorer() {
  const { data: votes = [], isLoading } = useVotes();
  const { data: billCtx = [] } = useBillContext();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [chamberFilter, setChamberFilter] = useState<"all" | "senate" | "house">("all");

  const billCtxMap = useMemo(() => {
    const m: Record<string, typeof billCtx[0]> = {};
    billCtx.forEach(b => { m[b.bill_number] = b; });
    return m;
  }, [billCtx]);

  const bills = useMemo(() => {
    const seen = new Set<string>();
    const out: typeof votes = [];
    votes.forEach(v => {
      if (!seen.has(v.bill_number)) { seen.add(v.bill_number); out.push(v); }
    });
    return out
      .filter(v => chamberFilter === "all" || v.chamber === chamberFilter)
      .filter(v => {
        if (!search) return true;
        const q = search.toLowerCase();
        return (v.bill_title || "").toLowerCase().includes(q) || (v.bill_number || "").toLowerCase().includes(q);
      })
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [votes, search, chamberFilter]);

  const selectedVote = selected ? votes.find(v => v.bill_number === selected) : null;
  const selectedCtx = selected ? billCtxMap[selected] : null;

  const chartData = selectedVote
    ? [
        { name: "Dem Yes", value: selectedVote.dem_yes || 0, color: DEM },
        { name: "Dem No", value: selectedVote.dem_no || 0, color: "hsl(213,80%,75%)" },
        { name: "Rep Yes", value: selectedVote.rep_yes || 0, color: REP },
        { name: "Rep No", value: selectedVote.rep_no || 0, color: "hsl(0,72%,70%)" },
      ]
    : [];

  if (isLoading) return <div className="p-6 text-muted-foreground text-sm">Loading votes…</div>;

  return (
    <div className="flex h-full overflow-hidden">
      {/* List */}
      <div className="w-80 flex-shrink-0 border-r border-border flex flex-col">
        <div className="p-3 border-b border-border space-y-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              data-testid="bill-search"
              placeholder="Search bills…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 h-8 text-sm"
            />
          </div>
          <div className="flex gap-1">
            {(["all", "senate", "house"] as const).map(c => (
              <button
                key={c}
                data-testid={`filter-${c}`}
                onClick={() => setChamberFilter(c)}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${chamberFilter === c ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"}`}
              >
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {bills.length === 0 && (
            <p className="text-xs text-muted-foreground p-4">No bills found.</p>
          )}
          {bills.map(v => (
            <button
              key={v.bill_number}
              data-testid={`bill-row-${v.bill_number}`}
              onClick={() => setSelected(v.bill_number)}
              className={`w-full text-left px-3 py-2.5 border-b border-border transition-colors ${selected === v.bill_number ? "bg-primary/10 border-l-2 border-l-primary" : "hover:bg-secondary"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-mono text-muted-foreground">{v.bill_number}</span>
                <Badge variant="outline" className="text-xs capitalize">{v.chamber}</Badge>
              </div>
              <p className="text-xs text-foreground mt-0.5 line-clamp-2 leading-snug">{v.bill_title || "—"}</p>
              <p className="text-xs text-muted-foreground mt-1">{v.date} · {v.result}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedVote ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Select a bill to see details
          </div>
        ) : (
          <div className="space-y-5 max-w-2xl">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-sm text-muted-foreground">{selectedVote.bill_number}</span>
                <Badge variant="outline" className="capitalize">{selectedVote.chamber}</Badge>
                <Badge variant={selectedVote.result?.toLowerCase().includes("pass") ? "default" : "destructive"} className="text-xs">
                  {selectedVote.result}
                </Badge>
              </div>
              <h2 className="text-lg font-semibold text-foreground leading-snug">{selectedVote.bill_title || "—"}</h2>
              <p className="text-sm text-muted-foreground mt-1">{selectedVote.date} · Roll call #{selectedVote.roll_call_number}</p>
            </div>

            {/* Vote totals */}
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Yes", value: selectedVote.total_yes, color: "text-green-400" },
                { label: "No", value: selectedVote.total_no, color: "text-red-400" },
                { label: "Not Voting", value: selectedVote.total_not_voting, color: "text-muted-foreground" },
                { label: "Present", value: selectedVote.total_present, color: "text-muted-foreground" },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-secondary rounded-lg p-3 text-center">
                  <div className={`text-xl font-bold tabular-nums ${color}`}>{value ?? 0}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
                </div>
              ))}
            </div>

            {/* Party breakdown chart */}
            <div className="bg-card border border-border rounded-lg p-4">
              <p className="text-sm font-medium text-foreground mb-3">Party Breakdown</p>
              <ResponsiveContainer width="100%" height={150}>
                <BarChart data={chartData} barCategoryGap="30%">
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }} />
                  <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                    {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Congress.gov summary */}
            {selectedCtx?.congress_gov_summary && (
              <div className="bg-card border border-border rounded-lg p-4">
                <p className="text-sm font-medium text-foreground mb-2">Official Summary</p>
                <p className="text-sm text-muted-foreground leading-relaxed">{selectedCtx.congress_gov_summary}</p>
              </div>
            )}

            {/* Bill URL */}
            {selectedVote.bill_url && (
              <a href={selectedVote.bill_url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                View on Congress.gov →
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
