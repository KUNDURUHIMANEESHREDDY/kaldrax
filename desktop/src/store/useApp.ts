import { useContext } from "react";
import { StoreContext } from "./store-context";
import type { StoreApi } from "./AppStore";

export function useApp(): StoreApi {
  const context = useContext(StoreContext);
  if (!context) throw new Error("useApp must be used inside AppStoreProvider");
  return context;
}
