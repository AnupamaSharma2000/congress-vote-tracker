import Papa from "papaparse";

export interface VoteSummary {
  vote_id: string;
  bill_number: string;
  bill_title: string;
  chamber: string;
  date: string;
  result: string;
  total_yes: number;
  total_no: number;
  total_not_voting: number;
  total_present: number;
  dem_yes: number;
  dem_no: number;
  rep_yes: number;
  rep_no: number;
  vote_question: string;
  congress_session: number;
  roll_call_number: number;
  bill_url: string;
}

export interface MemberVote {
  vote_id: string;
  member_id: string;
  member_name: string;
  party: string;
  state: string;
  vote_position: string;
  chamber: string;
}

export interface Member {
  member_id: string;
  full_name: string;
  party: string;
  state: string;
  chamber: string;
  district: string;
  next_election: string;
  in_office: string;
  gender: string;
  url: string;
  twitter: string;
  phone: string;
  office: string;
}

export interface MemberProfile {
  member_id: string;
  bio_summary: string;
  photo_url: string;
  wiki_url: string;
  total_assets_range: string;
  total_liabilities_range: string;
  outside_income: string;
  data_year: string;
}

export interface BillContext {
  bill_number: string;
  bill_title: string;
  vote_date: string;
  primary_topic: string;
  news_context: string;
  total_related_articles: number;
  sentiment_score: number;
  key_themes: string;
  congress_gov_summary: string;
}

async function loadCSV<T>(path: string): Promise<T[]> {
  const res = await fetch(path);
  const text = await res.text();
  const result = Papa.parse<T>(text, { header: true, skipEmptyLines: true, dynamicTyping: true });
  return result.data;
}

let _cache: Record<string, unknown[]> = {};

export async function getVotes(): Promise<VoteSummary[]> {
  if (!_cache.votes) _cache.votes = await loadCSV<VoteSummary>("/data/votes_summary.csv");
  return _cache.votes as VoteSummary[];
}

export async function getMemberVotes(): Promise<MemberVote[]> {
  if (!_cache.memberVotes) _cache.memberVotes = await loadCSV<MemberVote>("/data/member_votes.csv");
  return _cache.memberVotes as MemberVote[];
}

export async function getMembers(): Promise<Member[]> {
  if (!_cache.members) _cache.members = await loadCSV<Member>("/data/members.csv");
  return _cache.members as Member[];
}

export async function getMemberProfiles(): Promise<MemberProfile[]> {
  if (!_cache.profiles) _cache.profiles = await loadCSV<MemberProfile>("/data/member_profiles.csv");
  return _cache.profiles as MemberProfile[];
}

export async function getBillContext(): Promise<BillContext[]> {
  if (!_cache.bills) _cache.bills = await loadCSV<BillContext>("/data/bill_context.csv");
  return _cache.bills as BillContext[];
}
