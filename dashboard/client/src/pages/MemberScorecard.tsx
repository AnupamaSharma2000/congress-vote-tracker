import { useMembers, useMemberVotes, useMemberProfiles } from "@/hooks/useData";
import { useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Search, ExternalLink } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const PARTY_COLOR: Record<string, string> = {
  D: "hsl(213,80%,55%)",
  R: "hsl(0,72%,52%)",
  I: "hsl(142,60%,45%)",
};

export default function MemberScorecard() {
  const { data: members = [], isLoading } = useMembers();
  const { data: memberVotes = [] } = useMemberVotes();
  const { data: profiles = [] } = useMemberProfiles();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [partyFilter, setPartyFilter] = useState<"all" | "D" | "R">("all");

  const profileMap = useMemo(() => {
    const m: Record<string, typeof profiles[0]> = {};
    profiles.forEach(p => { m[p.member_id] = p; });
    return m;
  }, [profiles]);

  const votesByMember = useMemo(() => {
    const m: Record<string, typeof memberVotes> = {};
    memberVotes.forEach(mv => {
      if (!m[mv.member_id]) m[mv.member_id] = [];
      m[mv.member_id].push(mv);
    });
    return m;
  }, [memberVotes]);

  const filteredMembers = useMemo(() =>
    members
      .filter(m => partyFilter === "all" || m.party === partyFilter)
      .filter(m => {
        if (!search) return true;
        const q = search.toLowerCase();
        return (m.full_name || "").toLowerCase().includes(q) || (m.state || "").toLowerCase().includes(q);
      })
      .sort((a, b) => (a.full_name || "").localeCompare(b.full_name || ""))
  , [members, search, partyFilter]);

  const selectedMember = selected ? members.find(m => m.member_id === selected) : null;
  const selectedProfile = selected ? profileMap[selected] : null;
  const selectedVotes = selected ? (votesByMember[selected] || []) : [];

  const voteStats = useMemo(() => {
    if (!selectedVotes.length) return null;
    const yea = selectedVotes.filter(v => v.vote_position === "Yea" || v.vote_position === "Yes").length;
    const nay = selectedVotes.filter(v => v.vote_position === "Nay" || v.vote_position === "No").length;
    const absent = selectedVotes.filter(v => v.vote_position === "Not Voting").length;
    const total = selectedVotes.length;
    return [
      { name: "Yea", value: yea, pct: Math.round((yea / total) * 100), color: "hsl(142,60%,45%)" },
      { name: "Nay", value: nay, pct: Math.round((nay / total) * 100), color: "hsl(0,72%,52%)" },
      { name: "Not Voting", value: absent, pct: Math.round((absent / total) * 100), color: "hsl(var(--muted-foreground))" },
    ];
  }, [selectedVotes]);

  if (isLoading) return <div className="p-6 text-muted-foreground text-sm">Loading members…</div>;

  return (
    <div className="flex h-full overflow-hidden">
      {/* List */}
      <div className="w-72 flex-shrink-0 border-r border-border flex flex-col">
        <div className="p-3 border-b border-border space-y-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              data-testid="member-search"
              placeholder="Search members…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 h-8 text-sm"
            />
          </div>
          <div className="flex gap-1">
            {(["all", "D", "R"] as const).map(p => (
              <button key={p}
                data-testid={`party-filter-${p}`}
                onClick={() => setPartyFilter(p)}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${partyFilter === p ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"}`}
              >
                {p === "all" ? "All" : p === "D" ? "Democrat" : "Republican"}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{filteredMembers.length} members</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {filteredMembers.map(m => (
            <button key={m.member_id}
              data-testid={`member-row-${m.member_id}`}
              onClick={() => setSelected(m.member_id)}
              className={`w-full text-left px-3 py-2.5 border-b border-border transition-colors ${selected === m.member_id ? "bg-primary/10 border-l-2 border-l-primary" : "hover:bg-secondary"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-foreground font-medium truncate">{m.full_name}</span>
                <span className="text-xs font-bold flex-shrink-0" style={{ color: PARTY_COLOR[m.party] || "inherit" }}>{m.party}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">{m.state} · {m.chamber}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedMember ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Select a member to see their scorecard
          </div>
        ) : (
          <div className="space-y-5 max-w-2xl">
            {/* Header */}
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-full bg-secondary flex items-center justify-center text-xl font-bold text-foreground flex-shrink-0">
                {(selectedMember.full_name || "?").charAt(0)}
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-foreground">{selectedMember.full_name}</h2>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <Badge style={{ background: PARTY_COLOR[selectedMember.party] || undefined }} className="text-white text-xs">
                    {selectedMember.party === "D" ? "Democrat" : selectedMember.party === "R" ? "Republican" : selectedMember.party}
                  </Badge>
                  <span className="text-sm text-muted-foreground">{selectedMember.state}</span>
                  <span className="text-sm text-muted-foreground capitalize">{selectedMember.chamber}</span>
                  {selectedMember.gender && <span className="text-sm text-muted-foreground">{selectedMember.gender}</span>}
                </div>
              </div>
            </div>

            {/* Vote record */}
            {voteStats && (
              <div className="bg-card border border-border rounded-lg p-4">
                <p className="text-sm font-medium text-foreground mb-3">Voting Record ({selectedVotes.length} votes)</p>
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {voteStats.map(s => (
                    <div key={s.name} className="text-center">
                      <div className="text-xl font-bold tabular-nums" style={{ color: s.color }}>{s.pct}%</div>
                      <div className="text-xs text-muted-foreground">{s.name}</div>
                      <div className="text-xs text-muted-foreground">({s.value})</div>
                    </div>
                  ))}
                </div>
                <ResponsiveContainer width="100%" height={100}>
                  <BarChart data={voteStats} barCategoryGap="30%">
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12 }} />
                    <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                      {voteStats.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Bio */}
            {selectedProfile?.bio_summary && (
              <div className="bg-card border border-border rounded-lg p-4">
                <p className="text-sm font-medium text-foreground mb-2">Biography</p>
                <p className="text-sm text-muted-foreground leading-relaxed line-clamp-6">{selectedProfile.bio_summary}</p>
                {selectedProfile.wiki_url && (
                  <a href={selectedProfile.wiki_url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline mt-2">
                    Wikipedia <ExternalLink size={10} />
                  </a>
                )}
              </div>
            )}

            {/* Contact */}
            {(selectedMember.phone || selectedMember.office) && (
              <div className="bg-card border border-border rounded-lg p-4">
                <p className="text-sm font-medium text-foreground mb-2">Contact</p>
                {selectedMember.office && <p className="text-sm text-muted-foreground">{selectedMember.office}</p>}
                {selectedMember.phone && <p className="text-sm text-muted-foreground">{selectedMember.phone}</p>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
