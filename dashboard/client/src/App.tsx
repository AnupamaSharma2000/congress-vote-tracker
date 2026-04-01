import { Switch, Route, Router } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./lib/queryClient";
import { Toaster } from "@/components/ui/toaster";
import Sidebar from "./components/Sidebar";
import Overview from "./pages/Overview";
import BillExplorer from "./pages/BillExplorer";
import MemberScorecard from "./pages/MemberScorecard";
import PartyComparison from "./pages/PartyComparison";
import NotFound from "./pages/not-found";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router hook={useHashLocation}>
        <div className="flex h-screen overflow-hidden bg-background">
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            <Switch>
              <Route path="/" component={Overview} />
              <Route path="/bills" component={BillExplorer} />
              <Route path="/members" component={MemberScorecard} />
              <Route path="/parties" component={PartyComparison} />
              <Route component={NotFound} />
            </Switch>
          </main>
        </div>
      </Router>
      <Toaster />
    </QueryClientProvider>
  );
}
