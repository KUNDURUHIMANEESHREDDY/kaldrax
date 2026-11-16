import { useApp } from "../store/AppStore";
import { itemStatus } from "../lib/format";

export function useRailBadges() {
  const { state } = useApp();
  const low = state.items.filter((item) => itemStatus(item) !== "in-stock").length;
  const pending = state.requests.filter((request) => request.status === "pending").length;
  return { low, pending };
}
