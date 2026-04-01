import { useVotes, useMemberVotes, useMembers } from "@/hooks/useData";
import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis, Legend
} from "recharts";

const DEM = "hsl(213,80%,55%)";
const REP = "hsl(0,72%,52%)";

export default function PartyComparison() {
  const { data: votes = [], isLoading: vl } = useVotes();
  const { data: memberVotes = [], isLoading: ml } = useMemberVotes();
  const { data: members = [] } = useMembers();

  const partyMap = useMemo(() => {
    const m: Record<string, string> = {};
    members.forEach(mem => { m[mem.member_id] = mem.party; });
    // also from memberVotes directly
    memberVotes.forEach(mv => { if (!m[mv.member_id]) m[mv.member_id] = mv.party; });
    return m;
  }, [members, memberVotes]);

  const partyVoteStats = useMemo(() => {
    const stats: Record<string, { yea: number; nay: number; notVoting: number }> = {
      D: { yea: 0, nay: 0, notVoting: 0 },
      R: { yea: 0, nay: 0, notVoting: 0 },
    };
    memberVotes.forEach(mv => {
      const party = mv.party || partyMap[mv.member_id] || "?";
      if (!stats[party]) return;
      const pos = (mv.vote_position || "").toLowerCase();
      if (pos === "yea" || pos === "yes") stats[party].yea++;
      else if (pos === "nay" || pos === "no") stats[party].nay++;
      else if (pos === "not voting") stats[party].notVoting++;
    });
    return [
      { party: "Democrat", ...stats.D, color: DEM },
      { party: "Republican", ...stats.R, color: REP },
    ];
  }, [memberVotes, partyMap]);

  // Bipartisanship: votes where both parties had majority Yea
  const bipartisanData = useMemo(() => {
    const votePartyPos: Record<string, { D_yea: number; D_total: number; R_yea: number; R_total: number }> = {};
    memberVotes.forEach(mv => {
      const party = mv.party || partyMap[mv.member_id];
      if (party !== "D" && party !== "R") return;
      if (!votePartyPos[mv.vote_id]) votePartyPos[mv.vote_id] = { D_yea: 0, D_total: 0, R_yea: 0, R_total: 0 };
      const pos = (mv.vote_position || "").toLowerCase();
      const isYea = pos === "yea" || pos === "yes";
      if (party === "D") { votePartyPos[mv.vote_id].D_total++; if (isYea) votePartyPos[mv.vote_id].D_yea++; }
      if (party === "R") { votePartyPos[mv.vote_id].R_total++; if (isYea) votePartyPos[mv.vote_id].R_yea++; }
    });

    let bipartisan = 0, partisan = 0;
    Object.values(votePartyPos).forEach(({ D_yea, D_total, R_yea, R_total }) => {
      const demMaj = D_total > 0 && (D_yea / D_total) > 0.5;
      const repMaj = R_total > 0 && (R_yea / R_total) > 0.5;
      if (demMaj && repMaj) bipartisan++;
      else partisan++;
    });

    return [
      { name: "Bipartisan", value: bipartisan, color: "hsl(142,60%,45%)" },
      { name: "Party-line", value: partisan, color: "hsl(45,80%,55%)" },
    ];
  }, [memberVotes, partyMap]);

  // Per-bill party breakdown (top 20 by total votes)
  const perBillData = useMemo(() => {
    return votes
      .filter(v => (v.dem_yes || 0) + (v.dem_no || 0) + (v.rep_yes || 0) + (v.rep_no || 0) > 0)
      .sort((a, b) => ((b.total_yes || 0) + (b.total_no || 0)) - ((a.total_yes || 0) + (a.total_no || 0)))
      .slice(0, 20)
      .map(v => ({
        name: v.bill_number.length > 14 ? v.bill_number.slice(0, 14) + "…" : v.bill_number,
        dem_yes: v.dem_yes || 0,
        dem_no: v.dem_no || 0,
        rep_yes: v.rep_yes || 0,
        rep_no: v.rep_no || 0,
      }));
  }, [votes]);

  if (vl || ml) return <div className="p-6 text-muted-foreground text-sm">Loading…</div>;

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-bold text-foreground">Party Comparison</h1>
        <p className="text-sm text-muted-foreground">Democrat vs Republican voting patterns</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Total votes by party */}
        <div className="bg-card border border-border rounded-lg p-4">
          <p className="text-sm font-medium text-foreground mb-4">Total Votes by Party</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={partyVoteStats} barCategoryGap="40%">
              <XAxis dataKey="party" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="yea" name="Yea" fill="hsl(142,60%,45%)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="nay" name="Nay" fill="hsl(0,72%,52%)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="notVoting" name="Not Voting" fill="hsl(var(--muted-foreground))" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Bipartisanship */}
        <div className="bg-card border border-border rounded-lg p-4">
          <p className="text-sm font-medium text-foreground mb-1">Bipartisanship</p>
          <p className="text-xs text-muted-foreground mb-4">Votes where both parties had majority Yea</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={bipartisanData} layout="vertical" barCategoryGap="40%">
              <XAxis type="number" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} width={90} />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }} />
              <Bar dataKey="value" name="Votes" radius={[0, 3, 3, 0]}>
                {bipartisanData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Per-bill breakdown */}
      {perBillData.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-4">
          <p className="text-sm font-medium text-foreground mb-1">Per-Bill Party Breakdown (top 20 by total votes)</p>
          <p className="text-xs text-muted-foreground mb-4">Dem Yes · Dem No · Rep Yes · Rep No</p>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={perBillData} barCategoryGap="20%">
              <XAxis dataKey="name" tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="dem_yes" name="Dem Yes" fill={DEM} radius={[2, 2, 0, 0]} />
              <Bar dataKey="dem_no" name="Dem No" fill="hsl(213,80%,75%)" radius={[2, 2, 0, 0]} />
              <Bar dataKey="rep_yes" name="Rep Yes" fill={REP} radius={[2, 2, 0, 0]} />
              <Bar dataKey="rep_no" name="Rep No" fill="hsl(0,72%,72%)" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
