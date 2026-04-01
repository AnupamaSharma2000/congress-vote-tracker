import { useQuery } from "@tanstack/react-query";
import {
  getVotes, getMemberVotes, getMembers, getMemberProfiles, getBillContext,
  VoteSummary, MemberVote, Member, MemberProfile, BillContext
} from "@/lib/csv";

export function useVotes() {
  return useQuery<VoteSummary[]>({ queryKey: ["votes"], queryFn: getVotes });
}

export function useMemberVotes() {
  return useQuery<MemberVote[]>({ queryKey: ["memberVotes"], queryFn: getMemberVotes });
}

export function useMembers() {
  return useQuery<Member[]>({ queryKey: ["members"], queryFn: getMembers });
}

export function useMemberProfiles() {
  return useQuery<MemberProfile[]>({ queryKey: ["profiles"], queryFn: getMemberProfiles });
}

export function useBillContext() {
  return useQuery<BillContext[]>({ queryKey: ["billContext"], queryFn: getBillContext });
}
